"""Trim older chat history so the prompt stays within a token budget."""
import os
from logger import get_logger

log = get_logger("context")

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False

MAX_HISTORY_TOKENS = int(os.getenv("MAX_HISTORY_TOKENS", "6000"))


def _count_tokens(text: str) -> int:
    if _TIKTOKEN_AVAILABLE:
        return len(_enc.encode(text, disallowed_special=()))
    # Rough fallback: ~4 chars per token
    return len(text) // 4


def count_messages_tokens(messages: list[dict]) -> int:
    """Estimate token usage of an OpenAI-style messages list."""
    total = 0
    for m in messages:
        total += 4  # per-message overhead (role + delimiters)
        total += _count_tokens(m.get("content") or "")
    total += 2  # reply primer
    return total


def trim_history(
    history: list[dict],
    *,
    budget: int = MAX_HISTORY_TOKENS,
    keep_last: int = 2,
) -> list[dict]:
    """Drop older messages until the history fits within the requested budget."""
    if not history:
        return history

    tail = history[-keep_last:] if len(history) >= keep_last else history[:]
    candidates = history[:-keep_last] if len(history) > keep_last else []

    while candidates and count_messages_tokens(candidates + tail) > budget:
        candidates.pop(0)

    trimmed = candidates + tail
    dropped = len(history) - len(trimmed)
    if dropped:
        log.info("history trimmed", dropped=dropped, budget=budget)
    return trimmed
