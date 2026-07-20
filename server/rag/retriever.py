# Two-stage retrieval: FAISS dense + BM25 sparse hybrid, cross-encoder reranking.
import asyncio
from functools import lru_cache
import re
import time
from typing import Optional

try:
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    BM25Okapi = None  # type: ignore[assignment,misc]
    _BM25_AVAILABLE = False

from rag import embedder, reranker
from rag.knowledge import CHUNKS
from rag.knowledge_meta import enrich_chunk
from rag.store import VectorStore
from config import RETRIEVAL_TOP_K, RETRIEVAL_OVERFETCH, GROQ_MODEL_FAST
from logger import get_logger

log = get_logger("retriever")


# ---------------------------------------------------------------------------
# Query embedding cache — avoids re-encoding the same processed query string.
# 512 unique queries ≈ ~10 MB RAM at 384 dims × float32.
# ---------------------------------------------------------------------------

@lru_cache(maxsize=512)
def _embed_query_cached(query: str) -> tuple:
    """Synchronous embed — wrapped with lru_cache on the final query string.

    Returns a tuple (not numpy array) so lru_cache can hash it.
    The retrieval code converts back to ndarray with embedder.to_array().
    """
    vec = embedder.embed_one(f"query: {query}")
    return tuple(vec.tolist())


# ---------------------------------------------------------------------------
# Query rewriting — expand short / ambiguous queries before retrieval.
# Uses the fast 8B model so latency is minimal (~150 ms on Groq).
# Skipped when:
#   • query is already ≥ 8 words (specific enough)
#   • provider call fails (falls back to original query silently)
# ---------------------------------------------------------------------------

_REWRITE_SYSTEM = (
    "You are a retrieval query expander for Seelenruh, an Indian mental health, "
    "legal aid, government schemes, and women's safety assistant. "
    "Your only job: rewrite the user's short or ambiguous query into a clear, "
    "specific retrieval query (1–2 sentences) that will match the most relevant "
    "documents in the knowledge base. "
    "Output ONLY the rewritten query text — no explanation, no preamble, no quotes."
)


@lru_cache(maxsize=256)
def _rewrite_cache_lookup(query: str, domain: Optional[str]) -> Optional[str]:
    """In-process rewrite cache keyed on (query, domain).

    Returns None on a cache miss; the caller stores the result back via
    _rewrite_cache_store so subsequent identical queries skip the LLM call.
    Only populated by _rewrite_query after a successful LLM expansion.
    """
    return None  # populated via monkey-patch below


_rewrite_store: dict[tuple, str] = {}   # (query, domain) → rewritten


async def _rewrite_query(query: str, domain: Optional[str]) -> str:
    """Return an expanded version of *query* suitable for vector retrieval.

    Results are cached in-process so repeated short queries (e.g. "bail?"
    "RTI?" "pm kisan") bypass the LLM call entirely after the first hit.
    Average additional latency: ~0 ms on cache hit, ~150 ms on miss.

    Returns the original query unchanged when:
      - query is already ≥ 8 tokens (specific enough)
      - LLM call fails (graceful degradation)
      - rewritten result is not longer than original
    """
    tokens = query.split()
    if len(tokens) >= 8:
        return query

    cache_key = (query, domain)
    if cache_key in _rewrite_store:
        return _rewrite_store[cache_key]

    domain_hint = f" Domain context: {domain}." if domain else ""
    try:
        from ai.provider import chat as _provider_chat
        result = await _provider_chat(
            model=GROQ_MODEL_FAST,
            temperature=0.0,
            max_tokens=80,
            messages=[
                {"role": "system", "content": _REWRITE_SYSTEM + domain_hint},
                {"role": "user", "content": query},
            ],
        )
        rewritten = result["content"].strip()
        if rewritten and len(rewritten) > len(query):
            log.debug("query_rewritten", original=query, rewritten=rewritten)
            _rewrite_store[cache_key] = rewritten
            return rewritten
    except Exception as err:
        log.debug("query_rewrite_failed", error=str(err))
    return query


