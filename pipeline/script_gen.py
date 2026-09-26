"""
topic (+ channel) -> scenes.json, via the Anthropic API. CLAUDE.md Section 5.

Needs ANTHROPIC_API_KEY in .env (a plain Anthropic API key from
console.anthropic.com — separate from any Claude subscription/session).

Model id: set ANTHROPIC_MODEL in .env if the default below 404s — model
names change; check https://docs.claude.com/en/docs/about-claude/models
for the current list rather than guessing.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
MAX_NARRATION_CHARS = 1000
IMAGE_PROMPT_SUFFIX = (
    "Cinematic painting, epic historical film still, ancient Rome, warm amber "
    "light against deep shadows, rich detail, no text, no letters, no watermark."
)

PERSONAL_STORY_MARKERS = ["[PERSONAL STORY]", "[HISTORIA PERSONAL]", "[Espacio para historia personal"]


class SceneModel(BaseModel):
    key: str
    image: str
    zoom: Literal["in", "out", "in2"]
    overlay: dict
    narration: str = Field(max_length=MAX_NARRATION_CHARS)

    @field_validator("overlay")
    @classmethod
    def _valid_overlay_type(cls, v: dict) -> dict:
        allowed = {"caption", "capend", "titlecard", "title", "quote", "takeaway", "center", "sub"}
        if v.get("type") not in allowed:
            raise ValueError(f"overlay.type must be one of {allowed}, got {v.get('type')!r}")
        return v


class ScriptModel(BaseModel):
    title: str
    channel: Literal["en", "es"]
    scenes: list[SceneModel]
    images: dict[str, str]

    @field_validator("scenes")
    @classmethod
    def _images_exist(cls, scenes, info):
        # cross-field validation happens after the model is built; see generate_scenes()
        return scenes


SYSTEM_PROMPT = """You write scripts for a faceless YouTube channel about Stoic philosophy \
for leaders and founders, output as strict JSON matching an exact schema. Follow every rule \
below precisely — this JSON feeds an automated video pipeline with no human editing pass \
before rendering.

SCHEMA (respond with ONLY this JSON object, no markdown fences, no commentary before or after):
{
  "title": "<video title, under 60 characters>",
  "channel": "<'en' or 'es', as given>",
  "images": {"<image-key>": "<English visual description ending with the cinematic suffix>", ...},
  "scenes": [
    {"key": "<unique short id>", "image": "<one of the images keys above>", "zoom": "in|out|in2",
     "overlay": {"type": "caption|capend|titlecard|title|quote|takeaway|center|sub", ...type-specific fields...},
     "narration": "<spoken line(s), under 1000 characters>"}
  ]
}

Overlay type fields:
- caption / capend: {"text": "<short scene-setting caption>"}
- titlecard: {"line1": "<big line>", "line2": "<subtitle>"}
- title: {"label": "RULE N" (or "REGLA N" in Spanish), "text": "<short rule title>"}
- quote: {"lines": ["<line 1>", "<line 2>"], "author": "<name>"}
- takeaway: {"text": "<short one-line takeaway>"}
- center: {"lines": ["<closing line 1>", "<closing line 2>"]}
- sub: {"text": "SUBSCRIBE" (or "SUSCRÍBETE"), "channel_name": "<channel name>"}

STRUCTURE: a cold open (2-3 scenes building to a titlecard), then one block per Stoic rule in
the pattern `Na` (title + setup) -> `Nq` (quote scene, ONLY if the rule has a real quote) ->
`Nb` (explanation + takeaway), then a close (a `center` scene + a `sub` scene). Use exactly
TWO images per rule: one shared by its `a` and `q` scenes, a second for its `b` scene. Reuse
one image across the cold-open scenes, and reuse one image across both closing scenes.

CONTENT RULES (non-negotiable):
- Total narration across all scenes: 1,700-1,900 words for a 12-13 minute video (English pace;
  a Spanish adaptation naturally runs a bit longer for the same content, that's fine).
  Each individual scene's narration must stay under 1,000 characters.
- Every quoted line must be a REAL, correctly attributed quote (Marcus Aurelius, Seneca, or
  Epictetus), using a well-known public-domain translation. Never invent a quote. If recounting
  a historical anecdote that isn't rock-solid history, hedge it explicitly ("it's said",
  "according to one ancient story", "se dice que...") rather than stating it as fact.
- Use ellipses (...) sparingly for dramatic pauses.
- Include exactly one personal-story placeholder inside a `b`-type scene's narration, written
  as a bracketed instruction the human will replace — in English: "[PERSONAL STORY: a moment
  from your own career where X]"; in Spanish: "[HISTORIA PERSONAL: un momento de tu carrera
  donde X]". Put it at the rule that fits it best thematically, not automatically the first one.
- Every image description must be a vivid, concrete visual (no text/letters/logos in the image)
  and must end with this exact sentence appended: "{image_suffix}"
- English channel (Stoic Leader Mind): calm, authoritative tone for leaders/founders/executives.
- Spanish channel (Estoicismo Para Líderes): broader everyday angle (work, money, family,
  discipline, heartbreak) — ADAPT rather than translate: use natural neutral Latin American
  Spanish, idioms and examples that land for that audience, not a literal rendering of an
  English original. Still use the exact same well-known Spanish translations for direct quotes
  from Marcus Aurelius/Seneca/Epictetus (these are fixed historical translations, not something
  to paraphrase).
""".replace("{image_suffix}", IMAGE_PROMPT_SUFFIX)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def generate_scenes(topic: str, channel: str, channel_name: str) -> dict:
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("pip install anthropic (missing from this environment)") from e

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set in .env. This is a separate key from any Claude "
            "subscription — get one at console.anthropic.com."
        )

    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = (
        f"Channel: {channel} ({channel_name})\n"
        f"Topic: {topic}\n\n"
        f"Write the full script now as the JSON schema described."
    )

    resp = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw_text = "".join(block.text for block in resp.content if hasattr(block, "text"))

    try:
        data = _extract_json(raw_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Model didn't return valid JSON. First 500 chars:\n{raw_text[:500]}") from e

    script = ScriptModel(**data)  # raises pydantic.ValidationError on a bad shape

    # cross-field checks pydantic alone can't express
    image_keys = set(script.images.keys())
    used_keys = {s.image for s in script.scenes}
    missing = used_keys - image_keys
    if missing:
        raise RuntimeError(f"scenes reference undefined image keys: {missing}")

    total_narration = " ".join(s.narration for s in script.scenes)
    word_count = len(total_narration.split())
    if not (1200 <= word_count <= 2400):
        print(f"[script_gen] WARNING: {word_count} words total — outside the 1,700-1,900 target range. Review before rendering.")

    if not any(any(m in s.narration for m in PERSONAL_STORY_MARKERS) for s in script.scenes):
        print("[script_gen] WARNING: no [PERSONAL STORY] placeholder found anywhere — add one manually before recording.")

    return json.loads(script.model_dump_json())


def generate_and_save(topic: str, channel: str, channel_name: str, out_path: Path) -> dict:
    scenes = generate_scenes(topic, channel, channel_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scenes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[script_gen] {topic!r} -> {out_path} ({len(scenes['scenes'])} scenes, {len(scenes['images'])} images)")
    return scenes
