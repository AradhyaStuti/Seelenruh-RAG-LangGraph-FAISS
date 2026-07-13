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
    # legal Hinglish — rights and general
    "adhikar": "rights", "aadhikar": "rights", "kanoon": "law", "kanooni": "legal",
    "samasya": "problem", "shikayat": "complaint", "darj": "file register",
    "girftari": "arrest", "giraftaar": "arrested", "bail": "bail",
    "vakeel": "lawyer", "vkeel": "lawyer", "adalat": "court",
    "muavza": "compensation", "muaawza": "compensation damages",
    "zameen": "land property", "makaan": "house property",
    "hak": "right entitlement", "insaaf": "justice", "nyaay": "justice",
    "nyay": "justice", "sunawaai": "hearing", "faisla": "judgment decision",
    "faislaa": "judgment decision",
    # family law Hinglish
    "talaq": "divorce Muslim", "talaak": "divorce Muslim",
    "khula": "divorce Muslim wife initiated",
    "nafaqa": "maintenance alimony Muslim", "nafaka": "maintenance alimony Muslim",
    "mehr": "mahr dower Muslim marriage",
    "gawah": "witness evidence testimony", "gawaah": "witness evidence",
    "wasiyat": "will testament inheritance",
    "waris": "legal heir successor", "vaaris": "legal heir",
    "muqadma": "case lawsuit complaint registered",
    # property and housing
    "kiraya": "rent payment", "kiraaya": "rent",
    "kirayedaar": "tenant renter", "kiraydar": "tenant",
    "makan maalik": "landlord", "makaanmaalik": "landlord",
    "ghar se nikaala": "eviction evicted illegally",
    "bahar kar diya": "evicted thrown out illegal",
    "daakhil karo": "file submit application",
    "zameen ka hak": "land rights property ownership",
    # employment Hinglish
    "tankhwaah": "salary wages", "tankha": "salary wages",
    "tankhah": "salary wages", "talab": "salary wages",
    "salary nahi mili": "unpaid wages salary withheld",
    "naukri gayi": "job terminated dismissed",
    "mazdoor": "worker labour employee",
    "thekedar": "contractor employer",
    # crime and fraud
    "dhoka": "fraud cheated deceived",
    "thagi": "fraud scam cheated",
    "dhamki": "threat intimidation",
    "takleef": "harassment trouble",
    "pareshaan": "harassed troubled",
    "pareshan": "harassed troubled",
    "nakli": "fake forged counterfeit",
    "jhooth": "false fabricated",
    "jhuta": "false fabricated",
    # accident and insurance
    "durghatna": "accident motor vehicle",
    "hadsa": "accident incident",
    "bima": "insurance claim",
    "haadsa": "accident",
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
    (re.compile(r"husband|wife|spouse|(?<!business )partner.{0,30}(beat|hit|hurt|abuse|slap|kick|threaten|violence|assault|torture)", re.I),
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
    (re.compile(r"sexual harass|workplace harass|POSH|internal complaints committee|\bICC\b.{0,20}(complaint|harass|work)", re.I),
     "POSH Act Internal Complaints Committee ICC workplace harassment employer obligation SHe-Box LCC"),
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
    (re.compile(r"(contract|agreement|MOU).{0,30}(breach|violat|not paid|default|cancel|refuse).{0,20}|(freelanc|gig worker).{0,30}(payment|not paid|dispute)", re.I),
     "Indian Contract Act 1872 breach of contract Section 73 damages Specific Relief Act specific performance legal notice civil suit arbitration"),
    (re.compile(r"(inherit|succession|ancestral property|coparcen|after (death|demise)).{0,40}(property|asset|share|claim|will)|(will.{0,20}(contest|invalid|challeng|dispute)|probate|letters of administration)", re.I),
     "Hindu Succession Act 2005 intestate succession Section 8 legal heir succession certificate probate court ancestral property coparcener Vineeta Sharma 2020"),
    (re.compile(r"(doctor|hospital|surgeon|nurse).{0,30}(mistake|negligen|wrong|error|malpractice|died|death|injury|misdiagnos)|(medical negligen|wrong surgery|wrong medicine)", re.I),
     "medical negligence Consumer Protection Act 2019 IMC Act Jacob Mathew 2005 gross negligence standard of care District Consumer Commission state medical council"),
    (re.compile(r"senior citizen.{0,30}(property|house|flat|gift|transfer|son|daughter)|section 23.{0,20}senior|parents.{0,30}(throw|evict|abandon|neglect|not caring)", re.I),
     "Senior Citizens Act 2007 Section 23 property revocation Maintenance Tribunal SDM voidable transfer elder abuse"),
    (re.compile(r"(PF|provident fund|EPF|EPFO).{0,30}(not (deposit|paid|credited)|deduct|missing|claim)|gratuity.{0,30}(not paid|deny|withhold|entitl)|(ESI|ESIC).{0,20}(benefit|claim|hospital)", re.I),
     "Code on Social Security 2020 EPF ESIC gratuity EPFO regional office Payment of Gratuity Act 5 years continuous service"),
    (re.compile(r"gig worker|platform worker|delivery (agent|boy|partner)|app.{0,20}(deactivat|block|terminat)|freelanc.{0,20}(labour|social security|provident)", re.I),
     "Code on Social Security 2020 gig platform worker aggregator social security benefits e-Shram registration"),
    (re.compile(r"maternity.{0,20}(leave|benefit|pay|job|fired|terminat)|pregnant.{0,20}(fired|terminat|leave|benefit)", re.I),
     "Maternity Benefit Act 1961 26 weeks paid leave prohibition of dismissal during maternity Code on Social Security employer obligation"),
    (re.compile(r"(data.{0,15}(breach|leak|stolen|hacked|misuse)|personal data.{0,20}(share|sold|expose)|privacy.{0,20}(violat|data))", re.I),
     "Digital Personal Data Protection Act 2023 DPDP Act Data Protection Board Data Fiduciary consent right to erasure IT Act Section 43A CERT-In"),
    (re.compile(r"(road|traffic|vehicle|car|bike|truck|bus).{0,30}(accident|crash|collision|hit)|motor accident claim|MACT|(hit.{0,10}run|third.{0,10}party insurance)", re.I),
     "Motor Vehicles Act 1988 Motor Accident Claims Tribunal MACT Section 166 no fault liability Section 140 third party insurance Solatium Fund Solatium Scheme"),
    (re.compile(r"(traffic challan|drunk driving|over.?speeding|helmet|seatbelt).{0,20}(fine|penalty|offence|notice)|(driving licence|DL|RC).{0,20}(suspend|cancel|renew)", re.I),
     "Motor Vehicles Act 1988 amended 2019 traffic fine penalty parivahan.gov.in driving licence renewal"),
    (re.compile(r"(child|minor|kid).{0,30}(custody|guardian|live with|stay with|take away|take back)|(custody.{0,20}(husband|wife|mother|father|parent))", re.I),
     "Guardians and Wards Act 1890 Hindu Minority Guardianship Act custody welfare of child Family Court interim custody visitation rights"),
    (re.compile(r"(school.{0,20}(admission|denied|reject|fees)|EWS.{0,20}(seat|quota|admission)|25%.{0,20}(quota|reservation|school))", re.I),
     "Right to Education Act 2009 RTE Section 12 25 percent EWS disadvantaged group free admission private school reimbursement"),
    (re.compile(r"(school.{0,20}(beat|hit|punish|cane|abuse)|teacher.{0,20}(beat|hit|assault|harass)|child.{0,20}(punish|abuse).{0,20}school)", re.I),
     "RTE Act Section 17 prohibition physical punishment NCPCR SCPCR complaint District Education Officer"),
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
    if domain == "Legal":
        return max(base, 25)  # larger candidate pool — legal chunks are dense and wording matters
    if domain == "Government Schemes":
        return max(base, 20)
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
