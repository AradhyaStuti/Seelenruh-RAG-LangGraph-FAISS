"""Anthropic API client via httpx — no anthropic SDK needed.

Used as a third LLM fallback when both Groq and Ollama are unavailable.
Supports the same interface as groq_client.chat() so provider.py can call it
transparently.
"""
import json
from typing import AsyncIterator

import httpx

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_TIMEOUT = 60.0
_API_VERSION = "2023-06-01"


def is_enabled() -> bool:
    return bool(ANTHROPIC_API_KEY)


def _groq_to_anthropic(messages: list[dict]) -> tuple[str, list[dict]]:
    """Convert OpenAI-style messages (with system) to Anthropic format.

    Anthropic expects `system` as a top-level string and `messages` without
    system entries. Multiple consecutive system messages are merged.
    """
    system_parts: list[str] = []
    converted: list[dict] = []
    for m in messages:
        if m["role"] == "system":
            system_parts.append(m["content"])
        else:
            converted.append({"role": m["role"], "content": m["content"]})
    return "\n\n".join(system_parts), converted


async def chat(
    *,
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    json_mode: bool = False,
) -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    system_prompt, anthropic_messages = _groq_to_anthropic(messages)
    if json_mode:
        system_prompt = (system_prompt + "\n\nRespond with valid JSON only.").strip()

    payload: dict = {
        "model": model or ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": anthropic_messages,
    }
    if system_prompt:
        payload["system"] = system_prompt

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            _ANTHROPIC_URL,
            json=payload,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": _API_VERSION,
                "Content-Type": "application/json",
            },
        )

    if r.status_code != 200:
        raise RuntimeError(f"Anthropic returned {r.status_code}: {r.text[:300]}")

    data = r.json()
    content = data.get("content", [{}])
    text = content[0].get("text", "").strip() if content else ""
    return text


async def stream_chat(
    *,
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 900,
) -> AsyncIterator[str]:
    """Yield text tokens one by one from Anthropic's streaming API."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    system_prompt, anthropic_messages = _groq_to_anthropic(messages)
    payload: dict = {
        "model": model or ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": anthropic_messages,
        "stream": True,
    }
    if system_prompt:
        payload["system"] = system_prompt

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            _ANTHROPIC_URL,
            json=payload,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": _API_VERSION,
                "Content-Type": "application/json",
            },
        ) as resp:
            if resp.status_code != 200:
                body_bytes = await resp.aread()
                raise RuntimeError(f"Anthropic returned {resp.status_code}: {body_bytes[:300]}")
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:]
                if raw.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                if data.get("type") == "content_block_delta":
                    delta = (data.get("delta") or {}).get("text", "")
                    if delta:
                        yield delta
