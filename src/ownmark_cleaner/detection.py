from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

from ownmark_cleaner.video_io import VideoInfo, get_video_info, open_video


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int
    area: int


@dataclass(frozen=True)
class DetectionResult:
    mask: np.ndarray
    first_frame: np.ndarray
    boxes: list[Box]
    video_info: VideoInfo


def parse_rect(rect_str: str) -> tuple[int, int, int, int]:
    """Parse CLI rectangle in x,y,w,h format."""
    parts = [p.strip() for p in rect_str.split(",")]
    if len(parts) != 4:
        raise ValueError("rect must have 4 comma-separated values: x,y,w,h")

    try:
        x, y, w, h = [int(p) for p in parts]
    except ValueError as exc:
        raise ValueError("rect values must be integers: x,y,w,h") from exc

    if w <= 0 or h <= 0:
        raise ValueError("rect width and height must be positive")

    return x, y, w, h


def create_rect_mask(
    *,
    width: int,
    height: int,
    rects: list[tuple[int, int, int, int]] | None = None,
    mask_path: Path | None = None,
    expand: int = 0,
) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)

    for x, y, w, h in rects or []:
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(width, x + w)
        y2 = min(height, y + h)
        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = 255

    if mask_path:
        external_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if external_mask is None:
            raise FileNotFoundError(f"Cannot read mask image: {mask_path}")

        if external_mask.shape[:2] != (height, width):
            external_mask = cv2.resize(external_mask, (width, height), interpolation=cv2.INTER_NEAREST)

        _, external_mask = cv2.threshold(external_mask, 10, 255, cv2.THRESH_BINARY)
        mask = cv2.bitwise_or(mask, external_mask)

    if expand > 0:
        kernel = np.ones((expand * 2 + 1, expand * 2 + 1), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)

    return mask



def clamp_box(x: int, y: int, w: int, h: int, width: int, height: int, padding: int = 0) -> Box:
    """Clamp a padded box to frame boundaries."""
    x1 = max(0, int(x) - padding)
    y1 = max(0, int(y) - padding)
    x2 = min(width, int(x + w) + padding)
    y2 = min(height, int(y + h) + padding)
    return Box(x=x1, y=y1, w=max(0, x2 - x1), h=max(0, y2 - y1), area=max(0, x2 - x1) * max(0, y2 - y1))


def _boxes_overlap_or_close(a: Box, b: Box, gap: int) -> bool:
    """Return true when two boxes overlap after expanding each by gap pixels."""
    ax1, ay1, ax2, ay2 = a.x - gap, a.y - gap, a.x + a.w + gap, a.y + a.h + gap
    bx1, by1, bx2, by2 = b.x, b.y, b.x + b.w, b.y + b.h
    return ax1 <= bx2 and ax2 >= bx1 and ay1 <= by2 and ay2 >= by1


def merge_nearby_boxes(boxes: list[Box], *, gap: int, width: int, height: int) -> list[Box]:
    """Merge detected pieces that probably belong to the same watermark."""
    if not boxes:
        return []

    merged = [clamp_box(b.x, b.y, b.w, b.h, width, height) for b in boxes]
    changed = True

    while changed:
        changed = False
        result: list[Box] = []
        used = [False] * len(merged)

        for i, box in enumerate(merged):
            if used[i]:
                continue

            x1, y1 = box.x, box.y
            x2, y2 = box.x + box.w, box.y + box.h
            used[i] = True

            for j in range(i + 1, len(merged)):
                if used[j]:
                    continue
                other = merged[j]
                candidate = Box(x=x1, y=y1, w=x2 - x1, h=y2 - y1, area=(x2 - x1) * (y2 - y1))
                if _boxes_overlap_or_close(candidate, other, gap):
                    x1 = min(x1, other.x)
                    y1 = min(y1, other.y)
                    x2 = max(x2, other.x + other.w)
                    y2 = max(y2, other.y + other.h)
                    used[j] = True
                    changed = True

            result.append(clamp_box(x1, y1, x2 - x1, y2 - y1, width, height))

        merged = result

    return merged



