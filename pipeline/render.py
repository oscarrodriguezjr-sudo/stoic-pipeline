"""
scenes + images + overlays + voiceover -> videos/<id>/final.mp4

Follows the render recipe in CLAUDE.md Section 7: one ffmpeg process per
segment (keeps memory low), Ken Burns zoom via zoompan, overlay fade in/out,
0.5s fade on the whole segment, then concat + ambient bed + loudnorm.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

ZOOM_EXPR = {
    "in": "1+0.0006*on",
    "out": "1.15-0.0006*on",
    "in2": "1.12+0.0005*on",
}
PADDING = {"default": 1.6, "quote": 2.4, "closing": 3.0}
VOICE_START_DELAY = 0.7
SEGMENT_FADE = 0.5
FPS = 30
RES = "1920x1080"


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{r.stderr[-2000:]}")


def _ffprobe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {r.stderr}")
    return float(json.loads(r.stdout)["format"]["duration"])


def upscale_image(src: Path, dest: Path, size=(2560, 1440)) -> Path:
    if dest.exists():
        return dest
    im = Image.open(src).convert("RGB")
    im = im.resize(size, Image.LANCZOS)
    im.save(dest, quality=95)
    return dest


def _padding_for(scene: dict) -> float:
    if scene["overlay"]["type"] == "quote":
        return PADDING["quote"]
    if scene["overlay"]["type"] in ("center", "sub"):
        return PADDING["closing"]
    return PADDING["default"]


def render_segment(
    scene: dict,
    image_path: Path,
    overlay_path: Path,
    voice_path: Path,
    out_path: Path,
) -> Path:
    if out_path.exists():
        print(f"[render] {scene['key']}: segment already exists, skipping")
        return out_path

    voice_dur = _ffprobe_duration(voice_path)
    duration = voice_dur + VOICE_START_DELAY + _padding_for(scene)

    zoom_key = scene.get("zoom", "in")
    zoom_expr = ZOOM_EXPR[zoom_key]

    upscaled = image_path.with_name(image_path.stem + "_up.jpg")
    upscale_image(image_path, upscaled)

    delay_ms = int(VOICE_START_DELAY * 1000)
    fade_out_start = max(duration - SEGMENT_FADE, 0)
    ov_fade_out_start = max(duration - SEGMENT_FADE, 0)

    filter_complex = (
        f"[0:v]zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d=1:s={RES}:fps={FPS},"
        f"fade=t=in:st=0:d={SEGMENT_FADE},fade=t=out:st={fade_out_start}:d={SEGMENT_FADE}[bg];"
        f"[1:v]fade=t=in:st=0:d={SEGMENT_FADE}:alpha=1,"
        f"fade=t=out:st={ov_fade_out_start}:d={SEGMENT_FADE}:alpha=1[ov];"
        f"[bg][ov]overlay=0:0:format=auto[v];"
        f"[2:a]adelay={delay_ms}|{delay_ms},apad[a]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(upscaled),
        "-loop", "1", "-i", str(overlay_path),
        "-i", str(voice_path),
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-t", f"{duration:.3f}",
        "-r", str(FPS),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        str(out_path),
    ]
    _run(cmd)
    print(f"[render] {scene['key']}: -> {out_path} ({duration:.1f}s)")
    return out_path


def concat_and_finalize(segment_paths: list[Path], video_dir: Path, style_cfg: dict, final_path: Path) -> Path:
    list_file = video_dir / "segments" / "concat_list.txt"
    list_file.parent.mkdir(parents=True, exist_ok=True)
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in segment_paths), encoding="utf-8")

    concat_path = video_dir / "segments" / "_concat.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(concat_path)])

    ab = style_cfg["ambient_bed"]
    total_dur = _ffprobe_duration(concat_path)

    filter_complex = (
        f"aevalsrc='{ab['expr']}':d={total_dur:.3f}[bed0];"
        f"[bed0]tremolo={ab['tremolo']},lowpass={ab['lowpass']},volume={ab['volume']},"
        f"afade=t=in:st=0:d={ab['fade_seconds']},afade=t=out:st={max(total_dur - ab['fade_seconds'], 0):.3f}:d={ab['fade_seconds']}[bed];"
        f"[0:a][bed]amix=inputs=2:normalize=0[amixed];"
        f"[amixed]loudnorm=I={style_cfg['loudness']['I']}:TP={style_cfg['loudness']['TP']}:LRA={style_cfg['loudness']['LRA']}[aout]"
    )

    _run([
        "ffmpeg", "-y",
        "-i", str(concat_path),
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-movflags", "+faststart",
        str(final_path),
    ])
    print(f"[render] final video -> {final_path} ({total_dur:.1f}s)")
    return final_path
