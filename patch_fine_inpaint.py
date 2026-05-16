from pathlib import Path

# -----------------------------
# 1) Patch src/ownmark_cleaner/inpaint.py
# -----------------------------
p = Path("src/ownmark_cleaner/inpaint.py")
s = p.read_text()

if "def build_soft_alpha(" not in s:
    s = s.replace(
        "\n\ndef process_video(\n",
        '''

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
'''
    )

s = s.replace(
    '''    audio: str = "copy",
    start: float = 0.0,
    end: float | None = None,
) -> None:''',
    '''    audio: str = "copy",
    start: float = 0.0,
    end: float | None = None,
    feather: int = 8,
    blend_strength: float = 0.78,
    detail_amount: float = 0.16,
    detail_sigma: float = 2.0,
) -> None:'''
)

s = s.replace(
    '''                if should_inpaint:
                    frame = cv2.inpaint(frame, mask, radius, flag)

                if proc.stdin is None:''',
    '''                if should_inpaint:
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

                if proc.stdin is None:'''
)

p.write_text(s)


# -----------------------------
# 2) Patch src/ownmark_cleaner/cli.py
# -----------------------------
p = Path("src/ownmark_cleaner/cli.py")
s = p.read_text()

if "--feather" not in s:
    s = s.replace(
        '''    parser.add_argument("--end", type=float, default=None, help="End time in seconds.")
    parser.add_argument("--preview-dir", default=None, help="Directory for preview and mask outputs.")
''',
        '''    parser.add_argument("--end", type=float, default=None, help="End time in seconds.")
    parser.add_argument("--feather", type=int, default=8, help="Soft edge size. Try 4-12.")
    parser.add_argument("--blend-strength", type=float, default=0.78, help="0.6-0.9 looks less cut-out than 1.0.")
    parser.add_argument("--detail-amount", type=float, default=0.16, help="Add original fine texture back. Try 0.08-0.25.")
    parser.add_argument("--detail-sigma", type=float, default=2.0, help="Texture scale for detail restoration.")
    parser.add_argument("--preview-dir", default=None, help="Directory for preview and mask outputs.")
'''
    )

s = s.replace(
    '''        end=args.end,
    )''',
    '''        end=args.end,
        feather=args.feather,
        blend_strength=args.blend_strength,
        detail_amount=args.detail_amount,
        detail_sigma=args.detail_sigma,
    )'''
)

p.write_text(s)


# -----------------------------
# 3) Patch webapp.py, if it exists
# -----------------------------
p = Path("webapp.py")

if p.exists():
    s = p.read_text()

    if "feather = int(data.get" not in s:
        s = s.replace(
            '''    audio = data.get("audio", "copy")

    mask = create_rect_mask(''',
            '''    audio = data.get("audio", "copy")

    feather = int(data.get("feather", 8))
    blend_strength = float(data.get("blend_strength", 0.78))
    detail_amount = float(data.get("detail_amount", 0.16))
    detail_sigma = float(data.get("detail_sigma", 2.0))

    mask = create_rect_mask('''
        )

    s = s.replace(
        '''        start=0.0,
        end=None,
    )''',
        '''        start=0.0,
        end=None,
        feather=feather,
        blend_strength=blend_strength,
        detail_amount=detail_amount,
        detail_sigma=detail_sigma,
    )'''
    )

    p.write_text(s)


# -----------------------------
# 4) Patch templates/index.html, if it exists
# -----------------------------
p = Path("templates/index.html")

if p.exists():
    s = p.read_text()

    if 'id="feather"' not in s:
        s = s.replace(
            '''    <label>
      audio:
      <select id="audio">
        <option value="copy" selected>copy</option>
        <option value="aac">aac</option>
        <option value="none">none</option>
      </select>
    </label>
''',
            '''    <label>
      audio:
      <select id="audio">
        <option value="copy" selected>copy</option>
        <option value="aac">aac</option>
        <option value="none">none</option>
      </select>
    </label>

    <label>
      feather:
      <input id="feather" type="number" value="8" min="0" max="40" />
    </label>

    <label>
      blend:
      <input id="blendStrength" type="number" value="0.78" min="0.1" max="1" step="0.01" />
    </label>

    <label>
      detail:
      <input id="detailAmount" type="number" value="0.16" min="0" max="1" step="0.01" />
    </label>

    <label>
      detail sigma:
      <input id="detailSigma" type="number" value="2.0" min="0.5" max="10" step="0.5" />
    </label>
'''
        )

    s = s.replace(
        '''    audio: document.getElementById("audio").value
  };''',
        '''    audio: document.getElementById("audio").value,
    feather: Number(document.getElementById("feather").value),
    blend_strength: Number(document.getElementById("blendStrength").value),
    detail_amount: Number(document.getElementById("detailAmount").value),
    detail_sigma: Number(document.getElementById("detailSigma").value)
  };'''
    )

    p.write_text(s)

print("patched fine inpaint mode")
