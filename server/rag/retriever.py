# Two-stage retrieval: FAISS for candidates, cross-encoder for reranking.
import asyncio
import re
import time
from typing import Optional

from rag import embedder, reranker
from rag.knowledge import CHUNKS
from rag.knowledge_meta import enrich_chunk
from rag.store import VectorStore
from config import RETRIEVAL_TOP_K, RETRIEVAL_OVERFETCH
from logger import get_logger

log = get_logger("retriever")


_HINGLISH_MAP = {
    # common Hinglish contractions / misspellings → clean English equivalents
    "kaise": "how to", "karu": "do", "kru": "do", "karein": "how to",
    "karna": "to do", "kya": "what", "mera": "my", "mere": "my",
    "mujhe": "me", "chahiye": "need", "milega": "get", "milegi": "get",
    "nahi": "not", "nahin": "not", "hai": "is", "hain": "are", "tha": "was",
    "apply": "apply", "form": "form", "yojana": "scheme", "sarkari": "government",
    "madad": "help", "paisa": "money", "paise": "money", "rupaye": "rupees",
    "lakh": "lakh", "hazaar": "thousand", "card": "card", "banwana": "make",
    "eligible": "eligible", "laabh": "benefit", "labh": "benefit",
    "abhi": "now", "jaldi": "urgently", "please": "please",
    "aaj": "today", "kal": "tomorrow", "mahina": "month",
    # legal Hinglish
    "adhikar": "rights", "aadhikar": "rights", "kanoon": "law", "kanooni": "legal",
    "samasya": "problem", "shikayat": "complaint", "darj": "file register",
    "girftari": "arrest", "bail": "bail", "vakeel": "lawyer", "adalat": "court",
    "muavza": "compensation", "zameen": "land property", "makaan": "house property",
    # scheme Hinglish
    "berojgar": "unemployed unemployment", "naukri": "job employment",
    "kisan": "farmer agriculture", "garib": "poor poverty",
    "penshn": "pension", "ration": "ration food",
    "awas": "housing shelter", "bijli": "electricity",
    "paani": "water", "shauchalay": "toilet sanitation",
}

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]+")

# Legal query expansion — appends domain-specific terminology before embedding
# so vague natural-language queries map to the right knowledge chunks.
# Each tuple: (compiled regex pattern, extra terms to append)
_LEGAL_EXPANSIONS: list[tuple] = [
    (re.compile(r"husband|wife|spouse|partner.{0,30}(beat|hit|hurt|abuse|slap|kick|threaten|violence|assault|torture)", re.I),
     "domestic violence PWDVA protection order Section 18 DV Act BNS 85 498A shelter home"),
    (re.compile(r"(beat|hit|hurt|abuse|slap|violence|assault).{0,30}(husband|wife|spouse|partner|family|in-law)", re.I),
     "domestic violence PWDVA BNS 85 498A cruelty protection order"),
    (re.compile(r"dowry", re.I),
     "dowry Prohibition Act BNS 80 dowry death BNS 85 cruelty 498A Section 304B"),
    (re.compile(r"cheque.{0,15}(bounce|return|dishonour|dishonor)", re.I),
     "Section 138 Negotiable Instruments Act criminal offence magistrate demand notice 30 days"),
    (re.compile(r"FIR.{0,20}(refuse|not|register|denied|won.t)", re.I),
     "Section 154 BNSS 173 mandatory registration magistrate Section 156(3) SP complaint"),
    (re.compile(r"landlord.{0,30}(evict|leave|throw|illegal)", re.I),
     "Transfer of Property Act rent control eviction notice tenant rights 15 days"),
    (re.compile(r"(fired|terminated|dismissed|sacked).{0,30}(job|work|employ|company)", re.I),
     "Industrial Disputes Act retrenchment wrongful termination labour court gratuity notice pay"),
    (re.compile(r"sexual harass|workplace harass|POSH", re.I),
     "POSH Act Internal Complaints Committee ICC workplace harassment employer obligation"),
    (re.compile(r"\brti\b|right to information", re.I),
     "RTI Act Section 6 CPIO Public Information Officer 30 days first appeal second appeal CIC"),
    (re.compile(r"consumer.{0,20}(complain|fraud|defect|cheat|scam)", re.I),
     "Consumer Protection Act 2019 District Commission deficiency unfair trade practice Section 35"),
    (re.compile(r"\bbail\b|anticipatory bail|arrest", re.I),
     "BNSS 480 482 anticipatory bail non-bailable bailable offence sessions court surety"),
    (re.compile(r"(rape|sexual assault|molestation)", re.I),
     "BNS 64 65 66 POCSO special court FIR mandatory medical examination victim protection"),
    (re.compile(r"child.{0,20}(abuse|harm|exploit|traffick|labour)", re.I),
     "POCSO JJ Act child welfare committee special court mandatory reporting"),
    (re.compile(r"cyber.{0,20}(fraud|scam|hack|phish|black ?mail|stalk)", re.I),
     "IT Act Section 66 66C 66D 67 cybercrime.gov.in 1930 DPDP Act online fraud"),
    (re.compile(r"maintenance.{0,20}(wife|husband|child|parent)", re.I),
     "CrPC 125 BNSS 144 HMA Section 24 25 alimony interim maintenance family court"),
    (re.compile(r"\bdivorce\b|talaq|khula|dissolution of marriage", re.I),
     "Hindu Marriage Act Special Marriage Act dissolution Section 13 mutual consent contested divorce maintenance"),
    (re.compile(r"property.{0,20}(inherit|succession|share|will|partition)", re.I),
     "Hindu Succession Act Transfer of Property Act will partition civil court inheritance rights"),
    (re.compile(r"landlord|tenant|rent.{0,15}(dispute|increase|deposit|agreement)", re.I),
     "Transfer of Property Act rent control Rent Act tenant rights lease agreement eviction"),
    (re.compile(r"(police|officer).{0,20}(corrupt|bribe|harass|beat|threaten)", re.I),
     "police misconduct complaint SP Internal Complaints DGP human rights commission NHRC"),
    (re.compile(r"(illegal|wrongful|false).{0,20}arrest|arrest.{0,20}without", re.I),
     "BNSS fundamental rights Article 22 habeas corpus writ High Court custody remand"),
    (re.compile(r"(blackmail|extort|threaten).{0,30}(photo|video|nude|intimate|money)", re.I),
     "IT Act Section 67 67A cyber blackmail non-consensual intimate image 1930 cybercrime"),
    (re.compile(r"passport|visa.{0,20}(delay|refuse|cancel)", re.I),
     "passport grievance MEA passport seva RTI passport office"),
    (re.compile(r"senior citizen|elderly.{0,20}(rights|abuse|property|maintenance)", re.I),
     "Senior Citizens Act 2007 maintenance tribunal property rights elder abuse"),
    (re.compile(r"POCSO|minor.{0,20}(abuse|assault|harass|rape)", re.I),
     "POCSO special court child welfare committee mandatory reporting JJ Act"),
    (re.compile(r"writ|habeas corpus|mandamus|certiorari|Article 32|Article 226", re.I),
     "fundamental rights Constitution Article 32 High Court Supreme Court writ jurisdiction"),
]


