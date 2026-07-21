"""Groq SDK wrapper. Exposes chat and chat_json — the
provider layer wraps these with auto-fallback."""
import json
from typing import AsyncIterator

from groq import AsyncGroq, APIStatusError

from config import GROQ_API_KEY, GROQ_MODEL_FAST

_client: AsyncGroq | None = None


def _get() -> AsyncGroq:
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set")
        _client = AsyncGroq(api_key=GROQ_API_KEY)
    return _client


class GroqError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


async def chat(*, messages: list[dict], model: str | None = None, temperature: float = 0.7,
               max_tokens: int = 1024, json_mode: bool = False) -> str:
    try:
        resp = await _get().chat.completions.create(
            model=model or GROQ_MODEL_FAST,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"} if json_mode else None,
        )
        return (resp.choices[0].message.content or "").strip()
    except APIStatusError as err:
        raise GroqError(str(err), status=err.status_code) from err


async def chat_json(*, messages: list[dict], model: str | None = None, temperature: float = 0.2) -> dict:
    raw = await chat(messages=messages, model=model, temperature=temperature, json_mode=True)
    return json.loads(raw)


_GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


async def vision_chat(
    *,
    image_b64: str,
    media_type: str = "image/jpeg",
    text: str,
    system: str = "",
    temperature: float = 0.5,
    max_tokens: int = 1024,
) -> str:
    """Send an image + text to Groq's vision model (llama-4-scout)."""
    user_content: list[dict] = [
        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
        {"type": "text", "text": text},
    ]
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_content})
    try:
        resp = await _get().chat.completions.create(
            model=_GROQ_VISION_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
    except APIStatusError as err:
        raise GroqError(str(err), status=err.status_code) from err


async def stream_chat(
    *,
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 900,
) -> AsyncIterator[str]:
    """Yield text tokens one by one as Groq streams them."""
    try:
        stream = await _get().chat.completions.create(
            model=model or GROQ_MODEL_FAST,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except APIStatusError as err:
        raise GroqError(str(err), status=err.status_code) from err


