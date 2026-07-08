# Two-stage retrieval: FAISS for candidates, cross-encoder for reranking.
import asyncio
import re
import time
from datetime import date
from typing import Optional

from rag import embedder, reranker
from rag.knowledge import CHUNKS
from rag.store import VectorStore
from config import RETRIEVAL_TOP_K, RETRIEVAL_OVERFETCH
from logger import get_logger

log = get_logger("retriever")


_HINGLISH_MAP = {
    # common Hinglish contractions / misspellings → clean English equivalents
    "kaise": "how to", "karu": "do", "kru": "do", "karein": "how to",
    "karna": "to do", "kya": "what", "mera": "my", "mere": "my",
    "mujhe": "me", "chahiye": "need", "milega": "get", "milegi": "get",
    "nahi": "not", "hai": "is", "hain": "are", "tha": "was",
    "apply": "apply", "form": "form", "yojana": "scheme", "sarkari": "government",
    "madad": "help", "paisa": "money", "paise": "money", "rupaye": "rupees",
    "lakh": "lakh", "hazaar": "thousand", "card": "card", "banwana": "make",
    "eligible": "eligible", "laabh": "benefit", "labh": "benefit",
    "abhi": "now", "jaldi": "urgently", "please": "please",
    "aaj": "today", "kal": "tomorrow", "mahina": "month",
}

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]+")


def _normalize_query(text: str) -> str:
    """Clean OCR artifacts and lightly expand Hinglish terms for better embedding coverage."""
    text = re.sub(r" {2,}", " ", text)
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff")
    text = text.replace("ﬃ", "ffi").replace("ﬄ", "ffl")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Remove pure Devanagari tokens — multilingual-e5 handles them natively;
    # keeping them avoids OOV but we don't expand them here.
    # Expand common Hinglish words to their English equivalents for better
    # semantic matching against English knowledge chunks.
    tokens = text.split()
    expanded = []
    for tok in tokens:
        lower = tok.lower().rstrip("?!.,;:")
        if lower in _HINGLISH_MAP and not _DEVANAGARI_RE.search(tok):
            expanded.append(_HINGLISH_MAP[lower])
        else:
            expanded.append(tok)
    return " ".join(expanded).strip()

_STALE_MONTHS_WARN = 3    # penalty starts here (lowered — laws/schemes change fast)
_STALE_MONTHS_HEAVY = 9   # heavier penalty after 9 months


def _staleness_penalty(chunk: dict) -> float:
    """Penalise old chunks so fresher ones rank higher when content is otherwise similar."""
    lv = chunk.get("lastVerifiedOn")
    if not lv:
        return 0.0
    try:
        months_old = (date.today() - date.fromisoformat(str(lv))).days / 30.44
        if months_old > _STALE_MONTHS_HEAVY:
            return 0.15
        if months_old > _STALE_MONTHS_WARN:
            return 0.08
        return 0.0
    except Exception:
        return 0.0

_store = VectorStore()
_ready = False
_write_lock = asyncio.Lock()


async def init() -> None:
    """Build or load the FAISS index."""
    global _ready
    if _ready:
        return

    if _store.load() and _store.size() == len(CHUNKS):
        log.info("loaded from cache", chunks=_store.size())
        _ready = True
        return

    log.info("building index", chunks=len(CHUNKS))
    t0 = time.time()
    texts = [f"passage: {c['topic']}\n{c['text']}" for c in CHUNKS]
    vectors = await asyncio.to_thread(embedder.embed_many, texts)
    _store.build(CHUNKS, vectors)
    _store.save()
    log.info("index built", chunks=_store.size(), ms=int((time.time() - t0) * 1000))
    _ready = True


async def warmup() -> None:
    """Preload models so the first request isn't slow."""
    if not embedder.is_loaded():
        t0 = time.time()
        await asyncio.to_thread(embedder.warmup)
        log.info("embedder warmed", ms=int((time.time() - t0) * 1000))
    if reranker.is_enabled():
        t0 = time.time()
        await asyncio.to_thread(reranker.warmup)
        log.info("reranker warmed", ms=int((time.time() - t0) * 1000))


def is_ready() -> bool:
    return _ready


async def delete(chunk_ids: list[str]) -> int:
    """Soft-delete chunks. Triggers compaction if deleted vectors exceed 30%."""
    async with _write_lock:
        removed = _store.delete_chunks(chunk_ids)
    if removed and _store.should_compact():
        asyncio.create_task(_compact_background())
    return removed


async def _compact_background() -> None:
    """Rebuild index in a worker thread to physically evict deleted vectors."""
    async with _write_lock:
        try:
            log.info("compaction triggered")
            await asyncio.to_thread(_store.rebuild, embedder.embed_many)
        except Exception as err:
            log.error("compaction failed", error=str(err))


async def ingest(chunks: list[dict]) -> int:
    """Add chunks to the live FAISS index. Each chunk needs: id, domain, topic, text."""
    if not chunks:
        return 0
    if not _ready:
        await init()
    texts = [f"passage: {c['topic']}\n{c['text']}" for c in chunks]
    vectors = await asyncio.to_thread(embedder.embed_many, texts)
    async with _write_lock:
        _store.add_items(chunks, vectors)
    log.info("ingested chunks", added=len(chunks), total=_store.size())
    return len(chunks)


async def retrieve(query: str, *, domain: Optional[str] = None, k: int = RETRIEVAL_TOP_K) -> list[dict]:
    if not _ready:
        await init()
    query = _normalize_query(query)
    qv = await asyncio.to_thread(embedder.embed_one, f"query: {query}")
    fetch_k = max(k, RETRIEVAL_OVERFETCH) if reranker.is_enabled() else k
    candidates = _store.search(qv, k=fetch_k, domain=domain)

    for c in candidates:
        penalty = _staleness_penalty(c)
        if penalty:
            c["score"] = max(0.0, c["score"] - penalty)
            c["_stale_penalty"] = penalty
    candidates.sort(key=lambda c: c["score"], reverse=True)

    if reranker.is_enabled() and len(candidates) > k:
        return await reranker.rerank(query, candidates, k=k)
    return candidates[:k]
