"""
Keeps pipeline.batch running on a weekly schedule inside a long-lived
Render Background Worker.

Render Cron Jobs cannot mount persistent disks (Render rejects a `disks:`
block on a `type: cron` service with "field disks not found in type
file.Service") — discovered when deploying render.yaml on 2026-09-28.
Only Background Workers and Private Services support disks, and this
project's whole persistence design (state.json, topics.yaml done/pending
flags, the saved YouTube OAuth tokens) depends on a disk surviving between
runs. So instead of a `type: cron` service that Render spins up fresh on
a schedule, render.yaml now runs this script as a `type: worker` — one
process that stays alive the whole time, sleeps until the next scheduled
moment, runs pipeline.batch, then goes back to sleep.

    python -m pipeline.scheduler --channel es --count 3 --upload --hour 14
    python -m pipeline.scheduler --channel en --count 3 --upload --hour 15

Runs every Monday at the given UTC hour (default 14:00 UTC), matching the
original render.yaml cron schedules ("0 14 * * 1" / "0 15 * * 1"). All
other flags are passed straight through to `python -m pipeline.batch`.
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

WEEKDAY = 0  # Monday


def _extract_hour(argv: list[str]) -> tuple[int, list[str]]:
    hour = 14
    rest = list(argv)
    if "--hour" in rest:
        i = rest.index("--hour")
        hour = int(rest[i + 1])
        del rest[i:i + 2]
    return hour, rest


def _next_run(now: datetime, hour: int) -> datetime:
    candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    days_ahead = (WEEKDAY - now.weekday()) % 7
    candidate += timedelta(days=days_ahead)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def main() -> int:
    hour, batch_args = _extract_hour(sys.argv[1:])
    print(f"[scheduler] starting — will run `python -m pipeline.batch {' '.join(batch_args)}` "
          f"every Monday at {hour:02d}:00 UTC", flush=True)

    while True:
        now = datetime.now(timezone.utc)
        run_at = _next_run(now, hour)
        sleep_s = (run_at - now).total_seconds()
        print(f"[scheduler] next run at {run_at.isoformat()} (sleeping {sleep_s / 3600:.1f}h)", flush=True)
        time.sleep(sleep_s)

        print(f"[scheduler] {datetime.now(timezone.utc).isoformat()} — running batch", flush=True)
        result = subprocess.run([sys.executable, "-m", "pipeline.batch", *batch_args])
        print(f"[scheduler] batch exited with code {result.returncode}", flush=True)

        # Guard against clock/DST edge cases that could re-trigger immediately.
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
