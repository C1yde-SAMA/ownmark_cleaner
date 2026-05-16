from __future__ import annotations

import argparse
from pathlib import Path


from ownmark_cleaner.detection import (
    Box,
    auto_detect_watermark,
    create_rect_mask,
    parse_rect,
    save_detection_preview,
)
from ownmark_cleaner.inpaint import process_video
from ownmark_cleaner.video_io import get_video_info, open_video

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def preview_paths(input_path: Path, output_dir: Path | None = None) -> tuple[Path, Path]:
    base_dir = output_dir or input_path.parent
    stem = input_path.stem
    return base_dir / f"{stem}_detected_preview.jpg", base_dir / f"{stem}_detected_mask.png"


def print_boxes(boxes: list[Box]) -> None:
    if not boxes:
        print("Detected boxes: none")
        return

    print("Detected boxes:")
    for box in boxes:
        print(f"  x={box.x}, y={box.y}, w={box.w}, h={box.h}, area={box.area}")


def load_or_build_mask(
    *,
    input_path: Path,
    rects: list[tuple[int, int, int, int]],
    mask_path: Path | None,
    auto: bool,
    search: str,
    sample_frames: int,
    threshold: float,
    min_area_ratio: float,
    max_area_ratio: float,
    dilate: int,
    close: int,
    margin_ratio: float,
    canny_low: int,
    canny_high: int,
    fill_boxes: bool,
    box_padding: int,
    box_merge_gap: int,
    keep_position: str,
    keep_largest: bool,
    preview_dir: Path | None = None,
) -> np.ndarray:
    if rects or mask_path:
        cap = open_video(input_path)
        info = get_video_info(cap)
        ok, first_frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError("Cannot read first frame for preview.")

        mask = create_rect_mask(
            width=info.width,
            height=info.height,
            rects=rects,
            mask_path=mask_path,
            expand=dilate,
        )

        boxes = [Box(x=x, y=y, w=w, h=h, area=w * h) for x, y, w, h in rects]
        preview_path, detected_mask_path = preview_paths(input_path, preview_dir)
        save_detection_preview(
            first_frame=first_frame,
            mask=mask,
            boxes=boxes,
            preview_path=preview_path,
            mask_path=detected_mask_path,
        )
        print(f"Saved preview: {preview_path}")
        print(f"Saved mask: {detected_mask_path}")
        print_boxes(boxes)
        return mask

    if auto:
        result = auto_detect_watermark(
            input_path,
            search=search,
            sample_frames=sample_frames,
            threshold=threshold,
            min_area_ratio=min_area_ratio,
            max_area_ratio=max_area_ratio,
            dilate=dilate,
            close=close,
            margin_ratio=margin_ratio,
            canny_low=canny_low,
            canny_high=canny_high,
            fill_boxes=fill_boxes,
            box_padding=box_padding,
            box_merge_gap=box_merge_gap,
            keep_position=keep_position,
            keep_largest=keep_largest,
        )

        preview_path, detected_mask_path = preview_paths(input_path, preview_dir)
        save_detection_preview(
            first_frame=result.first_frame,
            mask=result.mask,
            boxes=result.boxes,
            preview_path=preview_path,
            mask_path=detected_mask_path,
        )
        print(f"Saved preview: {preview_path}")
        print(f"Saved mask: {detected_mask_path}")
        print_boxes(result.boxes)
        return result.mask

    raise RuntimeError("No mask source provided. Use auto detection, --rect, or --mask.")


