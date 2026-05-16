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


def inpaint_flag(method: str) -> int:
    if method == "telea":
        return cv2.INPAINT_TELEA
    if method == "ns":
        return cv2.INPAINT_NS
    raise ValueError("method must be telea or ns")


def build_soft_alpha(mask: np.ndarray, feather: int, blend_strength: float) -> np.ndarray:
    """
    Build a soft alpha mask.

    feather:
      0 = hard edge
      4-12 = softer transition, less obvious cut-out border

    blend_strength:
      1.0 = full inpainted result
      0.6-0.85 = preserve some original texture, less mosaic-looking
    """
    alpha = (mask.astype(np.float32) / 255.0)

    if feather > 0:
        k = feather * 2 + 1
        if k % 2 == 0:
            k += 1
        alpha = cv2.GaussianBlur(alpha, (k, k), 0)

    alpha = np.clip(alpha * blend_strength, 0.0, 1.0)
    return alpha[..., None]


def add_original_detail(
    *,
    original: np.ndarray,
    repaired: np.ndarray,
    mask: np.ndarray,
    detail_amount: float,
    detail_sigma: float,
) -> np.ndarray:
    """
    Add a small amount of high-frequency texture back from the original frame.

    This reduces the smooth/mosaic patch feeling.
    Keep detail_amount low, e.g. 0.10-0.25.
    """
    if detail_amount <= 0:
        return repaired

    original_f = original.astype(np.float32)
    repaired_f = repaired.astype(np.float32)

    blur = cv2.GaussianBlur(original_f, (0, 0), detail_sigma)
    detail = original_f - blur

    alpha = (mask.astype(np.float32) / 255.0)[..., None]
    out = repaired_f + detail * detail_amount * alpha

    return np.clip(out, 0, 255).astype(np.uint8)


def process_video(
    *,
    input_path: Path,
    output_path: Path,
    mask: np.ndarray,
    method: str = "telea",
    radius: float = 3,
    crf: int = 18,
    preset: str = "medium",
    audio: str = "copy",
    start: float = 0.0,
    end: float | None = None,
    feather: int = 8,
    blend_strength: float = 0.78,
    detail_amount: float = 0.16,
    detail_sigma: float = 2.0,
) -> None:
    """Inpaint mask region frame-by-frame and encode the result with FFmpeg."""
    check_ffmpeg()

    cap = open_video(input_path)
    info = get_video_info(cap)

    if mask.shape[:2] != (info.height, info.width):
        mask = cv2.resize(mask, (info.width, info.height), interpolation=cv2.INTER_NEAREST)
        _, mask = cv2.threshold(mask, 10, 255, cv2.THRESH_BINARY)

    if np.count_nonzero(mask) == 0:
        raise RuntimeError("Mask is empty.")

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

    flag = inpaint_flag(method)
    frame_index = 0

    try:
        with tqdm(total=info.total_frames if info.total_frames > 0 else None, desc="Inpainting") as pbar:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                current_time = frame_index / info.fps
                should_inpaint = current_time >= start and (end is None or current_time <= end)

                if should_inpaint:
                    original_frame = frame
                    repaired = cv2.inpaint(original_frame, mask, radius, flag)

                    repaired = add_original_detail(
                        original=original_frame,
                        repaired=repaired,
                        mask=mask,
                        detail_amount=detail_amount,
                        detail_sigma=detail_sigma,
                    )

                    if feather > 0 or blend_strength < 1.0:
                        alpha = build_soft_alpha(mask, feather, blend_strength)
                        frame = (
                            original_frame.astype(np.float32) * (1.0 - alpha)
                            + repaired.astype(np.float32) * alpha
                        )
                        frame = np.clip(frame, 0, 255).astype(np.uint8)
                    else:
                        frame = repaired

                if proc.stdin is None:
                    raise RuntimeError("FFmpeg stdin pipe is closed.")

                proc.stdin.write(frame.tobytes())
                frame_index += 1
                pbar.update(1)
    except BrokenPipeError as exc:
        raise RuntimeError("FFmpeg pipe failed. Check FFmpeg output above.") from exc
    finally:
        cap.release()
        if proc.stdin:
            proc.stdin.close()

    return_code = proc.wait()
    if return_code != 0:
        raise RuntimeError("FFmpeg failed. If audio copy failed, retry with --audio aac")
