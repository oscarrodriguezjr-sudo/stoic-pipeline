"""
scenes.json['scenes'][i]['overlay'] -> videos/<id>/overlays/<key>.png

1920x1080 transparent PNGs per the table in CLAUDE.md Section 7. Every text
element gets a soft drop shadow (Gaussian blur ~6px, black @ alpha 200).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080


def _font(path: str, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(path, size)
    if weight is not None:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass  # non-variable font fallback build — fine, just uses its default weight
    return f


def _shadow_and_text(base: Image.Image, xy, text: str, font, fill, anchor="la", align="left", blur=6, alpha=200):
    """Draw a soft drop shadow, then the text itself, onto `base` (RGBA)."""
    shadow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(shadow_layer)
    d.text((xy[0] + 3, xy[1] + 3), text, font=font, fill=(0, 0, 0, alpha), anchor=anchor, align=align)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(shadow_layer)
    ImageDraw.Draw(base).text(xy, text, font=font, fill=fill, anchor=anchor, align=align)


def _veil(base: Image.Image, alpha: int):
    veil = Image.new("RGBA", base.size, (0, 0, 0, alpha))
    base.alpha_composite(veil)


def _gradient_bottom(base: Image.Image, height=340, max_alpha=170):
    grad = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(grad)
    for i in range(height):
        a = int(max_alpha * (i / height))
        d.line([(0, H - height + i), (W, H - height + i)], fill=(0, 0, 0, a))
    base.alpha_composite(grad)


def build_overlay(scene: dict, channel_cfg: dict, style_cfg: dict) -> Image.Image:
    overlay = scene["overlay"]
    otype = overlay["type"]
    gold = tuple(channel_cfg["colors"]["gold"]) + (255,)
    ivory = tuple(channel_cfg["colors"]["ivory"]) + (255,)
    label_font_path = channel_cfg["fonts"]["label"]
    quote_font_path = channel_cfg["fonts"]["quote"]
    sizes = style_cfg["overlay"]["font_sizes"]

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    if otype in ("caption", "capend"):
        _gradient_bottom(img)
        f = _font(label_font_path, sizes["caption"], 650)
        _shadow_and_text(img, (90, H - 140), overlay["text"].upper(), f, gold, anchor="ls")
        d = ImageDraw.Draw(img)
        w = d.textlength(overlay["text"].upper(), font=f)
        d.line([(92, H - 120), (92 + w, H - 120)], fill=gold, width=3)

    elif otype == "titlecard":
        _veil(img, style_cfg["overlay"]["veil_alpha"]["titlecard"])
        f_main = _font(label_font_path, sizes["titlecard_main"], 700)
        f_sub = _font(quote_font_path, sizes["titlecard_sub"], 500)
        _shadow_and_text(img, (W // 2, H // 2 - 40), overlay["line1"], f_main, gold, anchor="mm", align="center")
        _shadow_and_text(img, (W // 2, H // 2 + 90), overlay["line2"], f_sub, ivory, anchor="mm", align="center")

    elif otype == "title":
        _veil(img, style_cfg["overlay"]["veil_alpha"]["title"])
        f_label = _font(label_font_path, sizes["title_label"], 700)
        f_text = _font(quote_font_path, sizes["title_text"], 500)
        _shadow_and_text(img, (W // 2, H // 2 - 70), overlay["label"], f_label, gold, anchor="mm", align="center")
        _shadow_and_text(img, (W // 2, H // 2 + 40), overlay["text"], f_text, ivory, anchor="mm", align="center")

    elif otype == "quote":
        _veil(img, style_cfg["overlay"]["veil_alpha"]["quote"])
        f_line = _font(quote_font_path, sizes["quote_line"], 500)
        f_author = _font(label_font_path, sizes["quote_author"], 700)
        lines = overlay["lines"]
        total_h = len(lines) * (sizes["quote_line"] + 20)
        start_y = H // 2 - total_h // 2
        for i, line in enumerate(lines):
            _shadow_and_text(img, (W // 2, start_y + i * (sizes["quote_line"] + 20)), line, f_line, ivory, anchor="mm", align="center")
        _shadow_and_text(img, (W // 2, start_y + total_h + 30), f"— {overlay['author'].upper()}", f_author, gold, anchor="mm", align="center")

    elif otype == "takeaway":
        _gradient_bottom(img, height=300)
        f = _font(quote_font_path, sizes["takeaway"], 500)
        _shadow_and_text(img, (W // 2, H - 150), overlay["text"], f, ivory, anchor="mm", align="center")
        d = ImageDraw.Draw(img)
        w = d.textlength(overlay["text"], font=f)
        d.line([(W // 2 - w // 4, H - 100), (W // 2 + w // 4, H - 100)], fill=gold, width=2)

    elif otype == "center":
        _veil(img, 120)
        f = _font(quote_font_path, sizes["takeaway"], 500)
        lines = overlay.get("lines") or [overlay.get("text", "")]
        total_h = len(lines) * (sizes["takeaway"] + 24)
        start_y = H // 2 - total_h // 2
        for i, line in enumerate(lines):
            _shadow_and_text(img, (W // 2, start_y + i * (sizes["takeaway"] + 24)), line, f, ivory, anchor="mm", align="center")

    elif otype == "sub":
        _gradient_bottom(img, height=260)
        f1 = _font(label_font_path, 56, 700)
        f2 = _font(quote_font_path, 44, 500)
        _shadow_and_text(img, (W // 2, H - 150), overlay.get("text", "SUBSCRIBE"), f1, gold, anchor="mm", align="center")
        if overlay.get("channel_name"):
            _shadow_and_text(img, (W // 2, H - 90), overlay["channel_name"], f2, ivory, anchor="mm", align="center")

    else:
        raise ValueError(f"Unknown overlay type: {otype}")

    return img


def generate_overlays(scenes: dict, video_dir: Path, channel_cfg: dict, style_cfg: dict) -> dict[str, Path]:
    out_dir = video_dir / "overlays"
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    for scene in scenes["scenes"]:
        key = scene["key"]
        out_path = out_dir / f"{key}.png"
        if not out_path.exists():
            img = build_overlay(scene, channel_cfg, style_cfg)
            img.save(out_path)
            print(f"[overlays] {key}: -> {out_path}")
        result[key] = out_path
    return result