# Single-token Hinglish → English (processed per token in _normalize_query)
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
    # property and housing — single-token only; multi-word phrases handled below
    "kiraya": "rent payment", "kiraaya": "rent",
    "kirayedaar": "tenant renter", "kiraydar": "tenant",
    "makaanmaalik": "landlord",   # camelCase / no-space variant
    # employment Hinglish — single-token only
    "tankhwaah": "salary wages", "tankha": "salary wages",
    "tankhah": "salary wages", "talab": "salary wages",
    "mazdoor": "worker labour employee",
    "thekedar": "contractor employer",
    "f&f": "full and final settlement dues payable",
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

# Multi-word Hinglish phrases → English equivalents.
# Processed BEFORE per-token expansion using regex substitution on the full query string.
# Previously these were dead keys in _HINGLISH_MAP because the token loop never saw them.
_HINGLISH_PHRASES: list[tuple[re.Pattern, str]] = [
    # Property / housing
    (re.compile(r'\bmakan\s+maalik\b', re.I),   "landlord"),
    (re.compile(r'\bghar\s+se\s+nikaala\b', re.I), "eviction evicted illegally"),
    (re.compile(r'\bbahar\s+kar\s+diya\b', re.I),  "evicted thrown out illegal"),
    (re.compile(r'\bdaakhil\s+karo\b', re.I),      "file submit application"),
    (re.compile(r'\bzameen\s+ka\s+hak\b', re.I),   "land rights property ownership"),
    # Employment — salary unpaid
    (re.compile(r'\bsalary\s+nahi\s+mili\b', re.I),  "unpaid wages salary withheld"),
    (re.compile(r'\bsalary\s+nahi\s+di\b', re.I),    "unpaid wages employer withheld salary"),
    (re.compile(r'\bsalary\s+pending\b', re.I),       "salary unpaid wages pending"),
    (re.compile(r'\bpaise\s+nahi\s+mile\b', re.I),    "salary wages not received unpaid"),
    (re.compile(r'\bhisaab\s+nahi\s+hua\b', re.I),    "dues not settled salary pending"),
    # Employment — termination
    (re.compile(r'\bnaukri\s+gayi\b', re.I),           "job terminated dismissed"),
    (re.compile(r'\bnaukri\s+se\s+nikaala\b', re.I),   "wrongful termination dismissed"),
    (re.compile(r'\bjob\s+se\s+hataya\b', re.I),        "wrongful termination dismissed"),
    (re.compile(r'\bterminate\s+kar\s+diya\b', re.I),  "termination dismissed employment"),
    (re.compile(r'\bnaukri\s+chod\s+di\b', re.I),      "resigned from job employment"),
    (re.compile(r'\bresign\s+kar\s+diya\b', re.I),      "resignation employment"),
    # Employment — settlement documents
    (re.compile(r'\bf\s+and\s+f\b', re.I),                  "full and final settlement dues"),
    (re.compile(r'\bfinal\s+settlement\b', re.I),           "full and final F&F dues payable on exit"),
    (re.compile(r'\bfull\s+and\s+final\b', re.I),           "full and final settlement F&F dues"),
    (re.compile(r'\bexperience\s+letter\b', re.I),          "experience letter employment relieving"),
    (re.compile(r'\brelieving\s+letter\b', re.I),           "relieving letter experience employment"),
    (re.compile(r'\bnotice\s+period\s+ka\s+paisa\b', re.I), "notice period salary payment dues"),
    (re.compile(r'\bnotice\s+period\b', re.I),               "notice period pay employment contract"),
    # Company absconded
    (re.compile(r'\bcompany\s+bhaag\s+gayi\b', re.I),    "employer absconded company closed wages unpaid"),
    (re.compile(r'\bcompany\s+band\s+ho\s+gayi\b', re.I), "company closed employer absconded dues pending"),
]

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]+")

