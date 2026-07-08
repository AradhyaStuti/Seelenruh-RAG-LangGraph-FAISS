"""Ollama HTTP client — local LLM fallback when Groq is rate-limited."""
import json
from typing import AsyncIterator

import httpx

from config import OLLAMA_URL, OLLAMA_MODEL


class OllamaError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


async def chat(*, messages: list[dict], model: str | None = None, temperature: float = 0.7,
               max_tokens: int = 1024, json_mode: bool = False) -> str:
    body = {
        "model": model or OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if json_mode:
        body["format"] = "json"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/chat", json=body)
        if resp.status_code >= 400:
            raise OllamaError(resp.text, status=resp.status_code)
        return (resp.json().get("message", {}).get("content") or "").strip()


async def stream_chat(
    *,
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 900,
) -> AsyncIterator[str]:
    """Yield text tokens one by one from Ollama's streaming API."""
    body = {
        "model": model or OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=body) as resp:
            if resp.status_code >= 400:
                body_bytes = await resp.aread()
                raise OllamaError(body_bytes.decode(errors="replace"), status=resp.status_code)
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                delta = (data.get("message") or {}).get("content", "")
                if delta:
                    yield delta
                if data.get("done"):
                    break


async def available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False