def filter_boxes_by_position(
    boxes: list[Box],
    *,
    width: int,
    height: int,
    position: str = "all",
    keep_largest: bool = False,
) -> list[Box]:
    if position == "all" and not keep_largest:
        return boxes

    def in_position(box: Box) -> bool:
        cx = box.x + box.w / 2
        cy = box.y + box.h / 2

        if position == "all":
            return True
        if position == "top-left":
            return cx < width / 2 and cy < height / 2
        if position == "top-right":
            return cx >= width / 2 and cy < height / 2
        if position == "bottom-left":
            return cx < width / 2 and cy >= height / 2
        if position == "bottom-right":
            return cx >= width / 2 and cy >= height / 2
        if position == "center":
            return width * 0.25 <= cx <= width * 0.75 and height * 0.25 <= cy <= height * 0.75

        raise ValueError("position must be all, top-left, top-right, bottom-left, bottom-right, or center")

    filtered = [box for box in boxes if in_position(box)]

    if not filtered:
        return []

    if keep_largest:
        return [max(filtered, key=lambda b: b.area)]

    return filtered


def mask_from_boxes(width: int, height: int, boxes: list[Box], *, padding: int = 0) -> np.ndarray:

    """Create a solid mask by filling detected bounding boxes.

    This is useful for translucent watermark panels: edge-only masks can leave a
    visible rectangular/rounded ghost, while a filled box repairs the whole panel.
    """
    mask = np.zeros((height, width), dtype=np.uint8)
    for box in boxes:
        padded = clamp_box(box.x, box.y, box.w, box.h, width, height, padding)
        if padded.w > 0 and padded.h > 0:
            mask[padded.y : padded.y + padded.h, padded.x : padded.x + padded.w] = 255
    return mask


def build_search_area(width: int, height: int, mode: str = "edges", margin_ratio: float = 0.22) -> np.ndarray:
    """Return mask of where the detector is allowed to look."""
    search_mask = np.zeros((height, width), dtype=np.uint8)
    mx = max(1, int(width * margin_ratio))
    my = max(1, int(height * margin_ratio))

    if mode == "full":
        search_mask[:, :] = 255
    elif mode == "edges":
        search_mask[:my, :] = 255
        search_mask[height - my :, :] = 255
        search_mask[:, :mx] = 255
        search_mask[:, width - mx :] = 255
    elif mode == "corners":
        search_mask[:my, :mx] = 255
        search_mask[:my, width - mx :] = 255
        search_mask[height - my :, :mx] = 255
        search_mask[height - my :, width - mx :] = 255
    else:
        raise ValueError("search must be one of: edges, corners, full")

    return search_mask


def sample_edge_persistence(
    input_path: Path,
    *,
    sample_frames: int = 80,
    canny_low: int = 60,
    canny_high: int = 160,
) -> tuple[np.ndarray, np.ndarray, VideoInfo]:
    cap = open_video(input_path)
    info = get_video_info(cap)

    if info.total_frames > 0:
        indices = np.linspace(0, max(0, info.total_frames - 1), sample_frames).astype(int)
    else:
        indices = np.arange(sample_frames)

    edge_sum = np.zeros((info.height, info.width), dtype=np.float32)
    valid_count = 0
    first_frame: np.ndarray | None = None

    for idx in tqdm(indices, desc="Sampling frames"):
        if info.total_frames > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))

        ok, frame = cap.read()
        if not ok:
            continue

        if first_frame is None:
            first_frame = frame.copy()

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(gray, canny_low, canny_high)
        edge_sum += (edges > 0).astype(np.float32)
        valid_count += 1

    cap.release()

    if valid_count == 0 or first_frame is None:
        raise RuntimeError("Could not sample frames from video.")

    return edge_sum / valid_count, first_frame, info


