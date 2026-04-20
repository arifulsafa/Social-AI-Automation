"""
Nano Banana image client — Google's gemini-2.5-flash-image model.

Uses the Gemini REST API directly so we don't pull the full google-genai SDK.
Returns a local file path to the generated PNG.
"""
from __future__ import annotations

import base64
import time
import uuid
from pathlib import Path

import httpx

from src.config import settings

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_RETRY_DELAYS = [60, 120, 180]  # seconds between retries on 429 (free-tier RPM is very low)


def generate_image(prompt: str, *, out_dir: Path | None = None) -> Path:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not set in .env")

    out_dir = out_dir or settings.image_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    url = _ENDPOINT.format(model=settings.nano_banana_model)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        # responseModalities is required for image output on flash-image.
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    headers = {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}

    last_err: Exception | None = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(url, json=payload, headers=headers)
                if r.status_code == 429:
                    last_err = RuntimeError(f"429 rate limited (attempt {attempt + 1})")
                    continue
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPStatusError as e:
            last_err = e
            continue

        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    img_bytes = base64.b64decode(inline["data"])
                    path = out_dir / f"{uuid.uuid4().hex}.png"
                    path.write_bytes(img_bytes)
                    return path

        raise RuntimeError(f"Nano Banana returned no image. Full response: {data}")

    raise RuntimeError(f"Nano Banana failed after retries: {last_err}")
