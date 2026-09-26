"""
scenes.json['images'] -> videos/<id>/img/<key>.png

One Runway text_to_image call per unique image key (scenes reuse the same
key/image across several beats), submitted sequentially, resumable via
state.py. Cost estimate uses CLAUDE.md's observed ~8 credits/image
(~$0.01/credit) — Runway doesn't return a cost field on the task, so this
is bookkeeping, not a billing source of truth; check dev.runwayml.com ->
Billing for the real balance.
"""
from __future__ import annotations

from pathlib import Path

from .runway_client import RunwayClient, RunwayError
from .state import VideoState

EST_CREDITS_PER_IMAGE = 8
EST_USD_PER_CREDIT = 0.01
IMAGE_PROMPT_SUFFIX = (
    " Cinematic painting, epic historical film still, ancient Rome, warm amber "
    "light against deep shadows, rich detail, no text, no letters, no watermark."
)


def generate_images(scenes: dict, video_dir: Path, state: VideoState, client: RunwayClient | None = None) -> dict[str, Path]:
    client = client or RunwayClient()
    img_dir = video_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    images: dict[str, str] = scenes.get("images", {})
    result: dict[str, Path] = {}

    for key, prompt in images.items():
        state_key = f"image:{key}"
        out_path = img_dir / f"{key}.png"

        if state.is_done(state_key):
            result[key] = out_path
            print(f"[images] {key}: already done, skipping")
            continue

        asset = state.get_asset(state_key)
        full_prompt = prompt if prompt.rstrip().endswith(".") is False else prompt
        full_prompt = f"{prompt.rstrip()}.{IMAGE_PROMPT_SUFFIX}" if not prompt.rstrip().endswith(IMAGE_PROMPT_SUFFIX.strip()) else prompt

        try:
            if asset and asset.get("task_id") and asset.get("status") not in ("SUCCEEDED",):
                # resume an in-flight task instead of resubmitting
                print(f"[images] {key}: resuming task {asset['task_id']}")
                task_id = asset["task_id"]
            else:
                print(f"[images] {key}: submitting...")
                created = client.create_text_to_image(full_prompt)
                task_id = created.get("id") or created.get("task_id")
                if not task_id:
                    raise RunwayError(f"No task id in create_text_to_image response: {created}")
                state.set_asset(state_key, provider="runway", status="RUNNING", task_id=task_id)

            task = client.wait_for_task(task_id)
            urls = client.extract_output_urls(task)
            client.download(urls[0], str(out_path))
            state.set_asset(
                state_key,
                provider="runway",
                status="SUCCEEDED",
                task_id=task_id,
                cost_credits=EST_CREDITS_PER_IMAGE,
                cost_usd=EST_CREDITS_PER_IMAGE * EST_USD_PER_CREDIT,
                path=str(out_path),
            )
            result[key] = out_path
            print(f"[images] {key}: done -> {out_path}")

        except RunwayError as e:
            state.set_asset(state_key, provider="runway", status="FAILED")
            print(f"[images] {key}: FAILED — {e}")
            raise

    return result