def cmd_detect(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    result = auto_detect_watermark(
        input_path,
        search=args.search,
        sample_frames=args.sample_frames,
        threshold=args.threshold,
        min_area_ratio=args.min_area_ratio,
        max_area_ratio=args.max_area_ratio,
        dilate=args.dilate,
        close=args.close,
        margin_ratio=args.margin_ratio,
        canny_low=args.canny_low,
        canny_high=args.canny_high,
        fill_boxes=args.fill_boxes,
        box_padding=args.box_padding,
        box_merge_gap=args.box_merge_gap,
        keep_position=args.keep_position,
        keep_largest=args.keep_largest,
    )

    output_dir = Path(args.output_dir) if args.output_dir else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    preview_path, mask_path = preview_paths(input_path, output_dir)
    save_detection_preview(
        first_frame=result.first_frame,
        mask=result.mask,
        boxes=result.boxes,
        preview_path=preview_path,
        mask_path=mask_path,
    )
    print(f"Saved preview: {preview_path}")
    print(f"Saved mask: {mask_path}")
    print_boxes(result.boxes)


def cmd_clean(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_dir = Path(args.preview_dir) if args.preview_dir else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    mask = load_or_build_mask(
        input_path=input_path,
        rects=[parse_rect(v) for v in args.rect],
        mask_path=Path(args.mask) if args.mask else None,
        auto=not args.no_auto,
        search=args.search,
        sample_frames=args.sample_frames,
        threshold=args.threshold,
        min_area_ratio=args.min_area_ratio,
        max_area_ratio=args.max_area_ratio,
        dilate=args.dilate,
        close=args.close,
        margin_ratio=args.margin_ratio,
        canny_low=args.canny_low,
        canny_high=args.canny_high,
        fill_boxes=args.fill_boxes,
        box_padding=args.box_padding,
        box_merge_gap=args.box_merge_gap,
        keep_position=args.keep_position,
        keep_largest=args.keep_largest,
        preview_dir=output_dir,
    )

    process_video(
        input_path=input_path,
        output_path=output_path,
        mask=mask,
        method=args.method,
        radius=args.radius,
        crf=args.crf,
        preset=args.preset,
        audio=args.audio,
        start=args.start,
        end=args.end,
        feather=args.feather,
        blend_strength=args.blend_strength,
        detail_amount=args.detail_amount,
        detail_sigma=args.detail_sigma,
    )
    print(f"Done: {output_path}")


def cmd_batch(args: argparse.Namespace) -> None:
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS)
    if not files:
        raise RuntimeError(f"No video files found in: {input_dir}")

    for input_path in files:
        output_path = output_dir / f"{input_path.stem}_cleaned.mp4"
        print("=" * 80)
        print(f"Input:  {input_path}")
        print(f"Output: {output_path}")

        mask = load_or_build_mask(
            input_path=input_path,
            rects=[parse_rect(v) for v in args.rect],
            mask_path=Path(args.mask) if args.mask else None,
            auto=not args.no_auto,
            search=args.search,
            sample_frames=args.sample_frames,
            threshold=args.threshold,
            min_area_ratio=args.min_area_ratio,
            max_area_ratio=args.max_area_ratio,
            dilate=args.dilate,
            close=args.close,
            margin_ratio=args.margin_ratio,
            canny_low=args.canny_low,
            canny_high=args.canny_high,
            fill_boxes=args.fill_boxes,
            box_padding=args.box_padding,
            box_merge_gap=args.box_merge_gap,
            preview_dir=output_dir,
        )

        process_video(
            input_path=input_path,
            output_path=output_path,
            mask=mask,
            method=args.method,
            radius=args.radius,
            crf=args.crf,
            preset=args.preset,
            audio=args.audio,
            start=args.start,
            end=args.end,
        )


def add_detection_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--search",
        choices=["edges", "corners", "full"],
        default="edges",
        help="Where to search for fixed watermark. Default: edges.",
    )
    parser.add_argument("--sample-frames", type=int, default=80, help="Frames sampled for detection.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.45,
        help="Edge persistence threshold. Lower detects more; higher detects less.",
    )
    parser.add_argument("--min-area-ratio", type=float, default=0.00002)
    parser.add_argument("--max-area-ratio", type=float, default=0.08)
    parser.add_argument("--dilate", type=int, default=9, help="Expand detected mask by pixels.")
    parser.add_argument("--close", type=int, default=21, help="Connect fragmented text/logo strokes.")
    parser.add_argument("--margin-ratio", type=float, default=0.22, help="Border search margin ratio.")
    parser.add_argument("--canny-low", type=int, default=60)
    parser.add_argument("--canny-high", type=int, default=160)
    parser.add_argument(
        "--fill-boxes",
        action="store_true",
        help="Fill merged detected bounding boxes instead of only detected strokes. Useful for translucent rectangular watermark panels.",
    )
    parser.add_argument(
        "--box-padding",
        type=int,
        default=12,
        help="Padding in pixels around filled boxes when --fill-boxes is used.",
    )
    parser.add_argument(
        "--box-merge-gap",
        type=int,
        default=24,
        help="Merge detected boxes within this many pixels when --fill-boxes is used.",
    )
    parser.add_argument(
        "--keep-position",
        choices=["all", "top-left", "top-right", "bottom-left", "bottom-right", "center"],
        default="all",
        help="Only keep detections in this screen region.",
    )
    parser.add_argument(
        "--keep-largest",
        action="store_true",
        help="Only keep the largest detected area after position filtering.",
    )


