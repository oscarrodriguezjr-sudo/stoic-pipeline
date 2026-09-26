"""
Best scene image + bold Cinzel text -> videos/<id>/thumbnail.png (1280x720),
two variants for A/B testing. CLAUDE.md Section 9.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720


def _font(path: str, size: int, weight: int = 700) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(path, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def make_thumbnail(source_image: Path, text: str, channel_cfg: dict, out_path: Path, veil_alpha: int = 130) -> Path:
    im = Image.open(source_image).convert("RGB").resize((W, H), Image.LANCZOS)
    im = im.convert("RGBA")

    veil = Image.new("RGBA", im.size, (0, 0, 0, veil_alpha))
    im.alpha_composite(veil)

    gold = tuple(channel_cfg["colors"]["gold"]) + (255,)
    font = _font(channel_cfg["fonts"]["label"], 96, 700)

    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((W // 2, H // 2), text.upper(), font=font, fill=(0, 0, 0, 220), anchor="mm", align="center")
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    im.alpha_composite(shadow)
    ImageDraw.Draw(im).text((W // 2, H // 2), text.upper(), font=font, fill=gold, anchor="mm", align="center")

    im.convert("RGB").save(out_path, quality=95)
    return out_path


def make_variants(source_image: Path, text: str, channel_cfg: dict, video_dir: Path) -> list[Path]:
    out1 = make_thumbnail(source_image, text, channel_cfg, video_dir / "thumbnail_a.png", veil_alpha=130)
    out2 = make_thumbnail(source_image, text, channel_cfg, video_dir / "thumbnail_b.png", veil_alpha=90)
    return [out1, out2]
