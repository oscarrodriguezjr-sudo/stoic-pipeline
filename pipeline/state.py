"""
State ledger for one video: every generated asset's provider, task id,
status, cost, and local path — so a crash never means regenerating a
paid asset. See CLAUDE.md Section 8.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import date
from pathlib import Path
from typing import Any, Optional


class VideoState:
    def __init__(self, video_dir: Path):
        self.video_dir = Path(video_dir)
        self.video_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.video_dir / "state.json"
        self._lock = threading.Lock()
        self.data: dict[str, Any] = {
            "assets": {},        # key -> {provider, task_id, status, cost, path, ts}
            "daily_usage": {},   # "2026-09-23|eleven_multilingual_v2" -> count
            "totals": {"credits": 0, "usd": 0.0},
        }
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            self.data.setdefault("daily_usage", {})
            self.data.setdefault("totals", {"credits": 0, "usd": 0.0})

    def save(self) -> None:
        with self._lock:
            self.path.write_text(
                json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    # ---- assets -------------------------------------------------------

    def get_asset(self, key: str) -> Optional[dict]:
        return self.data["assets"].get(key)

    def is_done(self, key: str) -> bool:
        a = self.get_asset(key)
        return bool(a and a.get("status") == "SUCCEEDED" and a.get("path") and Path(a["path"]).exists())

    def set_asset(
        self,
        key: str,
        *,
        provider: str,
        status: str,
        task_id: Optional[str] = None,
        cost_credits: float = 0,
        cost_usd: float = 0.0,
        path: Optional[str] = None,
    ) -> None:
        prev = self.data["assets"].get(key, {})
        self.data["assets"][key] = {
            "provider": provider,
            "task_id": task_id or prev.get("task_id"),
            "status": status,
            "cost_credits": cost_credits or prev.get("cost_credits", 0),
            "cost_usd": cost_usd or prev.get("cost_usd", 0.0),
            "path": path or prev.get("path"),
            "ts": time.time(),
        }
        if status == "SUCCEEDED" and prev.get("status") != "SUCCEEDED":
            self.data["totals"]["credits"] += cost_credits
            self.data["totals"]["usd"] += cost_usd
        self.save()

    # ---- daily rate limits ---------------------------------------------

    def daily_usage(self, model: str) -> int:
        return self.data["daily_usage"].get(f"{date.today().isoformat()}|{model}", 0)

    def bump_daily_usage(self, model: str) -> int:
        k = f"{date.today().isoformat()}|{model}"
        self.data["daily_usage"][k] = self.data["daily_usage"].get(k, 0) + 1
        self.save()
        return self.data["daily_usage"][k]

    # ---- summary --------------------------------------------------------

    def summary(self) -> str:
        done = sum(1 for a in self.data["assets"].values() if a.get("status") == "SUCCEEDED")
        total = len(self.data["assets"])
        return (
            f"{done}/{total} assets done · "
            f"{self.data['totals']['credits']:.0f} credits · "
            f"${self.data['totals']['usd']:.2f} spent"
        )
