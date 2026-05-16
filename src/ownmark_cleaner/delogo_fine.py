from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

from ownmark_cleaner.video_io import (
    build_ffmpeg_rawvideo_cmd,
    check_ffmpeg,
    get_video_info,
    open_video,
    start_ffmpeg_pipe,
)


def soft_alpha(mask: np.ndarray, feather: int, strength: float = 1.0) -> np.ndarray:
    alpha = mask.astype(np.float32) / 255.0

    if feather > 0:
        k = feather * 2 + 1
        if k % 2 == 0:
            k += 1
        alpha = cv2.GaussianBlur(alpha, (k, k), 0)

    alpha = np.clip(alpha * strength, 0.0, 1.0)
    return alpha[..., None]


def rects_to_mask(height: int, width: int, rects: list[tuple[int, int, int, int]]) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)

    for x, y, w, h in rects:
        x1 = max(0, int(x))
        y1 = max(0, int(y))
        x2 = min(width, int(x + w))
        y2 = min(height, int(y + h))

        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = 255

    return mask


def make_bright_stroke_mask(
    frame: np.ndarray,
    rects: list[tuple[int, int, int, int]],
    *,
    threshold: int = 8,
    kernel_size: int = 35,
    dilate: int = 1,
) -> np.ndarray:
    """
    Only extract bright watermark strokes inside selected rectangles.

    This is much better than repairing the whole rectangle.
    """
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    final = np.zeros((h, w), dtype=np.uint8)

    if kernel_size % 2 == 0:
        kernel_size += 1

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (kernel_size, kernel_size),
    )

    for x, y, rw, rh in rects:
        x1 = max(0, int(x))
        y1 = max(0, int(y))
        x2 = min(w, int(x + rw))
        y2 = min(h, int(y + rh))

        if x2 <= x1 or y2 <= y1:
            continue

        crop = gray[y1:y2, x1:x2]

        # White top-hat extracts bright thin text/border strokes.
        top_hat = cv2.morphologyEx(crop, cv2.MORPH_TOPHAT, kernel)

        _, stroke = cv2.threshold(
            top_hat,
            threshold,
            255,
            cv2.THRESH_BINARY,
        )

        if dilate > 0:
            dk = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (dilate * 2 + 1, dilate * 2 + 1),
            )
            stroke = cv2.dilate(stroke, dk, iterations=1)

        final[y1:y2, x1:x2] = cv2.bitwise_or(final[y1:y2, x1:x2], stroke)

    return final


def remove_white_overlay(
    frame: np.ndarray,
    mask: np.ndarray,
    *,
    opacity: float = 0.22,
    feather: int = 3,
    strength: float = 0.95,
) -> np.ndarray:
    """
    Reverse a semi-transparent white watermark.

    observed = original * (1 - opacity) + 255 * opacity
    original = (observed - 255 * opacity) / (1 - opacity)
    """
    opacity = float(np.clip(opacity, 0.01, 0.90))

    frame_f = frame.astype(np.float32)
    recovered = (frame_f - 255.0 * opacity) / (1.0 - opacity)
    recovered = np.clip(recovered, 0, 255)

    alpha = soft_alpha(mask, feather=feather, strength=strength)
    out = frame_f * (1.0 - alpha) + recovered * alpha

    return np.clip(out, 0, 255).astype(np.uint8)


def remove_black_overlay(
    frame: np.ndarray,
    mask: np.ndarray,
    *,
    opacity: float = 0.22,
    feather: int = 3,
    strength: float = 0.95,
) -> np.ndarray:
    """
    Reverse a semi-transparent dark watermark.

    observed = original * (1 - opacity)
    original = observed / (1 - opacity)
    """
    opacity = float(np.clip(opacity, 0.01, 0.90))

    frame_f = frame.astype(np.float32)
    recovered = frame_f / (1.0 - opacity)
    recovered = np.clip(recovered, 0, 255)

    alpha = soft_alpha(mask, feather=feather, strength=strength)
    out = frame_f * (1.0 - alpha) + recovered * alpha

    return np.clip(out, 0, 255).astype(np.uint8)


def fine_delogo_video(
    *,
    input_path: Path,
    output_path: Path,
    rects: list[tuple[int, int, int, int]],
    mask_mode: str = "bright-strokes",
    remove_mode: str = "white-overlay",
    stroke_threshold: int = 8,
    stroke_kernel: int = 35,
    stroke_dilate: int = 1,
    overlay_opacity: float = 0.22,
    feather: int = 3,
    strength: float = 0.95,
    inpaint_radius: float = 1.2,
    inpaint_method: str = "telea",
    crf: int = 15,
    preset: str = "medium",
    audio: str = "copy",
) -> None:
    check_ffmpeg()

    cap = open_video(input_path)
    info = get_video_info(cap)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = build_ffmpeg_rawvideo_cmd(
        width=info.width,
        height=info.height,
        fps=info.fps,
        input_path=input_path,
        output_path=output_path,
        crf=crf,
        preset=preset,
        audio=audio,
    )

    proc = start_ffmpeg_pipe(cmd)

    if inpaint_method == "telea":
        flag = cv2.INPAINT_TELEA
    else:
        flag = cv2.INPAINT_NS

    try:
        with tqdm(total=info.total_frames if info.total_frames > 0 else None, desc="Fine delogo") as pbar:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                if mask_mode == "full-rect":
                    mask = rects_to_mask(info.height, info.width, rects)
                else:
                    mask = make_bright_stroke_mask(
                        frame,
                        rects,
                        threshold=stroke_threshold,
                        kernel_size=stroke_kernel,
                        dilate=stroke_dilate,
                    )

                if remove_mode == "white-overlay":
                    frame = remove_white_overlay(
                        frame,
                        mask,
                        opacity=overlay_opacity,
                        feather=feather,
                        strength=strength,
                    )

                elif remove_mode == "black-overlay":
                    frame = remove_black_overlay(
                        frame,
                        mask,
                        opacity=overlay_opacity,
                        feather=feather,
                        strength=strength,
                    )

                elif remove_mode == "inpaint":
                    frame = cv2.inpaint(frame, mask, inpaint_radius, flag)

                else:
                    raise ValueError("remove_mode must be white-overlay, black-overlay, or inpaint")

                if proc.stdin is None:
                    raise RuntimeError("FFmpeg stdin pipe closed.")

                proc.stdin.write(frame.tobytes())
                pbar.update(1)

    finally:
        cap.release()
        if proc.stdin:
            proc.stdin.close()

    ret = proc.wait()

    if ret != 0:
        raise RuntimeError("FFmpeg failed. Try audio=aac.")
