from pathlib import Path

detection = Path("src/ownmark_cleaner/detection.py")
cli = Path("src/ownmark_cleaner/cli.py")

s = detection.read_text()

if "def filter_boxes_by_position(" not in s:
    s = s.replace(
        "def mask_from_boxes(width: int, height: int, boxes: list[Box], *, padding: int = 0) -> np.ndarray:",
        """
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
"""
    )

s = s.replace(
    """    fill_boxes: bool = False,
    box_padding: int = 12,
    box_merge_gap: int = 24,
) -> DetectionResult:""",
    """    fill_boxes: bool = False,
    box_padding: int = 12,
    box_merge_gap: int = 24,
    keep_position: str = "all",
    keep_largest: bool = False,
) -> DetectionResult:""",
)

s = s.replace(
    """    if fill_boxes and boxes:
        boxes = merge_nearby_boxes(boxes, gap=max(0, box_merge_gap), width=info.width, height=info.height)
        final_mask = mask_from_boxes(info.width, info.height, boxes, padding=max(0, box_padding))
    else:
        final_mask = component_mask

    if np.count_nonzero(final_mask) == 0:""",
    """    boxes = filter_boxes_by_position(
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

    if fill_boxes:
        boxes = merge_nearby_boxes(boxes, gap=max(0, box_merge_gap), width=info.width, height=info.height)
        boxes = filter_boxes_by_position(
            boxes,
            width=info.width,
            height=info.height,
            position=keep_position,
            keep_largest=keep_largest,
        )
        final_mask = mask_from_boxes(info.width, info.height, boxes, padding=max(0, box_padding))
    else:
        final_mask = np.zeros_like(component_mask)
        for box in boxes:
            final_mask[
                max(0, box.y):min(info.height, box.y + box.h),
                max(0, box.x):min(info.width, box.x + box.w),
            ] = component_mask[
                max(0, box.y):min(info.height, box.y + box.h),
                max(0, box.x):min(info.width, box.x + box.w),
            ]

    if np.count_nonzero(final_mask) == 0:""",
)

detection.write_text(s)


s = cli.read_text()

s = s.replace(
    """    box_merge_gap: int,
    preview_dir: Path | None = None,
) -> np.ndarray:""",
    """    box_merge_gap: int,
    keep_position: str,
    keep_largest: bool,
    preview_dir: Path | None = None,
) -> np.ndarray:""",
)

s = s.replace(
    """            box_padding=box_padding,
            box_merge_gap=box_merge_gap,
        )""",
    """            box_padding=box_padding,
            box_merge_gap=box_merge_gap,
            keep_position=keep_position,
            keep_largest=keep_largest,
        )""",
)

s = s.replace(
    """        box_padding=args.box_padding,
        box_merge_gap=args.box_merge_gap,
    )""",
    """        box_padding=args.box_padding,
        box_merge_gap=args.box_merge_gap,
        keep_position=args.keep_position,
        keep_largest=args.keep_largest,
    )""",
)

s = s.replace(
    """        box_padding=args.box_padding,
        box_merge_gap=args.box_merge_gap,
        preview_dir=output_dir,
    )""",
    """        box_padding=args.box_padding,
        box_merge_gap=args.box_merge_gap,
        keep_position=args.keep_position,
        keep_largest=args.keep_largest,
        preview_dir=output_dir,
    )""",
)

if "--keep-position" not in s:
    s = s.replace(
        """    parser.add_argument(
        "--box-merge-gap",
        type=int,
        default=24,
        help="Merge detected boxes within this many pixels when --fill-boxes is used.",
    )
""",
        """    parser.add_argument(
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
""",
    )

cli.write_text(s)

print("patched")