# (pattern, expansion terms) — appended before embedding for vague legal queries
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
    # Unpaid salary / wages withheld
    (re.compile(r"salary.{0,30}(nahi|not paid|not credited|withheld|pending|due|hold|stop|delay|deduct)|wages.{0,20}(not paid|unpaid|pending|due|withheld|stop)|(employer|company|boss).{0,20}(not paying|not given|withheld|holding|salary)", re.I),
     "Code on Wages 2019 Payment of Wages Act 1936 unpaid salary labour commissioner complaint Shops and Establishments Act written demand notice EPFO shramsuvidha.gov.in"),
    # Employer absconded / company closed
    (re.compile(r"(employer|company|boss).{0,30}(absconded|fled|ran away|disappeared|shut|closed|shut down|bhaag)|company.{0,20}(band|close|shut)|owner.{0,20}(missing|absconded)", re.I),
     "Code on Wages 2019 Insolvency and Bankruptcy Code wages priority claim labour commissioner EPFO provident fund outstanding dues employer absconded"),
    # Full and final settlement / F&F / relieving/experience letter
    (re.compile(r"(full.{0,5}final|F&F|final.{0,10}settlement|dues.{0,20}(clear|pending|not|settle)|experience.{0,5}letter|relieving.{0,5}letter|notice period.{0,20}(pay|dues|salary|not|pending)|last.{0,10}salary.{0,10}(not|pending|due))", re.I),
     "full and final settlement F&F dues Shops and Establishments Act Industrial Disputes Act retrenchment compensation gratuity earned leave encashment notice pay relieving letter labour commissioner"),
    # Wrongful termination
    (re.compile(r"(wrongful.{0,10}termination|illegal.{0,10}terminat|unfair dismissal|terminat.{0,20}(without notice|without cause|no reason)|retrench.{0,20}(illegal|wrongful|unfair|without|not follow))", re.I),
     "Industrial Disputes Act 1947 Industrial Relations Code 2020 wrongful termination retrenchment workman reinstatement back wages labour court"),
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
    """Append domain-specific terminology to vague legal queries before embedding. No LLM call."""
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

    # Phase 1: multi-word phrase expansion (must run BEFORE per-token loop;
    # these patterns were dead keys in _HINGLISH_MAP because the token loop
    # processes one whitespace-split token at a time and never sees phrases).
    for phrase_re, replacement in _HINGLISH_PHRASES:
        text = phrase_re.sub(replacement, text)

    # Phase 2: per-token single-word Hinglish expansion.
    # Devanagari tokens are left as-is — multilingual-e5 handles them natively.
    tokens = text.split()
    expanded = []
    for tok in tokens:
        lower = tok.lower().rstrip("?!.,;:")
        if lower in _HINGLISH_MAP and not _DEVANAGARI_RE.search(tok):
            expanded.append(_HINGLISH_MAP[lower])
        else:
            expanded.append(tok)
    return " ".join(expanded).strip()


def _build_retrieval_query(query: str, history: Optional[list[dict]]) -> str:
    """
    For short follow-up queries that lack sufficient retrieval context
    (e.g. "what documents?" after a DV discussion), prepend the most recent
    user turn so the retriever understands what topic is being continued.

    Only activates when query is ≤ 10 words — longer queries are self-contained.
    The original query is appended at the end so the embedding space is dominated
    by the user's actual intent, not the historical context.
    """
    if not history or len(query.split()) > 10:
        return query
    # Walk history in reverse to find the last user message
    prev_user_content = next(
        (m.get("content", "") for m in reversed(history) if m.get("role") == "user"),
        None,
    )
    if not prev_user_content or len(prev_user_content.split()) < 3:
        return query
    # Use up to 100 characters of context — enough for topic signal, not noise
    context_prefix = prev_user_content.strip()[:100]
    return f"{context_prefix} {query}"


