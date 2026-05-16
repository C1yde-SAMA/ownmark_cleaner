from __future__ import annotations

import math
import uuid
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, jsonify, render_template, request, send_from_directory

from ownmark_cleaner.video_io import (
    build_ffmpeg_rawvideo_cmd,
    check_ffmpeg,
    get_video_info,
    open_video,
    start_ffmpeg_pipe,
)

app = Flask(__name__)

ROOT = Path.cwd()
UPLOAD_DIR = ROOT / "web_uploads"
OUTPUT_DIR = ROOT / "web_outputs"
PREVIEW_DIR = ROOT / "web_previews"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
PREVIEW_DIR.mkdir(exist_ok=True)


def safe_path(path_text: str) -> Path:
    path = Path(path_text)

    if not path.is_absolute():
        path = ROOT / path

    path = path.resolve()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return path


def build_soft_alpha(mask: np.ndarray, feather: int, blend_strength: float) -> np.ndarray:
    alpha = mask.astype(np.float32) / 255.0

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
    if detail_amount <= 0:
        return repaired

    original_f = original.astype(np.float32)
    repaired_f = repaired.astype(np.float32)

    blur = cv2.GaussianBlur(original_f, (0, 0), detail_sigma)
    detail = original_f - blur

    alpha = (mask.astype(np.float32) / 255.0)[..., None]
    out = repaired_f + detail * detail_amount * alpha

    return np.clip(out, 0, 255).astype(np.uint8)


def get_preset(name: str) -> dict:
    presets = {
        "fine": {
            "radius": 1.5,
            "feather": 10,
            "blend_strength": 0.72,
            "detail_amount": 0.20,
            "detail_sigma": 2.0,
            "blur_kernel": 21,
            "blur_strength": 0.45,
            "blur_feather": 18,
            "corner_radius": 22,
            "tile_expand": 1,
            "passes": 1,
        },
        "normal": {
            "radius": 2.2,
            "feather": 8,
            "blend_strength": 0.85,
            "detail_amount": 0.12,
            "detail_sigma": 2.0,
            "blur_kernel": 31,
            "blur_strength": 0.70,
            "blur_feather": 20,
            "corner_radius": 26,
            "tile_expand": 3,
            "passes": 1,
        },
        "strong": {
            "radius": 3.5,
            "feather": 6,
            "blend_strength": 1.0,
            "detail_amount": 0.04,
            "detail_sigma": 2.0,
            "blur_kernel": 61,
            "blur_strength": 1.0,
            "blur_feather": 24,
            "corner_radius": 32,
            "tile_expand": 6,
            "passes": 2,
        },
    }

    return presets.get(name, presets["fine"])


def choose_grid(total_parts: int, w: int, h: int) -> tuple[int, int]:
    total_parts = max(1, int(total_parts))
    aspect = max(w, 1) / max(h, 1)

    cols = max(1, round(math.sqrt(total_parts * aspect)))
    rows = math.ceil(total_parts / cols)

    while rows * cols < total_parts:
        cols += 1
        rows = math.ceil(total_parts / cols)

    return rows, cols


def split_rect(
    rect: tuple[int, int, int, int],
    total_parts: int,
) -> list[tuple[int, int, int, int]]:
    x, y, w, h = rect
    rows, cols = choose_grid(total_parts, w, h)

    parts: list[tuple[int, int, int, int]] = []
    count = 0

    for r in range(rows):
        for c in range(cols):
            if count >= total_parts:
                break

            x1 = x + round(c * w / cols)
            x2 = x + round((c + 1) * w / cols)
            y1 = y + round(r * h / rows)
            y2 = y + round((r + 1) * h / rows)

            pw = x2 - x1
            ph = y2 - y1

            if pw > 1 and ph > 1:
                parts.append((x1, y1, pw, ph))

            count += 1

    return parts


