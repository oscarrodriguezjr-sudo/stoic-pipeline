"""
Thin wrapper around the Runway Dev API (api.dev.runwayml.com/v1).

Verified against the live API reference on 2026-09-23:
  - base URL:        https://api.dev.runwayml.com/v1
  - auth header:      Authorization: Bearer <RUNWAY_API_KEY>
  - version header:   X-Runway-Version: 2024-11-06
  - create image:      POST /text_to_image   {promptText, model, ratio, ...}
  - create speech:      POST /text_to_speech  {model, prompt_text, voice}
  - poll a task:        GET  /tasks/{id}
  - list voices:         GET  /voices  (see CORRECTION below)
  - create a voice:      POST /voices  {name, from: {...}}
  - get a voice:         GET  /voices/{id}

CORRECTION #1 (2026-09-25, since superseded — kept here as a warning):
`GET /voices` returned an empty list on Oscar's account, which looked like
"no preset library exists — you must create a custom voice." That's WRONG.
`GET /voices` only ever lists *custom* voices you've created; it was never
going to show the built-in preset library, which isn't a listable resource
at all — it's a fixed, undocumented set of names baked into Runway's own
SDK types. Chasing the empty list down the custom-voice path (design/clone
via POST /voices, then {"voice": {"type": "custom", "id": ...}}) wasted a
step: that "custom" type is not a valid discriminator for text_to_speech's
voice field at all — POST /text_to_speech only accepts
{"type": "runway-preset", "preset_id": <name>} or
{"type": "reference-audio", "audio_uri": <url>} (the seed_audio model).

CORRECTION #2 (2026-09-25, the actual fix, confirmed against
runwayml/sdk-python's text_to_speech_create_params.py on GitHub — the
closest thing to ground truth short of the live API itself): the real bug
was a field-name casing mismatch. The wire-format JSON field for the line
to speak is **`promptText`** (camelCase) on eleven_multilingual_v2, not
`prompt_text` — the Python SDK's snake_case `prompt_text` is a local alias
that gets serialized to `promptText` on the wire, and this module's `_post`
was sending the raw snake_case key with no such translation, which the API
rejected as "expected string, received undefined". Confirmed valid
preset_id values (50 total, includes "James" despite Section 14's claim it
didn't exist — the preset roster is apparently not fixed over time, so
don't trust an old exclusion list either): Maya, Arjun, Serene, Bernard,
Billy, Mark, Clint, Mabel, Chad, Leslie, Eleanor, Elias, Elliot, Grungle,
Brodie, Sandra, Kirk, Kylie, Lara, Lisa, Malachi, Marlene, Martin, Miriam,
Monster, Paula, Pip, Rusty, Ragnar, Xylar, Maggie, Jack, Katie, Noah, James,
Rina, Ella, Mariah, Frank, Claudia, Niki, Vincent, Kendrick, Myrna, Tom,
Wanda, Benjamin, Kiana, Rachel. config/channels.yaml stores `preset_id`
(back to the original Section 3/6 design) — the `create_voice_from_text` /
`create_voice_from_audio` / `wait_for_voice` methods below still work as
custom-voice API calls, but nothing in this pipeline uses them; they're
left in case a future feature (not text_to_speech) needs a cloned voice.

IMPORTANT: this module could not be tested end-to-end from the machine that
wrote it — this cloud sandbox's network policy blocks api.dev.runwayml.com
outright. Endpoint paths and request shapes are confirmed from Runway's own
docs/SDK source; the exact field names in a *response* (status enum values,
where the output URL lives) were NOT independently confirmed and are
implemented against the most common Runway response shape
({"id", "status", "output": [...]}) with status in
{PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED}. If your first run hits a
KeyError or an unexpected status string while polling, print the raw JSON
(this module does that automatically on an unrecognized shape) and adjust
`_extract_output` / the status set below — do not just retry blindly.
"""
from __future__ import annotations

import os
import time
from typing import Any, Optional

import requests

BASE_URL = "https://api.dev.runwayml.com/v1"
API_VERSION = "2024-11-06"

TERMINAL_OK = {"SUCCEEDED"}
TERMINAL_FAIL = {"FAILED", "CANCELLED", "ABORTED"}


class RunwayError(RuntimeError):
    pass


class RunwayClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("RUNWAY_API_KEY")
        if not self.api_key:
            raise RunwayError("RUNWAY_API_KEY is not set (check .env)")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "X-Runway-Version": API_VERSION,
                "Content-Type": "application/json",
            }
        )

    def _post(self, path: str, body: dict) -> dict:
        try:
            r = self.session.post(f"{BASE_URL}{path}", json=body, timeout=60)
        except requests.exceptions.RequestException as e:
            raise RunwayError(f"Couldn't reach Runway for POST {path} — {e}") from e
        if r.status_code == 401:
            raise RunwayError("Runway rejected the API key (401) — check .env")
        if r.status_code == 429:
            raise RunwayError("RATE_LIMITED")
        if not r.ok:
            raise RunwayError(f"POST {path} -> {r.status_code}: {r.text[:500]}")
        return r.json()

    def get_task(self, task_id: str) -> dict:
        try:
            r = self.session.get(f"{BASE_URL}/tasks/{task_id}", timeout=30)
        except requests.exceptions.RequestException as e:
            raise RunwayError(f"Couldn't reach Runway for GET /tasks/{task_id} — {e}") from e
        if not r.ok:
            raise RunwayError(f"GET /tasks/{task_id} -> {r.status_code}: {r.text[:500]}")
        return r.json()

    def list_voices(self) -> list[dict]:
        try:
            r = self.session.get(f"{BASE_URL}/voices", timeout=30)
        except requests.exceptions.RequestException as e:
            raise RunwayError(f"Couldn't reach Runway for GET /voices — {e}") from e
        if not r.ok:
            raise RunwayError(f"GET /voices -> {r.status_code}: {r.text[:500]}")
        data = r.json()
        return data.get("data", data if isinstance(data, list) else [])

    def create_text_to_image(self, prompt_text: str, ratio: str = "1920:1080", model: str = "gen4_image") -> dict:
        return self._post("/text_to_image", {"promptText": prompt_text, "model": model, "ratio": ratio})

    def create_text_to_speech(self, prompt_text: str, preset_id: str, model: str = "eleven_multilingual_v2") -> dict:
        body = {
            "model": model,
            "promptText": prompt_text,
            "voice": {"type": "runway-preset", "presetId": preset_id},
        }
        return self._post("/text_to_speech", body)

    def create_voice_from_text(self, name: str, prompt: str, model: str = "eleven_ttv_v3") -> dict:
        """Design a new voice from a text description. Returns the voice
        object immediately (status will be PENDING/PROCESSING) — poll with
        get_voice() until status == "READY" before using its id."""
        return self._post_voices({"name": name, "from": {"type": "text", "prompt": prompt, "model": model}})

    def create_voice_from_audio(self, name: str, audio_url: str) -> dict:
        """Clone a voice from a reference audio sample (URL)."""
        return self._post_voices({"name": name, "from": {"type": "audio", "audio": audio_url}})

    def _post_voices(self, body: dict) -> dict:
        try:
            r = self.session.post(f"{BASE_URL}/voices", json=body, timeout=60)
        except requests.exceptions.RequestException as e:
            raise RunwayError(f"Couldn't reach Runway for POST /voices — {e}") from e
        if not r.ok:
            raise RunwayError(f"POST /voices -> {r.status_code}: {r.text[:500]}")
        return r.json()

    def get_voice(self, voice_id: str) -> dict:
        try:
            r = self.session.get(f"{BASE_URL}/voices/{voice_id}", timeout=30)
        except requests.exceptions.RequestException as e:
            raise RunwayError(f"Couldn't reach Runway for GET /voices/{voice_id} — {e}") from e
        if not r.ok:
            raise RunwayError(f"GET /voices/{voice_id} -> {r.status_code}: {r.text[:500]}")
        return r.json()

    def wait_for_voice(self, voice_id: str, poll_seconds: float = 5.0, timeout_seconds: float = 300.0) -> dict:
        start = time.time()
        while True:
            voice = self.get_voice(voice_id)
            status = str(voice.get("status", "")).upper()
            if status == "READY":
                return voice
            if status in ("FAILED", "ERROR"):
                raise RunwayError(f"Voice {voice_id} failed to build: {voice}")
            if time.time() - start > timeout_seconds:
                raise RunwayError(f"Voice {voice_id} timed out after {timeout_seconds}s, last status {status}")
            time.sleep(poll_seconds)

    def wait_for_task(self, task_id: str, poll_seconds: float = 5.0, timeout_seconds: float = 600.0) -> dict:
        """Poll GET /tasks/{id} until it reaches a terminal state."""
        start = time.time()
        while True:
            task = self.get_task(task_id)
            status = str(task.get("status", "")).upper()
            if status in TERMINAL_OK:
                return task
            if status in TERMINAL_FAIL:
                raise RunwayError(f"Task {task_id} ended {status}: {task}")
            if not status:
                # unrecognized response shape — surface it instead of looping forever
                raise RunwayError(f"Task {task_id}: couldn't find a status field in {task}")
            if time.time() - start > timeout_seconds:
                raise RunwayError(f"Task {task_id} timed out after {timeout_seconds}s, last status {status}")
            time.sleep(poll_seconds)

    @staticmethod
    def extract_output_urls(task: dict) -> list[str]:
        """Pull output URL(s) out of a completed task's JSON, tolerant of a
        couple of likely response shapes."""
        out = task.get("output")
        if isinstance(out, list):
            return [o for o in out if isinstance(o, str)]
        if isinstance(out, dict):
            for key in ("url", "audio", "image", "uri"):
                if key in out:
                    return [out[key]]
        if isinstance(out, str):
            return [out]
        raise RunwayError(f"Couldn't find an output URL in completed task: {task}")

    def download(self, url: str, dest_path: str) -> None:
        r = self.session.get(url, timeout=120)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(r.content)
