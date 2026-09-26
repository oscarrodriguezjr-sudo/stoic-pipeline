"""
Builds title/description/tags/chapters from the scene list and each
segment's actual rendered duration (read via ffprobe, not guessed) so
chapter timestamps in the YouTube description are always correct.
CLAUDE.md Section 9.
"""
from __future__ import annotations

import json
from pathlib import Path

from .render import _ffprobe_duration


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _chapter_label(scene: dict) -> str | None:
    ov = scene["overlay"]
    if ov["type"] == "titlecard":
        return "Intro"
    if ov["type"] == "title":
        return f"{ov['label']}: {ov['text']}"
    return None


def build_metadata(
    scenes: dict,
    segment_paths: list[Path],
    channel_cfg: dict,
    out_path: Path,
) -> dict:
    cursor = 0.0
    chapters = [(0, "Intro")]  # YouTube requires the first chapter to start at 0:00
    for scene, seg_path in zip(scenes["scenes"], segment_paths):
        label = _chapter_label(scene)
        if label and cursor > 0:
            chapters.append((cursor, label))
        cursor += _ffprobe_duration(seg_path)

    chapter_lines = "\n".join(f"{_fmt_ts(t)} {label}" for t, label in chapters)

    title = scenes["title"]
    if len(title) > 60:
        print(f"[metadata] WARNING: title is {len(title)} chars, over the 60-char SEO target")

    description = (
        f"{title}\n\n"
        f"{channel_cfg['name']} turns ancient Stoic philosophy into practical rules for "
        f"leaders and founders today.\n\n"
        f"CHAPTERS\n{chapter_lines}\n\n"
        f"Which rule are you practicing this week? Tell me in the comments.\n\n"
        f"Subscribe to {channel_cfg['name']} for more.\n"
    )

    tags = [
        "stoicism", "stoic philosophy", "marcus aurelius", "seneca", "epictetus",
        "stoic leadership", "mental toughness", "leadership advice", "meditations",
        "ancient wisdom", "calm under pressure", "executive coaching",
    ]
    hashtags = ["#Stoicism", "#MarcusAurelius", "#Leadership"]

    meta = {
        "title": title,
        "description": description,
        "tags": tags[:15],
        "hashtags": hashtags,
        "chapters": [{"start_seconds": t, "label": label} for t, label in chapters],
        "privacyStatus": "private",  # CLAUDE.md Section 11 — always upload private for manual review
    }
    out_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[metadata] -> {out_path}")
    return meta