def draw_rounded_rect(
    mask: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    radius: int,
) -> None:
    """
    Draw a filled rounded rectangle on mask.
    """
    if x2 <= x1 or y2 <= y1:
        return

    w = x2 - x1
    h = y2 - y1

    radius = max(0, int(radius))
    radius = min(radius, w // 2, h // 2)

    if radius <= 0:
        mask[y1:y2, x1:x2] = 255
        return

    # Center rectangles
    mask[y1:y2, x1 + radius:x2 - radius] = 255
    mask[y1 + radius:y2 - radius, x1:x2] = 255

    # Four rounded corners
    cv2.circle(mask, (x1 + radius, y1 + radius), radius, 255, -1)
    cv2.circle(mask, (x2 - radius - 1, y1 + radius), radius, 255, -1)
    cv2.circle(mask, (x1 + radius, y2 - radius - 1), radius, 255, -1)
    cv2.circle(mask, (x2 - radius - 1, y2 - radius - 1), radius, 255, -1)


def build_region_mask(
    frame_shape: tuple[int, int, int],
    rects: list[tuple[int, int, int, int]],
    expand: int = 0,
    corner_radius: int = 18,
) -> np.ndarray:
    """
    Build a rounded rectangle mask for the whole selected region.

    corner_radius:
      larger = more rounded corners.
    """
    h, w = frame_shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)

    for x, y, rw, rh in rects:
        x1 = max(0, int(x) - expand)
        y1 = max(0, int(y) - expand)
        x2 = min(w, int(x + rw) + expand)
        y2 = min(h, int(y + rh) + expand)

        if x2 > x1 and y2 > y1:
            # Auto limit radius so tiny boxes do not break.
            auto_radius = min(corner_radius, max(4, min(x2 - x1, y2 - y1) // 3))
            draw_rounded_rect(mask, x1, y1, x2, y2, auto_radius)

    return mask


def apply_gaussian_blur_to_regions(
    frame: np.ndarray,
    rects: list[tuple[int, int, int, int]],
    preset: dict,
) -> np.ndarray:
    blur_kernel = int(preset.get("blur_kernel", 31))
    blur_strength = float(preset.get("blur_strength", 0.75))
    blur_feather = int(preset.get("blur_feather", 8))
    tile_expand = int(preset.get("tile_expand", 0))

    if blur_strength <= 0:
        return frame

    if blur_kernel < 3:
        blur_kernel = 3

    if blur_kernel % 2 == 0:
        blur_kernel += 1

    corner_radius = int(preset.get("corner_radius", 24))

    mask = build_region_mask(
        frame.shape,
        rects,
        expand=tile_expand,
        corner_radius=corner_radius,
    )

    if np.count_nonzero(mask) == 0:
        return frame

    blurred = cv2.GaussianBlur(frame, (blur_kernel, blur_kernel), 0)

    alpha = mask.astype(np.float32) / 255.0

    if blur_feather > 0:
        k = blur_feather * 2 + 1
        if k % 2 == 0:
            k += 1
        alpha = cv2.GaussianBlur(alpha, (k, k), 0)

    alpha = np.clip(alpha * blur_strength, 0.0, 1.0)[..., None]

    out = (
        frame.astype(np.float32) * (1.0 - alpha)
        + blurred.astype(np.float32) * alpha
    )

    return np.clip(out, 0, 255).astype(np.uint8)


def process_frame_tiled(
    frame: np.ndarray,
    rects: list[tuple[int, int, int, int]],
    split_count: int,
    preset: dict,
) -> np.ndarray:
    original = frame.copy()
    working = frame.copy()

    frame_h, frame_w = frame.shape[:2]

    all_tiles: list[tuple[int, int, int, int]] = []

    for rect in rects:
        all_tiles.extend(split_rect(rect, split_count))

    tile_expand = int(preset.get("tile_expand", 0))
    passes = int(preset.get("passes", 1))
    passes = max(1, passes)

    for _ in range(passes):
        for x, y, rw, rh in all_tiles:
            x1 = max(0, int(x) - tile_expand)
            y1 = max(0, int(y) - tile_expand)
            x2 = min(frame_w, int(x + rw) + tile_expand)
            y2 = min(frame_h, int(y + rh) + tile_expand)

            if x2 <= x1 or y2 <= y1:
                continue

            mask = np.zeros((frame_h, frame_w), dtype=np.uint8)
            mask[y1:y2, x1:x2] = 255

            repaired = cv2.inpaint(
                working,
                mask,
                preset["radius"],
                cv2.INPAINT_TELEA,
            )

            repaired = add_original_detail(
                original=original,
                repaired=repaired,
                mask=mask,
                detail_amount=preset["detail_amount"],
                detail_sigma=preset["detail_sigma"],
            )

            alpha = build_soft_alpha(
                mask,
                feather=preset["feather"],
                blend_strength=preset["blend_strength"],
            )

            working = (
                working.astype(np.float32) * (1.0 - alpha)
                + repaired.astype(np.float32) * alpha
            )

            working = np.clip(working, 0, 255).astype(np.uint8)

    working = apply_gaussian_blur_to_regions(
        frame=working,
        rects=rects,
        preset=preset,
    )

    return working


def process_video_tiled(
    *,
    input_path: Path,
    output_path: Path,
    rects: list[tuple[int, int, int, int]],
    split_count: int,
    preset_name: str,
    blur_kernel: int,
    blur_strength: float,
    crf: int = 15,
    preset_codec: str = "medium",
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
        preset=preset_codec,
        audio=audio,
    )

    proc = start_ffmpeg_pipe(cmd)

    preset = dict(get_preset(preset_name))

    # 细腻/标准模式允许网页手动覆盖模糊参数。
    # 强力模式不允许网页参数覆盖，否则强力模式会被削弱。
    if preset_name != "strong":
        blur_kernel = int(blur_kernel)
        if blur_kernel < 0:
            blur_kernel = 0

        if blur_kernel > 0 and blur_kernel % 2 == 0:
            blur_kernel += 1

        blur_strength = float(blur_strength)
        blur_strength = max(0.0, min(1.0, blur_strength))

        if blur_kernel > 0:
            preset["blur_kernel"] = blur_kernel

        preset["blur_strength"] = blur_strength

    frame_index = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame = process_frame_tiled(
                frame=frame,
                rects=rects,
                split_count=split_count,
                preset=preset,
            )

            if proc.stdin is None:
                raise RuntimeError("FFmpeg stdin pipe closed.")

            proc.stdin.write(frame.tobytes())

            frame_index += 1

            if frame_index % 30 == 0:
                print(f"Processed {frame_index} frames")

    finally:
        cap.release()

        if proc.stdin:
            proc.stdin.close()

    ret = proc.wait()

    if ret != 0:
        raise RuntimeError("FFmpeg failed. Try changing audio mode to AAC.")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("video")

    if not file:
        return jsonify({"error": "No video uploaded"}), 400

    suffix = Path(file.filename).suffix.lower() or ".mp4"
    filename = f"{uuid.uuid4().hex}{suffix}"

    save_path = UPLOAD_DIR / filename
    file.save(save_path)

    return jsonify(
        {
            "video_path": str(save_path.relative_to(ROOT)),
            "message": "uploaded",
        }
    )


@app.route("/preview", methods=["POST"])
def preview():
    data = request.get_json(force=True)
    video_path = safe_path(data["video_path"])

    cap = open_video(video_path)
    info = get_video_info(cap)

    ok, frame = cap.read()
    cap.release()

    if not ok:
        return jsonify({"error": "Cannot read first frame"}), 500

    preview_name = f"{video_path.stem}_{uuid.uuid4().hex}.jpg"
    preview_path = PREVIEW_DIR / preview_name

    cv2.imwrite(str(preview_path), frame)

    return jsonify(
        {
            "preview_url": f"/previews/{preview_name}",
            "width": info.width,
            "height": info.height,
            "fps": info.fps,
            "total_frames": info.total_frames,
        }
    )


@app.route("/previews/<path:filename>")
def serve_preview(filename):
    return send_from_directory(PREVIEW_DIR, filename)


@app.route("/outputs/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


@app.route("/clean", methods=["POST"])
def clean():
    try:
        data = request.get_json(force=True)

        video_path = safe_path(data["video_path"])
        rects = data.get("rects", [])

        if not rects:
            return jsonify({"error": "Please draw at least one rectangle"}), 400

        parsed_rects: list[tuple[int, int, int, int]] = []

        for rect in rects:
            x = int(round(rect["x"]))
            y = int(round(rect["y"]))
            w = int(round(rect["w"]))
            h = int(round(rect["h"]))

            if w <= 1 or h <= 1:
                continue

            parsed_rects.append((x, y, w, h))

        if not parsed_rects:
            return jsonify({"error": "No valid rectangles"}), 400

        split_count = int(data.get("split_count", 9))
        preset_name = data.get("preset_name", "fine")
        blur_kernel = int(data.get("blur_kernel", 31))
        blur_strength = float(data.get("blur_strength", 0.75))

        if split_count not in [1, 4, 9, 16, 25, 36]:
            split_count = 9

        if preset_name not in ["fine", "normal", "strong"]:
            preset_name = "fine"

        output_name = f"{video_path.stem}_cleaned_{uuid.uuid4().hex[:8]}.mp4"
        output_path = OUTPUT_DIR / output_name

        process_video_tiled(
            input_path=video_path,
            output_path=output_path,
            rects=parsed_rects,
            split_count=split_count,
            preset_name=preset_name,
            blur_kernel=blur_kernel,
            blur_strength=blur_strength,
            crf=15,
            preset_codec="medium",
            audio="copy",
        )

        return jsonify(
            {
                "message": "done",
                "output_url": f"/outputs/{output_name}",
                "output_path": str(output_path.relative_to(ROOT)),
                "rects": parsed_rects,
                "split_count": split_count,
                "preset_name": preset_name,
                "blur_kernel": blur_kernel,
                "blur_strength": blur_strength,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=7860,
        debug=True,
    )