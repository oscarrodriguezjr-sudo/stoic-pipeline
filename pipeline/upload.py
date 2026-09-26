"""
final.mp4 + thumbnail + metadata.json -> a YouTube upload on the right
channel's Brand Account. CLAUDE.md Section 10 Phase 5 / Section 11.

ONE-TIME SETUP PER CHANNEL (this part genuinely can't be automated — Google
requires a human to click through the OAuth consent screen once per
account):

    python -m pipeline.upload --authorize --channel en
    python -m pipeline.upload --authorize --channel es

Each opens a browser, you sign in as the Brand Account's manager and approve
access, and it saves a refresh token to the path in
config/channels.yaml -> oauth_token_path. After that, uploads are fully
unattended — the saved token refreshes itself.

You'll also need a Google Cloud OAuth client (Desktop app type) — download
its JSON as config/google_client_secret.json. console.cloud.google.com ->
APIs & Services -> Credentials -> Create OAuth client ID. Enable the
"YouTube Data API v3" on that project first.

PRIVACY STATUS — read this before running unattended:
CLAUDE.md Section 11 treats a human approval step before publish as
non-negotiable, mainly because of YouTube's enforcement against repetitive,
unreviewed AI content. Oscar explicitly asked (2026-09-23) to override that
for this project and go straight to Public with no review — that choice is
implemented below (PUBLISH_STATUS = "public", and batch.py calls this with
no human in the loop). This means: a bad Runway image, a mispronounced line,
or a factual slip goes straight to a live public video on a real channel,
and if a batch of near-duplicate unreviewed videos trips YouTube's
inauthentic-content detection, it risks BOTH channels at once, not just the
one video. That risk was explained and this is what was chosen anyway — if
that ever stops being true, change PUBLISH_STATUS to "private" or "unlisted"
below (or pass --privacy-status on the CLI) and the review gate is back.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_PATH = Path("config/google_client_secret.json")

# See the module docstring's PRIVACY STATUS note before changing this.
PUBLISH_STATUS = "public"


def _get_credentials(token_path: Path) -> Credentials:
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def authorize(channel_cfg: dict) -> None:
    token_path = Path(channel_cfg["oauth_token_path"])
    if not CLIENT_SECRET_PATH.exists():
        raise RuntimeError(
            f"{CLIENT_SECRET_PATH} not found — download it from Google Cloud Console "
            f"(OAuth client, Desktop app type) first."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
    creds = flow.run_local_server(port=0)  # opens a browser for the one-time consent
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"Authorized. Token saved to {token_path} — future uploads on this channel are unattended.")


def upload_video(channel_cfg: dict, video_dir: Path, privacy_status: str | None = None) -> str:
    token_path = Path(channel_cfg["oauth_token_path"])
    if not token_path.exists():
        raise RuntimeError(
            f"No saved token at {token_path}. Run `python -m pipeline.upload --authorize "
            f"--channel <en|es>` once, interactively, before automating uploads."
        )
    creds = _get_credentials(token_path)
    if not creds or not creds.valid:
        raise RuntimeError(f"Token at {token_path} is invalid/expired and couldn't refresh — re-run --authorize.")

    meta = json.loads((video_dir / "metadata.json").read_text(encoding="utf-8"))
    final_path = video_dir / "final.mp4"
    thumb_path = video_dir / "thumbnail_a.png"
    if not final_path.exists():
        raise RuntimeError(f"{final_path} doesn't exist — render the video before uploading.")

    status = privacy_status or PUBLISH_STATUS
    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
        },
        "status": {"privacyStatus": status, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(final_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[upload] {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"[upload] uploaded as {status.upper()}: https://studio.youtube.com/video/{video_id}/edit")

    if thumb_path.exists():
        youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumb_path))).execute()
        print("[upload] thumbnail set")

    return video_id


def main() -> int:
    import yaml

    p = argparse.ArgumentParser()
    p.add_argument("--authorize", action="store_true")
    p.add_argument("--channel", required=True, choices=["en", "es"])
    p.add_argument("--video-id")
    p.add_argument("--privacy-status", choices=["public", "unlisted", "private"], default=None,
                    help=f"override the default ({PUBLISH_STATUS}) for this one upload")
    args = p.parse_args()

    channels = yaml.safe_load(Path("config/channels.yaml").read_text(encoding="utf-8"))["channels"]
    channel_cfg = channels[args.channel]

    if args.authorize:
        authorize(channel_cfg)
        return 0

    if not args.video_id:
        print("Pass --video-id <id> to upload a specific rendered video.")
        return 1

    upload_video(channel_cfg, Path("videos") / args.video_id, privacy_status=args.privacy_status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
