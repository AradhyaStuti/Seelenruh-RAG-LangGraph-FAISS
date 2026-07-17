"""Try Groq first, then fall back to Ollama or Anthropic when needed."""
import json
import time

from ai import groq_client, ollama_client, anthropic_client
from ai.circuit_breaker import groq_breaker, ollama_breaker, anthropic_breaker
from logger import get_logger

log = get_logger("provider")

_cached_ollama_up: bool | None = None
_last_check: float = 0.0


async def _ollama_up() -> bool:
    global _cached_ollama_up, _last_check
    now = time.time()
    if _cached_ollama_up is not None and now - _last_check < 30:
        return _cached_ollama_up
    _cached_ollama_up = await ollama_client.available()
    _last_check = now
    return _cached_ollama_up


def _is_fallback_worthy(err: Exception) -> bool:
    status = getattr(err, "status", None)
    if status == 429 or (status and status >= 500):
        return True
    msg = str(err).lower()
    return any(s in msg for s in ("timeout", "timed out", "econnreset", "fetch failed", "network", "enotfound", "circuit open"))


async def chat(**opts) -> dict:
    # 1. Groq (with circuit breaker + timeout)
    try:
        content = await groq_breaker.call(groq_client.chat, **opts)
        return {"content": content, "via": "groq"}
    except Exception as err:
        if not _is_fallback_worthy(err):
            raise
        log.warning("groq unavailable", error=type(err).__name__, next="ollama")

    # 2. Ollama (local)
    if await _ollama_up():
        try:
            content = await ollama_breaker.call(ollama_client.chat, **opts)
            return {"content": content, "via": "ollama"}
        except Exception as err:
            log.warning("ollama failed", error=str(err), next="anthropic")

    # 3. Anthropic (cloud fallback)
    if anthropic_client.is_enabled():
        try:
            content = await anthropic_breaker.call(anthropic_client.chat, **opts)
            return {"content": content, "via": "anthropic"}
        except Exception as err:
            log.error("anthropic fallback failed", error=str(err))

    raise _AllProvidersFailed()


# ---------------------------------------------------------------------------
# Graceful offline response — returned instead of a 500 error when every
# provider is down. Gives users actionable guidance and emergency contacts.
# ---------------------------------------------------------------------------

class _AllProvidersFailed(RuntimeError):
    """Sentinel so callers can distinguish a provider outage from a logic error."""
    def __init__(self):
        super().__init__("All LLM providers are currently unavailable.")


_OFFLINE_RESPONSE = (
    "I'm temporarily unable to connect to my AI systems right now. "
    "All of Seelenruh's AI providers appear to be unavailable at this moment.\n\n"
    "**While you wait, here are some immediate resources:**\n\n"
    "- **Mental health crisis (India):** iCall — 9152987821 | Tele-MANAS — 14416 | Vandrevala — 1860-2662-345\n"
    "- **Emergency (India):** Police / Ambulance / Fire — 112\n"
    "- **Women's helpline (India):** 181\n"
    "- **Cyber crime (India):** 1930 or cybercrime.gov.in\n"
    "- **NALSA (free legal aid):** 15100\n\n"
    "Please try sending your message again in a moment. "
    "If the issue persists, the service may be experiencing a temporary outage."
)


async def chat_safe(**opts) -> dict:
    """Like `chat()` but returns a graceful offline message instead of raising when all providers fail."""
    try:
        return await chat(**opts)
    except _AllProvidersFailed:
        log.error("all providers down — returning offline response")
        return {"content": _OFFLINE_RESPONSE, "via": "offline-fallback"}


async def chat_json(**opts) -> dict:
    # 1. Groq
    try:
        data = await groq_breaker.call(groq_client.chat_json, **opts)
        return {"data": data, "via": "groq"}
    except Exception as err:
        if not _is_fallback_worthy(err):
            raise
        log.warning("groq json unavailable", next="ollama")

    # 2. Ollama
    if await _ollama_up():
        try:
            raw = await ollama_breaker.call(ollama_client.chat, **opts, json_mode=True)
            return {"data": json.loads(raw), "via": "ollama"}
        except Exception:
            pass

    # 3. Anthropic
    if anthropic_client.is_enabled():
        try:
            raw = await anthropic_breaker.call(anthropic_client.chat, **opts, json_mode=True)
            return {"data": json.loads(raw), "via": "anthropic"}
        except Exception as err:
            log.error("anthropic json fallback failed", error=str(err))

    raise RuntimeError("All LLM providers failed. Please try again later.")