# Scheme-specific query expansion — mirrors _LEGAL_EXPANSIONS for Government Schemes domain.
# Activates on scheme abbreviations, Hinglish benefit names, and category keywords
# that the per-token Hinglish map can't handle (they need semantic context to expand).
_SCHEME_EXPANSIONS: list[tuple] = [
    # Health insurance
    (re.compile(r'\b(pm-?jay|pmjay|ayushman|health\s+card|jan\s+arogya)\b', re.I),
     "Ayushman Bharat PM-JAY health insurance hospitalisation 5 lakh pmjay.gov.in 14555"),
    # Housing
    (re.compile(r'\b(pmay|pm\s?awas|pradhan\s+mantri\s+awas|affordable\s+housing\s+scheme|gramin\s+awas)\b', re.I),
     "PM Awas Yojana PMAY housing subsidy pmaymis.gov.in rural urban CLSS interest subsidy"),
    # Farmer income support
    (re.compile(r'\b(pm-?kisan|pmkisan|kisan\s+samman|farmer.{0,10}(₹6000|6000|installment|samman))\b', re.I),
     "PM-KISAN 6000 annual farmer income support installment pmkisan.gov.in 155261 land records"),
    # Rural employment
    (re.compile(r'\b(mgnrega|mnrega|narega|100.{0,5}days|job\s+card|mahatma\s+gandhi\s+rural)\b', re.I),
     "MGNREGA 100 days employment guarantee wage rural job card nrega.nic.in"),
    # Accident and life insurance
    (re.compile(r'\b(pmsby|pmjjby|jan\s+suraksha|bima\s+yojana|accidental.{0,15}government|life\s+insurance.{0,15}government)\b', re.I),
     "PMSBY PMJJBY Jan Suraksha accident life insurance 330 436 premium jansuraksha.gov.in"),
    # Pension for unorganised
    (re.compile(r'\b(atal\s+pension|apy\b|pension.{0,20}(poor|bpl|worker|unorganised|asangathit))\b', re.I),
     "Atal Pension Yojana APY 1000 5000 monthly unorganised sector retirement NPS"),
    # Scholarships
    (re.compile(r'\b(nsp\b|national\s+scholarship|post.?matric|pre.?matric|merit.{0,10}scholarship|oasis\s+scholarship)\b', re.I),
     "National Scholarship Portal scholarships.gov.in post-matric pre-matric merit NSP deadline"),
    # LPG / Ujjwala
    (re.compile(r'\b(ujjwala|pmuy|lpg.{0,15}(free|connection|bpl|cylinder)|free.{0,10}gas)\b', re.I),
     "PM Ujjwala Yojana PMUY free LPG connection BPL women pmuy.gov.in"),
    # e-Shram / unorganised workers
    (re.compile(r'\b(e-?shram|eshram|asangathit|unorganised\s+worker|gig\s+worker.{0,15}register)\b', re.I),
     "e-Shram portal eshram.gov.in unorganised worker registration card insurance social security"),
    # MUDRA / micro-business loans
    (re.compile(r'\b(mudra|pmmy|shishu\s+loan|kishore\s+loan|tarun\s+loan|micro.{0,10}enterprise.{0,10}loan)\b', re.I),
     "MUDRA loan PMMY Shishu Kishore Tarun mudra.org.in micro enterprise business loan"),
    # Ration / food security
    (re.compile(r'\b(ration\s+card|pds|public\s+distribution|free\s+ration|pmgkay|antyodaya|aay\b)\b', re.I),
     "ration card PDS public distribution free grain PMGKAY Antyodaya BPL food security"),
    # Jan Dhan / financial inclusion
    (re.compile(r'\b(jan\s+dhan|pmjdy|zero.{0,10}balance.{0,10}account|basic.{0,10}savings.{0,10}account)\b', re.I),
     "Jan Dhan Yojana PMJDY zero balance bank account financial inclusion pmjdy.gov.in"),
    # Category-specific benefits
    (re.compile(r'\b(sc|st|obc|ews).{0,20}(scheme|reservation|quota|benefit|scholarship|yojana)\b', re.I),
     "SC ST OBC EWS category scheme scholarship reservation benefit eligibility caste certificate"),
    # Disability
    (re.compile(r'\b(disability|divyang|viklang|handicap).{0,20}(scheme|pension|benefit|card|certificate)\b', re.I),
     "disability Divyangjan scheme pension UDID card disability certificate welfare benefit"),
    # Women / child schemes
    (re.compile(r'\b(sukanya|beti\s+bachao|ladli|mahila\s+samridhi|maternity\s+benefit)\b', re.I),
     "Sukanya Samriddhi Beti Bachao Beti Padhao Ladli maternity benefit girl child scheme savings"),
    # Startup / MSME
    (re.compile(r'\b(startup\s+india|stand.?up\s+india|msme\s+(loan|scheme|benefit)|udyam\s+registration)\b', re.I),
     "Startup India Stand Up India MSME loan Udyam registration DPIIT recognition fund-of-funds"),
]


