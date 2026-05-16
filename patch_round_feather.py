from pathlib import Path

p = Path("webapp.py")
s = p.read_text()

old_build_region_mask = r'''def build_region_mask(
    frame_shape: tuple[int, int, int],
    rects: list[tuple[int, int, int, int]],
    expand: int = 0,
) -> np.ndarray:
    h, w = frame_shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)

    for x, y, rw, rh in rects:
        x1 = max(0, int(x) - expand)
        y1 = max(0, int(y) - expand)
        x2 = min(w, int(x + rw) + expand)
        y2 = min(h, int(y + rh) + expand)

        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = 255

    return mask
'''

new_build_region_mask = r'''def draw_rounded_rect(
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
'''

if old_build_region_mask not in s:
    raise SystemExit("build_region_mask block not found")

s = s.replace(old_build_region_mask, new_build_region_mask)


# Add corner_radius and edge feather presets
s = s.replace(
'''"blur_feather": 8,
            "tile_expand": 1,''',
'''"blur_feather": 18,
            "corner_radius": 22,
            "tile_expand": 1,''',
)

s = s.replace(
'''"blur_feather": 8,
            "tile_expand": 3,''',
'''"blur_feather": 20,
            "corner_radius": 26,
            "tile_expand": 3,''',
)

s = s.replace(
'''"blur_feather": 10,
            "tile_expand": 6,''',
'''"blur_feather": 24,
            "corner_radius": 32,
            "tile_expand": 6,''',
)


old_apply_mask_line = r'''    mask = build_region_mask(frame.shape, rects, expand=tile_expand)'''

new_apply_mask_line = r'''    corner_radius = int(preset.get("corner_radius", 24))

    mask = build_region_mask(
        frame.shape,
        rects,
        expand=tile_expand,
        corner_radius=corner_radius,
    )'''

if old_apply_mask_line not in s:
    raise SystemExit("apply_gaussian_blur_to_regions mask line not found")

s = s.replace(old_apply_mask_line, new_apply_mask_line)


# Make tile masks also slightly feathered but not rounded, to avoid inner tile hard edges
old_tile_alpha = r'''            alpha = build_soft_alpha(
                mask,
                feather=preset["feather"],
                blend_strength=preset["blend_strength"],
            )'''

new_tile_alpha = r'''            alpha = build_soft_alpha(
                mask,
                feather=preset["feather"],
                blend_strength=preset["blend_strength"],
            )'''

# no-op placeholder, kept for safety
s = s.replace(old_tile_alpha, new_tile_alpha)

p.write_text(s)
print("patched rounded corners + feathered edge")
