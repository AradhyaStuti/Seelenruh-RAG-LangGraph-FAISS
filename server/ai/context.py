"""Token-aware context window management.

Uses tiktoken (cl100k_base) as a conservative token counter — the actual
Llama tokeniser is slightly different but cl100k tends to overcount, which
means we leave a safe headroom before the model's context limit.

The budget defaults to 6000 tokens for the history block. Groq's
llama-3.3-70b has a 128k context window but adding retrieved chunks,
the system prompt, and the current query on top of history can easily
push past 8k. 6000 for history leaves comfortable room for everything else.
"""
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
    """Remove the oldest messages until the history fits within `budget` tokens.

    Always preserves the last `keep_last` messages so the model always has
    immediate context for the current exchange.

    Args:
        history:   list of {"role": ..., "content": ...} dicts, oldest first.
        budget:    maximum tokens for the history block.
        keep_last: minimum number of tail messages to always keep.

    Returns:
        Possibly-shorter list (oldest entries dropped first).
    """
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