def _expand_scheme_query(query: str) -> str:
    """Append scheme-specific terminology to Government Schemes queries before embedding."""
    additions: list[str] = []
    for pattern, expansion in _SCHEME_EXPANSIONS:
        if pattern.search(query):
            additions.append(expansion)
    if not additions:
        return query
    return query + " " + " ".join(additions)


_store = VectorStore()
_ready = False
_write_lock = asyncio.Lock()

# BM25 sparse index — built alongside FAISS during init()
_bm25_index: Optional["BM25Okapi"] = None  # type: ignore[type-arg]
_bm25_chunks: list[dict] = []  # parallel list to BM25 corpus


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    return re.sub(r"[^\w\s]", " ", text.lower()).split()


def _build_bm25(chunks: list[dict]) -> None:
    """Build (or rebuild) the BM25 index from enriched chunks."""
    global _bm25_index, _bm25_chunks
    if not _BM25_AVAILABLE:
        return
    corpus = [_tokenize(f"{c.get('topic', '')} {c.get('text', '')}") for c in chunks]
    _bm25_chunks = list(chunks)
    _bm25_index = BM25Okapi(corpus)
    log.info("bm25_index_built", docs=len(corpus))


def _bm25_search(query: str, k: int, domain: Optional[str] = None) -> list[dict]:
    """Return up to *k* BM25-ranked chunks, optionally filtered by domain."""
    if _bm25_index is None or not _bm25_chunks:
        return []
    tokens = _tokenize(query)
    scores = _bm25_index.get_scores(tokens)
    # pair (score, chunk) — filter by domain if requested
    pairs = [
        (scores[i], _bm25_chunks[i])
        for i in range(len(_bm25_chunks))
        if domain is None or _bm25_chunks[i].get("domain") == domain
    ]
    pairs.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in pairs[:k]]


def _rrf_fuse(
    faiss_hits: list[dict],
    bm25_hits: list[dict],
    k_param: int = 60,
) -> list[dict]:
    """Reciprocal Rank Fusion of FAISS + BM25 results, deduplicated by chunk id."""
    scores: dict[str, float] = {}
    id_to_chunk: dict[str, dict] = {}

    for rank, chunk in enumerate(faiss_hits):
        cid = chunk.get("id", "") or chunk.get("topic", f"faiss_{rank}")
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k_param + rank + 1)
        id_to_chunk[cid] = chunk

    for rank, chunk in enumerate(bm25_hits):
        cid = chunk.get("id", "") or chunk.get("topic", f"bm25_{rank}")
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k_param + rank + 1)
        id_to_chunk[cid] = chunk

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [id_to_chunk[cid] for cid in sorted_ids]


async def init() -> None:
    """Build or load the FAISS index and BM25 index."""
    global _ready
    if _ready:
        return

    if _store.load() and _store.size() == len(CHUNKS):
        log.info("loaded from cache", chunks=_store.size())
        # Build BM25 from cached store's chunks
        _build_bm25(_store.meta)
        _ready = True
        return

    log.info("building index", chunks=len(CHUNKS))
    t0 = time.time()
    enriched = [enrich_chunk(c) for c in CHUNKS]
    texts = [f"passage: {c['topic']}\n{c['text']}" for c in enriched]
    vectors = await asyncio.to_thread(embedder.embed_many, texts)
    _store.build(enriched, vectors)
    _store.save()
    _build_bm25(enriched)
    log.info("index built", chunks=_store.size(), ms=int((time.time() - t0) * 1000), bm25=_BM25_AVAILABLE)
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
    """Fetch more candidates for Legal/Scheme domains — dense chunks, wording differences matter."""
    if not reranker.is_enabled():
        return k
    base = max(k, RETRIEVAL_OVERFETCH)
    if domain == "Legal":
        return max(base, 25)  # larger candidate pool — legal chunks are dense and wording matters
    if domain == "Government Schemes":
        return max(base, 20)
    return base


