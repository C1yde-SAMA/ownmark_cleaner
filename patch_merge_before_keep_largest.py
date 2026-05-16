from pathlib import Path

p = Path("src/ownmark_cleaner/detection.py")
s = p.read_text()

old = '''    boxes = filter_boxes_by_position(
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

    if np.count_nonzero(final_mask) == 0:
'''

new = '''    if fill_boxes:
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
'''

if old not in s:
    raise SystemExit("Patch target not found. Open src/ownmark_cleaner/detection.py and check whether it was already changed.")

p.write_text(s.replace(old, new))
print("patched: merge boxes before keep-largest")