def add_clean_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--rect",
        action="append",
        default=[],
        help="Manual watermark rectangle x,y,w,h. Can be used multiple times.",
    )
    parser.add_argument("--mask", default=None, help="White-on-black mask image. White area is repaired.")
    parser.add_argument("--no-auto", action="store_true", help="Disable auto detection.")
    parser.add_argument("--method", choices=["telea", "ns"], default="telea")
    parser.add_argument("--radius", type=float, default=3, help="Inpaint radius. Try 3-7.")
    parser.add_argument("--crf", type=int, default=18, help="Video quality. Lower is better/larger.")
    parser.add_argument(
        "--preset",
        choices=[
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ],
        default="medium",
    )
    parser.add_argument("--audio", choices=["copy", "aac", "none"], default="copy")
    parser.add_argument("--start", type=float, default=0.0, help="Start time in seconds.")
    parser.add_argument("--end", type=float, default=None, help="End time in seconds.")
    parser.add_argument("--feather", type=int, default=8, help="Soft edge size. Try 4-12.")
    parser.add_argument("--blend-strength", type=float, default=0.78, help="0.6-0.9 looks less cut-out than 1.0.")
    parser.add_argument("--detail-amount", type=float, default=0.16, help="Add original fine texture back. Try 0.08-0.25.")
    parser.add_argument("--detail-sigma", type=float, default=2.0, help="Texture scale for detail restoration.")
    parser.add_argument("--preview-dir", default=None, help="Directory for preview and mask outputs.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ownmark-cleaner",
        description="Local video inpainting CLI for your own fixed watermarks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect_parser = subparsers.add_parser("detect", help="Auto-detect fixed watermark and save preview/mask.")
    detect_parser.add_argument("input", help="Input video path.")
    detect_parser.add_argument("--output-dir", default=None, help="Where to save preview/mask.")
    add_detection_options(detect_parser)
    detect_parser.set_defaults(func=cmd_detect)

    clean_parser = subparsers.add_parser("clean", help="Detect or load mask, then repair video.")
    clean_parser.add_argument("input", help="Input video path.")
    clean_parser.add_argument("output", help="Output video path.")
    add_detection_options(clean_parser)
    add_clean_options(clean_parser)
    clean_parser.set_defaults(func=cmd_clean)

    batch_parser = subparsers.add_parser("batch", help="Batch process all videos in a folder.")
    batch_parser.add_argument("input_dir", help="Input folder.")
    batch_parser.add_argument("output_dir", help="Output folder.")
    add_detection_options(batch_parser)
    add_clean_options(batch_parser)
    batch_parser.set_defaults(func=cmd_batch)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
