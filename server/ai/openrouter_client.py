"""OpenRouter API client — used for vision/image analysis (free tier available)."""
import httpx

from config import OPENROUTER_API_KEY

_BASE = "https://openrouter.ai/api/v1/chat/completions"
_VISION_MODEL = "google/gemma-4-27b-it:free"
_TIMEOUT = 30.0


def is_enabled() -> bool:
    return bool(OPENROUTER_API_KEY)


async def vision_chat(
    *,
    image_b64: str,
    media_type: str = "image/jpeg",
    text: str,
    system: str = "",
    temperature: float = 0.5,
    max_tokens: int = 1024,
) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
            {"type": "text", "text": text},
        ],
    })

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            _BASE,
            json={"model": _VISION_MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
        )

    if r.status_code != 200:
        raise RuntimeError(f"OpenRouter returned {r.status_code}: {r.text[:300]}")

    data = r.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected OpenRouter response: {data}") from e
