"""
Scheduled batch production — CLAUDE.md Section 10 Phase 7.

    python -m pipeline.batch --channel es --count 3
    python -m pipeline.batch --channel en --count 3 --upload

Picks the next N "pending" topics from config/topics.yaml for the given
channel, writes their scenes.json via script_gen, runs the full render
pipeline, and only then marks each topic "done" — a crash mid-topic leaves
it "pending" so the next scheduled run just retries it (video-level
state.json means it won't redo any asset that already succeeded).

This is the entry point a Render cron job should call.

--upload: per upload.py's PUBLISH_STATUS (currently "public" — Oscar's
explicit choice, see that module's docstring), a video produced with
--upload goes straight to a live, public YouTube video with NO human
watching it first. Without --upload, this just renders final.mp4/thumbnail/
metadata and stops — nothing gets near YouTube.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from . import script_gen
from .run import ROOT, load_config, run_video

TOPICS_PATH = ROOT / "config" / "topics.yaml"


def _load_topics() -> list[dict]:
    return yaml.safe_load(TOPICS_PATH.read_text(encoding="utf-8"))["topics"]


def _pending(topics: list[dict], channel: str, count: int) -> list[dict]:
    return [t for t in topics if t.get(f"status_{channel}") == "pending"][:count]


def _mark_done(topic_id: int, channel: str) -> None:
    """Flip status_<channel>: pending -> done for one topic's id block,
    without disturbing comments or formatting elsewhere in the file."""
    text = TOPICS_PATH.read_text(encoding="utf-8")
    blocks = list(re.finditer(r"(?m)^  - id: \d+", text))
    for i, m in enumerate(blocks):
        this_id = int(text[m.start():m.end()].split(":")[1])
        if this_id != topic_id:
            continue
        start = m.start()
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(text)
        block = text[start:end]
        new_block = re.sub(rf"(status_{channel}:\s*)pending", r"\1done", block, count=1)
        text = text[:start] + new_block + text[end:]
        TOPICS_PATH.write_text(text, encoding="utf-8")
        return
    raise RuntimeError(f"Couldn't find topic id {topic_id} in {TOPICS_PATH}")


def run_batch(channel: str, count: int, do_upload: bool) -> list[str]:
    channels, _ = load_config()
    channel_cfg = channels[channel]
    topics = _load_topics()
    pending = _pending(topics, channel, count)

    if not pending:
        print(f"[batch] no pending topics for '{channel}' — add more to config/topics.yaml")
        return []

    produced = []
    for topic in pending:
        slug = topic[f"slug_{channel}"]
        topic_text = topic[channel]
        video_dir = ROOT / "videos" / slug
        scenes_path = video_dir / "scenes.json"

        print(f"\n######## Topic {topic['id']} [{channel}]: {topic_text} ########")

        if not scenes_path.exists():
            script_gen.generate_and_save(topic_text, channel, channel_cfg["name"], scenes_path)
        else:
            print(f"[batch] {scenes_path} already exists, reusing it")

        run_video(channel, scenes_path, slug)

        if do_upload:
            from . import upload
            upload.upload_video(channel_cfg, video_dir)

        _mark_done(topic["id"], channel)
        produced.append(slug)
        print(f"[batch] topic {topic['id']} done -> videos/{slug}/final.mp4")

    return produced


def main() -> int:
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("--channel", required=True, choices=["en", "es"])
    p.add_argument("--count", type=int, default=3, help="how many pending topics to produce (default 3/week per CLAUDE.md cadence)")
    p.add_argument("--upload", action="store_true",
                    help="also upload after rendering, going straight to PUBLIC with no review "
                         "(needs --authorize run once first per channel) — see upload.py's docstring")
    args = p.parse_args()

    produced = run_batch(args.channel, args.count, args.upload)
    print(f"\n[batch] produced {len(produced)} video(s): {produced}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