def _expand_legal_query(query: str) -> str:
    """
    Append legal terminology to vague natural-language legal queries so that
    multilingual-e5-small maps them onto the right knowledge chunks.
    Only called when domain='Legal'. Pure string operation — no LLM needed.
    """
    additions: list[str] = []
    for pattern, expansion in _LEGAL_EXPANSIONS:
        if pattern.search(query):
            additions.append(expansion)
    if not additions:
        return query
    return query + " " + " ".join(additions)


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
    enriched = [enrich_chunk(c) for c in CHUNKS]
    texts = [f"passage: {c['topic']}\n{c['text']}" for c in enriched]
    vectors = await asyncio.to_thread(embedder.embed_many, texts)
    _store.build(enriched, vectors)
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
    chunks = [enrich_chunk(c) for c in chunks]
    texts = [f"passage: {c['topic']}\n{c['text']}" for c in chunks]
    vectors = await asyncio.to_thread(embedder.embed_many, texts)
    async with _write_lock:
        _store.add_items(chunks, vectors)
    log.info("ingested chunks", added=len(chunks), total=_store.size())
    return len(chunks)


def _overfetch_k(k: int, domain: Optional[str]) -> int:
    """Legal and scheme queries benefit from more candidates before reranking —
    they have denser knowledge chunks and small wording differences matter."""
    if not reranker.is_enabled():
        return k
    base = max(k, RETRIEVAL_OVERFETCH)
    if domain in ("Legal", "Government Schemes"):
        return max(base, 20)  # larger candidate pool for high-stakes domains
    return base


def _dedup(hits: list[dict]) -> list[dict]:
    """Remove near-duplicate chunks that share the same topic string.
    After reranking, higher-ranked chunks come first, so we keep the first
    occurrence of each topic and discard later ones with the same key."""
    seen: set[str] = set()
    out: list[dict] = []
    for h in hits:
        key = h.get("topic", "").lower().strip()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(h)
    return out


async def retrieve(query: str, *, domain: Optional[str] = None, k: int = RETRIEVAL_TOP_K) -> list[dict]:
    if not _ready:
        await init()
    query = _normalize_query(query)
    if domain == "Legal":
        query = _expand_legal_query(query)
    qv = await asyncio.to_thread(embedder.embed_one, f"query: {query}")
    fetch_k = _overfetch_k(k, domain)
    candidates = _store.search(qv, k=fetch_k, domain=domain)

    if reranker.is_enabled() and len(candidates) > k:
        results = await reranker.rerank(query, candidates, k=k)
    else:
        results = candidates[:k]

    return _dedup(results)