def _dedup(hits: list[dict]) -> list[dict]:
    """Drop duplicate chunks with the same topic. Keeps the highest-ranked occurrence."""
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


def _apply_staleness_penalty(results: list[dict]) -> list[dict]:
    """Penalise stale chunks so fresh sources rank higher.

    Deprecated/Superseded chunks stay in results (the LLM can still use them)
    but their rerank_score drops so fresh chunks bubble up ahead of them.
    We never completely remove stale chunks — sometimes they are the only
    source and the user still needs the information with a caveat.
    """
    for chunk in results:
        status = chunk.get("reviewStatus", "")
        if status == "Deprecated":
            chunk["score"] = float(chunk.get("score", 0.5)) * 0.5
            if "rerank_score" in chunk:
                chunk["rerank_score"] = float(chunk["rerank_score"]) - 3.0
            chunk["stale_penalty_applied"] = True
        elif status == "Superseded":
            chunk["score"] = float(chunk.get("score", 0.5)) * 0.7
            if "rerank_score" in chunk:
                chunk["rerank_score"] = float(chunk["rerank_score"]) - 1.5
            chunk["stale_penalty_applied"] = True
        elif status == "NeedsReview":
            # Mild nudge — needs-review chunks are probably still useful
            if "rerank_score" in chunk:
                chunk["rerank_score"] = float(chunk["rerank_score"]) - 0.4
    return results


async def retrieve(
    query: str,
    *,
    domain: Optional[str] = None,
    k: int = RETRIEVAL_TOP_K,
    history: Optional[list[dict]] = None,
) -> list[dict]:
    if not _ready:
        await init()

    # Multi-turn context injection: for short follow-up queries, prepend the
    # previous user turn so the retriever understands what topic is being continued.
    retrieval_query = _build_retrieval_query(query, history)

    # Normalise Hinglish (phrase pass + per-token pass)
    retrieval_query = _normalize_query(retrieval_query)

    # Query rewriting — expand short / ambiguous queries via fast LLM call
    retrieval_query = await _rewrite_query(retrieval_query, domain)

    # Domain-specific keyword expansion
    if domain == "Legal":
        retrieval_query = _expand_legal_query(retrieval_query)
    elif domain == "Government Schemes":
        retrieval_query = _expand_scheme_query(retrieval_query)

    # Use the LRU-cached embed to skip re-encoding repeated queries
    import numpy as np
    qv = await asyncio.to_thread(_embed_query_cached, retrieval_query)
    qv = np.array(qv, dtype="float32")
    fetch_k = _overfetch_k(k, domain)

    # Dense retrieval (FAISS)
    faiss_hits = _store.search(qv, k=fetch_k, domain=domain)

    # Sparse retrieval (BM25) — only if available
    if _BM25_AVAILABLE and _bm25_index is not None:
        bm25_hits = _bm25_search(retrieval_query, k=fetch_k, domain=domain)
        candidates = _rrf_fuse(faiss_hits, bm25_hits)
    else:
        candidates = faiss_hits

    if reranker.is_enabled() and len(candidates) > k:
        results = await reranker.rerank(retrieval_query, candidates, k=k)
    else:
        results = candidates[:k]

    # Apply staleness penalty and re-sort so fresh chunks surface first
    results = _apply_staleness_penalty(results)
    if any(c.get("stale_penalty_applied") for c in results):
        results.sort(key=lambda c: c.get("rerank_score", c.get("score", 0.0)), reverse=True)

    return _dedup(results)
