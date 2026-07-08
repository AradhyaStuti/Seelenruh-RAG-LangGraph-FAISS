# Cross-encoder reranker. Scores each (query, chunk) pair and returns top-k.
# Improves result quality but adds 200-400ms. Set RERANKER_ENABLED=1 in .env to turn on.
# If it times out (> RERANKER_TIMEOUT_S seconds), we fall back to the FAISS order.
import asyncio
from typing import Optional

from sentence_transformers import CrossEncoder

from config import RERANKER_MODEL, RERANKER_ENABLED
from logger import get_logger

log = get_logger("reranker")

RERANKER_TIMEOUT_S = 3.0  # if reranking takes longer than this, skip it

_model: Optional[CrossEncoder] = None


def _get() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(RERANKER_MODEL)
    return _model


def is_enabled() -> bool:
    return RERANKER_ENABLED


def warmup() -> None:
    if RERANKER_ENABLED:
        _get().predict([("warmup", "warmup")])


async def rerank(query: str, candidates: list[dict], k: int) -> list[dict]:
    if not RERANKER_ENABLED or not candidates:
        return candidates[:k]
    pairs = [(query, c["text"]) for c in candidates]
    try:
        scores = await asyncio.wait_for(
            asyncio.to_thread(_get().predict, pairs),
            timeout=RERANKER_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        log.warning("reranker timed out, using FAISS order", timeout_s=RERANKER_TIMEOUT_S)
        return candidates[:k]
    for c, s in zip(candidates, scores):
        c["rerank_score"] = float(s)
    candidates.sort(key=lambda c: c["rerank_score"], reverse=True)
    return candidates[:k]
