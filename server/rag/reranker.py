# Cross-encoder reranker. Scores each (query, chunk) pair and returns top-k.
# Improves result quality but adds 200-400ms. Set RERANKER_ENABLED=1 in .env to turn on.
# If it times out (> RERANKER_TIMEOUT_S seconds), we fall back to the FAISS order.
import asyncio
import hashlib
import json
from functools import lru_cache
from typing import Optional

from sentence_transformers import CrossEncoder

from config import RERANKER_MODEL, RERANKER_ENABLED
from logger import get_logger

log = get_logger("reranker")

RERANKER_TIMEOUT_S = 3.0  # if reranking takes longer than this, skip it

# ms-marco-MiniLM-L-6-v2 raw score floor below which a chunk is considered
# too irrelevant to include. Only applied when enough better chunks exist.
# Equivalent to "this chunk shares almost no information with the query."
_MIN_RERANK_SCORE = -5.0

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


# ---------------------------------------------------------------------------
# Score cache — avoids re-scoring the same (query, chunk_ids) pair
# within a server process.  Sized to hold ~256 unique query contexts.
# ---------------------------------------------------------------------------
def _cache_key(query: str, candidates: list[dict]) -> str:
    """Stable hash of query + ordered candidate IDs + text snippets."""
    payload = query + "|" + "|".join(
        f"{c.get('id', '')}:{c.get('text', '')[:60]}" for c in candidates
    )
    return hashlib.sha256(payload.encode()).hexdigest()


@lru_cache(maxsize=256)
def _cached_scores(cache_key: str, pairs_json: str) -> tuple[float, ...]:
    """Synchronous inner call — wrapped by lru_cache on (key, pairs_json)."""
    pairs: list[list[str]] = json.loads(pairs_json)
    raw_scores = _get().predict(pairs)
    return tuple(float(s) for s in raw_scores)


async def rerank(query: str, candidates: list[dict], k: int) -> list[dict]:
    if not RERANKER_ENABLED or not candidates:
        return candidates[:k]
    # Include topic as a high-signal prefix — it is a human-curated summary of the chunk
    # and dramatically improves relevance scoring for topically-named chunks.
    pairs = [(query, f"{c.get('topic', '')} {c['text']}") for c in candidates]

    key = _cache_key(query, candidates)
    pairs_json = json.dumps(pairs)

    try:
        scores: tuple[float, ...] = await asyncio.wait_for(
            asyncio.to_thread(_cached_scores, key, pairs_json),
            timeout=RERANKER_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        log.warning("reranker timed out, using FAISS order", timeout_s=RERANKER_TIMEOUT_S)
        return candidates[:k]

    for c, s in zip(candidates, scores):
        c["rerank_score"] = s
    candidates.sort(key=lambda c: c["rerank_score"], reverse=True)

    # Filter chunks whose score falls below the minimum threshold, but always
    # return at least min(k, 3) results so the LLM has something to work with.
    min_keep = min(k, 3)
    above = [c for c in candidates if c["rerank_score"] >= _MIN_RERANK_SCORE]
    if len(above) >= min_keep:
        return above[:k]
    return candidates[:k]
