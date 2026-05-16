from pathlib import Path

# Patch webapp.py
p = Path("webapp.py")
s = p.read_text()

s = s.replace(
'''    audio: str = "copy",
) -> None:''',
'''    audio: str = "copy",
    blur_kernel: int | None = None,
    blur_strength: float | None = None,
) -> None:'''
)

s = s.replace(
'''    preset = get_preset(preset_name)''',
'''    preset = dict(get_preset(preset_name))

    if blur_kernel is not None:
        blur_kernel = int(blur_kernel)
        if blur_kernel < 1:
            blur_kernel = 1
        if blur_kernel % 2 == 0:
            blur_kernel += 1
        preset["blur_kernel"] = blur_kernel

    if blur_strength is not None:
        blur_strength = float(blur_strength)
        blur_strength = max(0.0, min(1.0, blur_strength))
        preset["blur_strength"] = blur_strength'''
)

s = s.replace(
'''        if preset_name not in ["fine", "normal", "strong"]:
            preset_name = "fine"''',
'''        if preset_name not in ["fine", "normal", "strong"]:
            preset_name = "fine"

        blur_kernel = int(data.get("blur_kernel", 7))
        blur_strength = float(data.get("blur_strength", 0.16))'''
)

s = s.replace(
'''            preset_codec="medium",
            audio="copy",
        )''',
'''            preset_codec="medium",
            audio="copy",
            blur_kernel=blur_kernel,
            blur_strength=blur_strength,
        )'''
)

p.write_text(s)


# Patch templates/index.html
p = Path("templates/index.html")
s = p.read_text()

s = s.replace(
'''    <label>
      处理模式：
      <select id="presetName">
        <option value="fine" selected>细腻</option>
        <option value="normal">标准</option>
        <option value="strong">强力</option>
      </select>
    </label>''',
'''    <label>
      处理模式：
      <select id="presetName">
        <option value="fine" selected>细腻</option>
        <option value="normal">标准</option>
        <option value="strong">强力</option>
      </select>
    </label>

    <lanel">
        <option value="3">3 很轻</option>
        <option value="5">5 轻微</option>
        <option value="7" selected>7 推荐</option>
        <option value="9">9 稍强</option>
        <option value="11">11 强</option>
        <option value="15">15 很强</option>
      </select>
    </label>

    <label>
      高斯模糊强度：
      <select id="blurStrength">
        <option value="0">0 不模糊</option>
        <option value="0.08">0.08 很轻</option>
        <option value="0.16" selected>0.16 推荐</option>
        <option value="0.24">0.24 稍强</option>
        <option value="0.32">0.32 强</option>
        <option value="0.45">0.45 很强</option>
      </select>
    </label>'''
)

s = s.replace(
'''    split_count: Number(document.getElementById("splitCount").value),
    preset_name: document.getElementById("presetName").value
  };''',
'''    split_count: Number(document.getElementById("splitCount").value),
    preset_name: document.getElementById("presetName").value,
    blur,
    blur_strength: Number(document.getElementById("blurStrength").value)
  };'''
)

p.write_text(s)

print("patched blur controls")
