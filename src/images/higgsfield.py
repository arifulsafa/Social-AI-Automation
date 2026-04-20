"""
Higgsfield AI image client.

Auth: HTTP Basic with KEY_ID:KEY_SECRET (base64-encoded).
Generation is async — we poll until Completed or Failed.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import httpx

from src.config import settings

_BASE = "https://platform.higgsfield.ai"
_MODEL = "higgsfield-ai/soul/standard"
_POLL_INTERVAL = 5   # seconds between status checks
_POLL_TIMEOUT = 300  # give up after 5 minutes


def _auth() -> str:
    return f"Key {settings.higgsfield_key_id}:{settings.higgsfield_key_secret}"


def generate_image(prompt: str, *, out_dir: Path | None = None) -> Path:
    if not settings.higgsfield_key_id or not settings.higgsfield_key_secret:
        raise RuntimeError("HIGGSFIELD_KEY_ID / HIGGSFIELD_KEY_SECRET not set in .env")

    out_dir = out_dir or settings.image_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    headers = {"Authorization": _auth(), "Content-Type": "application/json"}

    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            f"{_BASE}/{_MODEL}",
            json={"prompt": prompt, "aspect_ratio": "1:1", "resolution": "720p"},
            headers=headers,
        )
        r.raise_for_status()
        body = r.json()
        request_id = body["request_id"]
        status_url = body["status_url"]

    # Poll until done
    deadline = time.monotonic() + _POLL_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(_POLL_INTERVAL)
        with httpx.Client(timeout=30.0) as client:
            r = client.get(status_url, headers=headers)
            r.raise_for_status()
            data = r.json()

        status = data.get("status", "")
        if status == "completed":
            image_url = data["images"][0]["url"]
            with httpx.Client(timeout=60.0) as client:
                img_resp = client.get(image_url)
                img_resp.raise_for_status()
            path = out_dir / f"{uuid.uuid4().hex}.png"
            path.write_bytes(img_resp.content)
            return path
        elif status in ("failed", "nsfw"):
            raise RuntimeError(f"Higgsfield generation {status}: {data}")
        # else Queued / InProgress — keep polling

    raise RuntimeError(f"Higgsfield timed out after {_POLL_TIMEOUT}s (request {request_id})")
