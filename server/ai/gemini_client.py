"""Google Gemini API client — used for vision/image analysis."""
import base64
import httpx

from config import GEMINI_API_KEY

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_VISION_MODEL = "gemini-2.0-flash"
_TIMEOUT = 30.0


def is_enabled() -> bool:
    return bool(GEMINI_API_KEY)


async def vision_chat(
    *,
    image_b64: str,
    media_type: str = "image/jpeg",
    text: str,
    system: str = "",
    temperature: float = 0.5,
    max_tokens: int = 1024,
) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    parts = []
    if system:
        parts.append({"text": system + "\n\n"})
    parts.append({"inline_data": {"mime_type": media_type, "data": image_b64}})
    parts.append({"text": text})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }

    url = f"{_BASE}/{_VISION_MODEL}:generateContent?key={GEMINI_API_KEY}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(url, json=payload)

    if r.status_code != 200:
        raise RuntimeError(f"Gemini returned {r.status_code}: {r.text[:300]}")

    data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Gemini response: {data}") from e
