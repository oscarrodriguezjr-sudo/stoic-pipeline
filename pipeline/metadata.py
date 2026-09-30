"""
Builds title/description/tags/chapters from the scene list and each
segment's actual rendered duration (read via ffprobe, not guessed) so
chapter timestamps in the YouTube description are always correct.
CLAUDE.md Section 9.

SEO fix (2026-09-29 — see chat with Oscar re: video/channel ranking):
tags, hashtags and the description boilerplate used to be 100% identical
on every single upload regardless of topic or channel language. That gave
each video zero topic-specific keyword coverage and put an English
description under every Spanish (es) video. This version derives
per-topic keywords from the video's slug (e.g. "calm-under-pressure" ->
"calm under pressure", "calm", "under", "pressure") and writes the
description/CTA in the channel's own language.
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


# Words too generic to be useful as their own tag, per slug language.
_STOPWORDS = {
    "en": {"a", "an", "the", "to", "of", "and", "or", "for", "on", "in", "at",
           "is", "are", "you", "your", "how", "why", "never", "when"},
    "es": {"el", "la", "los", "las", "un", "una", "de", "del", "y", "o",
           "para", "por", "en", "que", "tu", "su", "sus", "con", "sin"},
}

# Base (channel-language) keyword set — used to round out every video's
# tags/hashtags after the topic-specific ones, so search coverage isn't
# lost for a topic whose slug happens to be short.
_BASE_TAGS = {
    "en": ["stoicism", "stoic philosophy", "marcus aurelius", "seneca", "epictetus",
           "stoic leadership", "mental toughness", "leadership advice", "meditations",
           "ancient wisdom", "executive coaching"],
    "es": ["estoicismo", "filosofía estoica", "marco aurelio", "séneca", "epicteto",
           "liderazgo estoico", "fortaleza mental", "consejos de liderazgo",
           "meditaciones", "sabiduría antigua", "coaching ejecutivo"],
}

_BASE_HASHTAGS = {
    "en": ["#Stoicism", "#Leadership"],
    "es": ["#Estoicismo", "#Liderazgo"],
}


def _slug_keywords(video_id: str, language: str) -> tuple[list[str], str]:
    """Turn a slug like 'calm-under-pressure' into (['calm', 'under',
    'pressure', 'calm under pressure'], 'calm under pressure')."""
    words = [w for w in video_id.split("-") if w]
    if not words:
        return [], ""
    phrase = " ".join(words)
    stop = _STOPWORDS.get(language, set())
    single_words = [w for w in words if w.lower() not in stop and len(w) > 2]
    # Longest/most specific candidate first: the full phrase ranks best for
    # search relevance, then the individual words fill in long-tail matches.
    return [phrase] + single_words, phrase


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        key = item.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def build_metadata(
    scenes: dict,
    segment_paths: list[Path],
    channel_cfg: dict,
    out_path: Path,
    video_id: str = "",
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

    language = channel_cfg.get("language", "en")
    topic_keywords, topic_phrase = _slug_keywords(video_id, language)

    # --- tags: topic-specific first (strongest relevance signal), then the
    # channel's base keyword set, deduped and capped at 15 (YouTube's
    # practical tag-count sweet spot; well under its 500-char total limit
    # given how short these are).
    tags = _dedupe(topic_keywords + _BASE_TAGS.get(language, _BASE_TAGS["en"]))[:15]

    # --- hashtags: YouTube reads hashtags out of the title+description text
    # itself (there's no separate API field), and shows the first 3 it finds
    # above the title. Build one topic-specific hashtag from the slug plus
    # two base ones, then actually put them in the description below.
    topic_hashtag = "#" + "".join(w.capitalize() for w in topic_keywords[1:]) if len(topic_keywords) > 1 else ""
    hashtags = _dedupe(([topic_hashtag] if topic_hashtag else []) + _BASE_HASHTAGS.get(language, _BASE_HASHTAGS["en"]))[:3]

    if language == "es":
        intro = (
            f"{channel_cfg['name']} convierte la filosofía estoica antigua en reglas "
            f"prácticas para líderes y fundadores de hoy"
        )
        topic_line = f". Tema: {topic_phrase}." if topic_phrase else "."
        chapters_label = "CAPÍTULOS"
        cta_comment = "¿Qué regla vas a practicar esta semana? Cuéntamelo en los comentarios."
        cta_subscribe = f"Suscríbete a {channel_cfg['name']} para más."
    else:
        intro = (
            f"{channel_cfg['name']} turns ancient Stoic philosophy into practical rules "
            f"for leaders and founders today"
        )
        topic_line = f". Topic: {topic_phrase}." if topic_phrase else "."
        chapters_label = "CHAPTERS"
        cta_comment = "Which rule are you practicing this week? Tell me in the comments."
        cta_subscribe = f"Subscribe to {channel_cfg['name']} for more."

    description = (
        f"{title}\n\n"
        f"{intro}{topic_line}\n\n"
        f"{chapters_label}\n{chapter_lines}\n\n"
        f"{cta_comment}\n\n"
        f"{cta_subscribe}\n\n"
        f"{' '.join(hashtags)}\n"
    )

    meta = {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
        "categoryId": "27",  # Education — better algorithmic fit than the default (22, People & Blogs)
        "chapters": [{"start_seconds": t, "label": label} for t, label in chapters],
    }
    out_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[metadata] -> {out_path}")
    return meta