def auto_detect_watermark(
    input_path: Path,
    *,
    search: str = "edges",
    sample_frames: int = 80,
    threshold: float = 0.45,
    min_area_ratio: float = 0.00002,
    max_area_ratio: float = 0.08,
    dilate: int = 9,
    close: int = 21,
    margin_ratio: float = 0.22,
    canny_low: int = 60,
    canny_high: int = 160,
    fill_boxes: bool = False,
    box_padding: int = 12,
    box_merge_gap: int = 24,
    keep_position: str = "all",
    keep_largest: bool = False,
) -> DetectionResult:
    persistence, first_frame, info = sample_edge_persistence(
        input_path,
        sample_frames=sample_frames,
        canny_low=canny_low,
        canny_high=canny_high,
    )

    search_area = build_search_area(info.width, info.height, mode=search, margin_ratio=margin_ratio)

    raw = np.zeros((info.height, info.width), dtype=np.uint8)
    raw[(persistence >= threshold) & (search_area > 0)] = 255

    if close > 0:
        kernel = np.ones((close, close), np.uint8)
        raw = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, kernel)

    if dilate > 0:
        kernel = np.ones((dilate, dilate), np.uint8)
        raw = cv2.dilate(raw, kernel, iterations=1)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(raw, connectivity=8)

    component_mask = np.zeros_like(raw)
    frame_area = info.width * info.height
    min_area = int(frame_area * min_area_ratio)
    max_area = int(frame_area * max_area_ratio)
    boxes: list[Box] = []

    for label in range(1, num_labels):
        x, y, w, h, area = stats[label]

        if area < min_area or area > max_area:
            continue
        if w > info.width * 0.8 or h > info.height * 0.8:
            continue

        component = (labels == label).astype(np.uint8) * 255
        component_mask = cv2.bitwise_or(component_mask, component)
        boxes.append(Box(x=int(x), y=int(y), w=int(w), h=int(h), area=int(area)))

    if fill_boxes:
        boxes = filter_boxes_by_position(
            boxes,
            width=info.width,
            height=info.height,
            position=keep_position,
            keep_largest=False,
        )

        if not boxes:
            raise RuntimeError(
                f"No detected area matched keep_position={keep_position}. "
                "Try --keep-position all or lower --threshold."
            )

        boxes = merge_nearby_boxes(
            boxes,
            gap=max(0, box_merge_gap),
            width=info.width,
            height=info.height,
        )

        boxes = filter_boxes_by_position(
            boxes,
            width=info.width,
            height=info.height,
            position=keep_position,
            keep_largest=keep_largest,
        )

        final_mask = mask_from_boxes(
            info.width,
            info.height,
            boxes,
            padding=max(0, box_padding),
        )
    else:
        boxes = filter_boxes_by_position(
            boxes,
            width=info.width,
            height=info.height,
            position=keep_position,
            keep_largest=keep_largest,
        )

        if not boxes:
            raise RuntimeError(
                f"No detected area matched keep_position={keep_position}. "
                "Try --keep-position all or lower --threshold."
            )

        final_mask = np.zeros_like(component_mask)
        for box in boxes:
            final_mask[
                max(0, box.y):min(info.height, box.y + box.h),
                max(0, box.x):min(info.width, box.x + box.w),
            ] = component_mask[
                max(0, box.y):min(info.height, box.y + box.h),
                max(0, box.x):min(info.width, box.x + box.w),
            ]

    if np.count_nonzero(final_mask) == 0:
        raise RuntimeError(
            "No watermark-like fixed area detected. Try: "
            "--search full --threshold 0.35 --sample-frames 120"
        )

    return DetectionResult(mask=final_mask, first_frame=first_frame, boxes=boxes, video_info=info)


def save_detection_preview(
    *,
    first_frame: np.ndarray,
    mask: np.ndarray,
    boxes: list[Box],
    preview_path: Path,
    mask_path: Path,
) -> None:
    preview = first_frame.copy()
    overlay = preview.copy()
    overlay[mask > 0] = (0, 0, 255)
    preview = cv2.addWeighted(overlay, 0.35, preview, 0.65, 0)

    for box in boxes:
        cv2.rectangle(preview, (box.x, box.y), (box.x + box.w, box.y + box.h), (0, 0, 255), 2)

    cv2.imwrite(str(preview_path), preview)
    cv2.imwrite(str(mask_path), mask)
