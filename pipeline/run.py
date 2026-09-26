"""
CLI entry point.

    python -m pipeline.run --check
    python -m pipeline.run --list-voices
    python -m pipeline.run --channel es --scenes videos/reglas-estoicas-calma/scenes.json --video-id reglas-estoicas-calma
    python -m pipeline.run --resume reglas-estoicas-calma --channel es

Every step is resumable: rerun the same command after a crash and it picks
up wherever state.json left off (CLAUDE.md Section 8).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .images import generate_images
from .metadata import build_metadata
from .overlays import generate_overlays
from .render import concat_and_finalize, render_segment
from .runway_client import RunwayClient, RunwayError
from .state import VideoState
from .thumbnail import make_variants
from .voice import generate_voiceover

ROOT = Path(__file__).resolve().parent.parent


def load_config():
    channels = yaml.safe_load((ROOT / "config" / "channels.yaml").read_text(encoding="utf-8"))["channels"]
    style = yaml.safe_load((ROOT / "config" / "style.yaml").read_text(encoding="utf-8"))
    return channels, style


def cmd_check() -> int:
    ok = True

    if shutil.which("ffmpeg") is None:
        print("[check] FAIL: ffmpeg not found on PATH. Install with `winget install Gyan.FFmpeg` and reopen your terminal.")
        ok = False
    else:
        print("[check] ffmpeg: found")

    for name in ("Cinzel[wght].ttf", "CormorantGaramond-Italic[wght].ttf"):
        p = ROOT / "assets" / "fonts" / name
        if not p.exists():
            print(f"[check] FAIL: missing font {p}. Download from github.com/google/fonts "
                  f"(ofl/cinzel, ofl/cormorantgaramond) into assets/fonts/.")
            ok = False
        else:
            print(f"[check] font: {name} found")

    import os
    if not os.environ.get("RUNWAY_API_KEY"):
        print("[check] FAIL: RUNWAY_API_KEY not set — check .env")
        ok = False
    else:
        print("[check] RUNWAY_API_KEY: set")
        try:
            RunwayClient().list_voices()
            print("[check] Runway API: reachable, key accepted")
        except RunwayError as e:
            print(f"[check] FAIL: Runway API call failed — {e}")
            ok = False

    channels, _ = load_config()
    for lang, cfg in channels.items():
        if cfg["voice"]["preset_id"] in ("REPLACE_ME", "", None):
            print(f"[check] FAIL: config/channels.yaml [{lang}].voice.preset_id is still a placeholder. "
                  f"Pick a real name from the 50 listed in runway_client.py's module docstring.")
            ok = False

    print("[check] " + ("ALL GOOD" if ok else "FIX THE ABOVE BEFORE CONTINUING"))
    return 0 if ok else 1


def cmd_list_voices() -> int:
    """Lists *custom* voices already created on this Runway account — there
    is no built-in preset library (see runway_client.py's module docstring).
    Use --create-voice to make one if this comes back empty."""
    try:
        voices = RunwayClient().list_voices()
    except RunwayError as e:
        print(f"Couldn't reach Runway: {e}")
        return 1
    print(json.dumps(voices, indent=2, ensure_ascii=False))
    if not voices:
        print("\nNo custom voices exist on this account yet. Run:\n"
              "  python -m pipeline.run --create-voice\n"
              "to design one from a text description (or clone one from audio).")
    return 0


DEFAULT_VOICE_NAME = "Stoic Narrator"
DEFAULT_VOICE_PROMPT = (
    "A calm, deep, measured male voice in his 40s-50s, authoritative but warm, "
    "like a thoughtful mentor narrating ancient wisdom. Slow, deliberate pacing "
    "with natural gravitas — suited to reflective philosophical narration in "
    "both English and Spanish."
)


def cmd_create_voice(name: str, prompt: str | None, audio_url: str | None) -> int:
    client = RunwayClient()
    try:
        if audio_url:
            print(f"[create-voice] cloning '{name}' from {audio_url} ...")
            created = client.create_voice_from_audio(name, audio_url)
        else:
            used_prompt = prompt or DEFAULT_VOICE_PROMPT
            print(f"[create-voice] designing '{name}' from a text description ...")
            print(f"[create-voice] prompt: {used_prompt}")
            created = client.create_voice_from_text(name, used_prompt)
        voice_id = created.get("id")
        if not voice_id:
            print(f"[create-voice] FAIL: no 'id' in response — raw response:\n{json.dumps(created, indent=2)}")
            return 1
        print(f"[create-voice] created, id={voice_id}, waiting for it to become READY ...")
        voice = client.wait_for_voice(voice_id)
        print(f"[create-voice] READY. voice_id = {voice_id}")
        preview = voice.get("previewUrl") or voice.get("preview_url")
        if preview:
            print(f"[create-voice] preview (listen before locking it in): {preview}")
        print(
            "\nPut this in config/channels.yaml for [en].voice.voice_id (and try it for "
            "[es] too, per the note in that file, before creating a second voice):\n"
            f"  voice_id: \"{voice_id}\""
        )
        return 0
    except RunwayError as e:
        print(f"[create-voice] FAIL: {e}")
        return 1


def run_video(channel: str, scenes_path: Path, video_id: str) -> int:
    channels, style = load_config()
    if channel not in channels:
        print(f"Unknown channel '{channel}', expected one of {list(channels)}")
        return 1
    channel_cfg = channels[channel]

    scenes = json.loads(scenes_path.read_text(encoding="utf-8"))
    video_dir = ROOT / "videos" / video_id
    video_dir.mkdir(parents=True, exist_ok=True)
    # keep the scenes.json that was actually used alongside the outputs
    (video_dir / "scenes.json").write_text(json.dumps(scenes, indent=2, ensure_ascii=False), encoding="utf-8")

    state = VideoState(video_dir)
    client = RunwayClient()

    print(f"\n=== {scenes['title']} [{channel}] ===")

    print("\n-- Phase: images --")
    images = generate_images(scenes, video_dir, state, client)

    print("\n-- Phase: voiceover --")
    voices = generate_voiceover(scenes, video_dir, state, channel_cfg, client)

    print("\n-- Phase: overlays --")
    overlays = generate_overlays(scenes, video_dir, channel_cfg, style)

    print("\n-- Phase: render segments --")
    seg_dir = video_dir / "segments"
    seg_dir.mkdir(exist_ok=True)
    segment_paths = []
    for scene in scenes["scenes"]:
        key = scene["key"]
        img_path = images[scene["image"]]
        seg_out = seg_dir / f"{key}.mp4"
        render_segment(scene, img_path, overlays[key], voices[key], seg_out)
        segment_paths.append(seg_out)

    print("\n-- Phase: final assembly --")
    final_path = video_dir / "final.mp4"
    concat_and_finalize(segment_paths, video_dir, style, final_path)

    print("\n-- Phase: thumbnail + metadata --")
    # use the image from the first "title"-type scene as the thumbnail source
    thumb_scene = next((s for s in scenes["scenes"] if s["overlay"]["type"] == "title"), scenes["scenes"][0])
    make_variants(images[thumb_scene["image"]], scenes["title"], channel_cfg, video_dir)
    build_metadata(scenes, segment_paths, channel_cfg, video_dir / "metadata.json")

    print(f"\n=== DONE: {final_path} ===")
    print(state.summary())
    return 0


def main() -> int:
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    p.add_argument("--list-voices", action="store_true")
    p.add_argument("--create-voice", action="store_true",
                    help="design (or clone, with --voice-audio) a custom Runway voice — "
                         "there's no preset library, this is a one-time step")
    p.add_argument("--voice-name", default=DEFAULT_VOICE_NAME)
    p.add_argument("--voice-prompt", help="text description for --create-voice (default: a calm stoic narrator)")
    p.add_argument("--voice-audio", help="URL to a reference audio sample, to clone instead of design")
    p.add_argument("--channel", choices=["en", "es"])
    p.add_argument("--scenes", type=Path)
    p.add_argument("--video-id")
    p.add_argument("--resume")
    args = p.parse_args()

    if args.check:
        return cmd_check()
    if args.list_voices:
        return cmd_list_voices()
    if args.create_voice:
        return cmd_create_voice(args.voice_name, args.voice_prompt, args.voice_audio)

    video_id = args.resume or args.video_id
    if not (video_id and args.channel and (args.scenes or args.resume)):
        p.print_help()
        return 1

    scenes_path = args.scenes or (ROOT / "videos" / video_id / "scenes.json")
    return run_video(args.channel, scenes_path, video_id)


if __name__ == "__main__":
    sys.exit(main())
