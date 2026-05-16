from pathlib import Path

p = Path("webapp.py")
s = p.read_text()

# 1. 给 preset 增加 blur 参数
s = s.replace(
'''        "fine": {
            "radius": 1.5,
            "feather": 10,
            "blend_strength": 0.72,
            "detail_amount": 0.20,
            "detail_sigma": 2.0,
        },
        "normal": {
            "radius": 2.0,
            "feather": 8,
            "blend_strength": 0.82,
            "detail_amount": 0.14,
            "detail_sigma": 2.0,
        },
        "strong": {
            "radius": 2.6,
            "feather": 6,
            "blend_strength": 0.95,
            "detail_amount": 0.10,
            "detail_sigma": 2.0,
        },''',
'''        "fine": {
            "radius": 1.5,
            "feather": 10,
            "blend_strength": 0.72,
            "detail_amount": 0.20,
            "detail_sigma": 2.0,
            "blur_kernel": 7,
            "blur_strength": 0.16,
            "blur_feather": 10,
        },
   al": {
            "radius": 2.0,
            "feather": 8,
            "blend_strength": 0.82,
            "detail_amount": 0.14,
            "detail_sigma": 2.0,
            "blur_kernel": 9,
            "blur_strength": 0.22,
            "blur_feather": 10,
        },
        "strong": {
            "radius": 2.6,
            "feather": 6,
            "blend_strength": 0.95,
            "detail_amount": 0.10,
            "detail_sigma": 2.0,
            "blur_kernel": 11,
            "blur_strength": 0.30,
            "blur_feather": 12,
        },'''
)

# 2. 加高斯模糊函数
s = s.replace(
'''def process_frame_tiled(
    frame: np.ndarray,
    rects: list[tuple[int, int, int, int]],
    split_count: int,
    preset: dict,
) -> np.ndarray:''',
'''def build_region_mask(
    frame_shape: tuple[int, int, int],
    rects: list[tuple[int, int, int, int]],
) -> np.ndarray:
    h, w = frame_shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)

    for x, y, rw, rh in rects:
        x1 = max(0, int(x))
   0, int(y))
        x2 = min(w, int(x + rw))
        y2 = min(h, int(y + rh))

        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = 255

    return mask


def apply_gaussian_blur_to_regions(
    frame: np.ndarray,
    rects: list[tuple[int, int, int, int]],
    preset: dict,
) -> np.ndarray:
    blur_kernel = int(preset.get("blur_kernel", 7))
    blur_strength = float(preset.get("blur_strength", 0.16))
    blur_feather = int(preset.get("blur_feather", 10))

    if blur_kernel <= 1 or blur_strength <= 0:
        return frame

    if blur_kernel % 2 == 0:
        blur_kernel += 1

    mask = build_region_mask(frame.shape, rects)

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
) -> np.ndarray:'''
)

# 3. 在 process_frame_tiled 最后返回前加模糊
s = s.replace(
'''    return working''',
'''    working = apply_gaussian_blur_to_regions(
        frame=working,
        rects=rects,
        preset=preset,
    )

    return working''',
    1
)

p.write_text(s)
print("patched gaussian blur")
