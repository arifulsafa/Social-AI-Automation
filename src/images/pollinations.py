"""
Pollinations.ai image client — free, no API key required.

GET https://image.pollinations.ai/prompt/{prompt}
Returns the image bytes directly. Rate limit: ~1 req/15s.
"""
from __future__ import annotations

import urllib.parse
import uuid
from pathlib import Path

import httpx

from src.config import settings

_BASE = "https://image.pollinations.ai/prompt"


def generate_image(prompt: str, *, out_dir: Path | None = None) -> tuple[Path, str]:
    """Returns (local_path, public_url)."""
    out_dir = out_dir or settings.image_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    encoded = urllib.parse.quote(prompt)
    public_url = f"{_BASE}/{encoded}?width=1024&height=1024&nologo=true"

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        r = client.get(public_url)
        r.raise_for_status()
        # Capture the final resolved URL after any redirects
        final_url = str(r.url)

    path = out_dir / f"{uuid.uuid4().hex}.png"
    path.write_bytes(r.content)
    return path, final_url
