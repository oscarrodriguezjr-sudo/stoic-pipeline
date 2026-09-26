"""
scenes.json['scenes'][i]['narration'] -> videos/<id>/vo/<key>.mp3

Lessons from CLAUDE.md Section 6, enforced here:
  - one generation at a time (sequential submit/poll/download, never parallel)
  - max 50 generations per model per day (tracked in state.py, stops early
    with a clear message rather than silently spilling into tomorrow)
  - on a rejected request: retry once as-is, then retry once more with the
    line lightly rephrased (strip curly quotes / em-dashes, which is a common
    trigger), then give up on that line and say so clearly
  - Runway doesn't expose a credits-balance endpoint we could confirm, so if
    everything starts failing, check dev.runwayml.com -> Billing yourself
    before assuming it's a code bug

NOTE: the preset_id used here comes from config/channels.yaml — pick from
the confirmed real preset list in runway_client.py's module docstring
(50 named voices, e.g. "James", "Bernard", "Mark"). See that docstring's
CORRECTION #1/#2 for why GET /voices looked empty and doesn't help here —
it only lists custom voices, not this built-in list.
"""
from __future__ import annotations

import re
from pathlib import Path

from .runway_client import RunwayClient, RunwayError
from .state import VideoState

DAILY_LIMIT_PER_MODEL = 50
EST_CREDITS_PER_SEGMENT = 5
EST_USD_PER_CREDIT = 0.01
MAX_PROMPT_CHARS = 1000  # eleven_multilingual_v2 limit is 1000 UTF-16 code units


def _rephrase(text: str) -> str:
    """Light, mechanical rewrite used only as a second attempt after a
    content-moderation rejection — strips characters that have tripped
    Runway's filter in past testing per CLAUDE.md Section 6."""
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("—", ", ").replace("–", "-")
    text = re.sub(r"\.\.\.+", "...", text)
    return text.strip()


def generate_voiceover(
    scenes: dict,
    video_dir: Path,
    state: VideoState,
    channel_cfg: dict,
    client: RunwayClient | None = None,
) -> dict[str, Path]:
    client = client or RunwayClient()
    vo_dir = video_dir / "vo"
    vo_dir.mkdir(parents=True, exist_ok=True)

    model = channel_cfg["voice"]["model"]
    preset_id = channel_cfg["voice"]["preset_id"]
    if preset_id in ("REPLACE_ME", "", None):
        raise RunwayError(
            "config/channels.yaml has a placeholder voice.preset_id — pick a real "
            "name from the 50 listed in runway_client.py's module docstring "
            "(e.g. James, Bernard, Mark) and put it in the config before recording."
        )

    result: dict[str, Path] = {}

    for scene in scenes["scenes"]:
        key = scene["key"]
        narration = scene["narration"]
        state_key = f"voice:{key}"
        out_path = vo_dir / f"{key}.mp3"

        if state.is_done(state_key):
            result[key] = out_path
            print(f"[voice] {key}: already done, skipping")
            continue

        if len(narration) > MAX_PROMPT_CHARS:
            raise RunwayError(
                f"[voice] scene {key}: narration is {len(narration)} chars, over the "
                f"{MAX_PROMPT_CHARS}-char limit — split this scene in scenes.json."
            )

        used_today = state.daily_usage(model)
        if used_today >= DAILY_LIMIT_PER_MODEL:
            print(
                f"[voice] Hit the {DAILY_LIMIT_PER_MODEL}/day cap for {model}. "
                f"Stopping here — rerun tomorrow with --resume to pick up at scene {key}."
            )
            break

        text_to_send = narration
        last_error = None
        for attempt in range(1, 4):
            try:
                print(f"[voice] {key}: submitting (attempt {attempt})...")
                created = client.create_text_to_speech(text_to_send, preset_id, model=model)
                task_id = created.get("id") or created.get("task_id")
                if not task_id:
                    raise RunwayError(f"No task id in create_text_to_speech response: {created}")
                state.set_asset(state_key, provider="runway", status="RUNNING", task_id=task_id)
                state.bump_daily_usage(model)

                task = client.wait_for_task(task_id)
                urls = client.extract_output_urls(task)
                client.download(urls[0], str(out_path))
                state.set_asset(
                    state_key,
                    provider="runway",
                    status="SUCCEEDED",
                    task_id=task_id,
                    cost_credits=EST_CREDITS_PER_SEGMENT,
                    cost_usd=EST_CREDITS_PER_SEGMENT * EST_USD_PER_CREDIT,
                    path=str(out_path),
                )
                result[key] = out_path
                print(f"[voice] {key}: done -> {out_path}")
                last_error = None
                break

            except RunwayError as e:
                last_error = e
                msg = str(e).lower()
                rejected = "reject" in msg or "moderation" in msg
                print(f"[voice] {key}: attempt {attempt} failed — {e}")
                if not rejected:
                    break  # not a content rejection (e.g. auth/network) — don't keep hammering it
                if attempt == 2:
                    text_to_send = _rephrase(narration)
                    print(f"[voice] {key}: retrying with lightly rephrased text")

        if last_error is not None:
            state.set_asset(state_key, provider="runway", status="FAILED")
            print(
                f"[voice] {key}: giving up after retries. If every scene is failing, "
                f"check your Runway credit balance at dev.runwayml.com -> Billing — "
                f"Runway rejects requests when credits run out, and that shows up as "
                f"the same 'rejected' error as content moderation."
            )
            raise last_error

    return result
