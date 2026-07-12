"""
Knowledge metadata enrichment and intelligent verification system.

PROBLEM SOLVED:
  The old system penalised chunks purely by age (months since lastVerifiedOn).
  A Constitution article from 1950 got the same "STALE" badge as a helpline
  number not verified in 7 months. Age alone is the wrong signal.

NEW APPROACH:
  1. Classify every chunk by documentType (Act, Scheme, Helpline, Constitution, etc.)
  2. Assign type-appropriate review windows (Constitution = never, Helpline = 30 days)
  3. Compute reviewStatus from type + last verification date — not age alone
  4. Score source authority from URL / source string (Authoritative → Low)
  5. Compute weighted confidence: authority 30% + retrieval 20% + rerank 20%
     + review status 10% + source quality 10% + cross-doc agreement 10%
  6. Generate human-readable reviewNote for the frontend instead of bare "STALE"

Existing chunks are enriched at runtime — no manual knowledge.py edits needed.
"""
from datetime import date
from enum import Enum
from typing import Optional

# ──────────────────────────────────────────────────────────────
# TAXONOMY
# ──────────────────────────────────────────────────────────────

class DocumentType(str, Enum):
    CONSTITUTION   = "Constitution"     # Constitutional provisions — never expire
    ACT            = "Act"              # Statutes / bare acts
    RULE           = "Rule"             # Subordinate legislation
    NOTIFICATION   = "Notification"     # Ministry/gazette notifications
    CIRCULAR       = "Circular"         # Department circulars / advisories
    SCHEME         = "Scheme"           # Government welfare schemes / yojanas
    HELPLINE       = "Helpline"         # Emergency / support numbers
    SCHOLARSHIP    = "Scholarship"      # Academic scholarships / fellowships
    JUDGMENT       = "Judgment"         # Court judgments / orders
    FAQ            = "FAQ"              # Frequently asked questions
    RESEARCH       = "Research"         # Research papers / academic studies
    MANUAL         = "Manual"           # Official manuals / handbooks
    GUIDELINE      = "Guideline"        # Advisories / recommendations
    POLICY         = "Policy"           # National / state policies
    PORTAL         = "Portal"           # Government web portals
    GENERAL        = "General"          # Fallback


class ReviewStatus(str, Enum):
    VERIFIED      = "Verified"          # Within review window — information is current
    NEEDS_REVIEW  = "NeedsReview"       # Review window elapsed — human should verify
    DEPRECATED    = "Deprecated"        # Explicitly retired / no longer relevant
    SUPERSEDED    = "Superseded"        # Replaced by newer version / law
    UNKNOWN       = "Unknown"           # No verification date available


class SourceAuthority(str, Enum):
    AUTHORITATIVE = "Authoritative"     # Primary law / gazette / apex court
    OFFICIAL      = "Official"          # Government portal / ministry
    INSTITUTIONAL = "Institutional"     # Universities / statutory bodies
    SECONDARY     = "Secondary"         # News / reference sites
    UNKNOWN       = "Unknown"           # No source URL


# ──────────────────────────────────────────────────────────────
# REVIEW WINDOWS (days; None = no expiry)
# ──────────────────────────────────────────────────────────────

REVIEW_DAYS: dict[DocumentType, Optional[int]] = {
    DocumentType.CONSTITUTION:   None,   # Never expires
    DocumentType.ACT:            365,    # Annual — laws change rarely but need yearly check
    DocumentType.RULE:           365,    # Annual
    DocumentType.JUDGMENT:       180,    # Biannual — precedents evolve
    DocumentType.MANUAL:         365,    # Annual
    DocumentType.GUIDELINE:      365,    # Annual
    DocumentType.POLICY:         365,    # Annual
    DocumentType.FAQ:            180,    # Biannual
    DocumentType.RESEARCH:       730,    # Biennial
    DocumentType.SCHEME:         90,     # Quarterly — budget cycles change schemes
    DocumentType.NOTIFICATION:   90,     # Quarterly — government orders change often
    DocumentType.CIRCULAR:       90,     # Quarterly
    DocumentType.PORTAL:         90,     # Quarterly — portals restructure
    DocumentType.HELPLINE:       30,     # Monthly — numbers change
    DocumentType.SCHOLARSHIP:    30,     # Monthly — deadlines change every cycle
    DocumentType.GENERAL:        180,    # Biannual default
}

_REVIEW_LABEL: dict[Optional[int], str] = {
    None:  "No expiry",
    30:    "Monthly",
    90:    "Quarterly",
    180:   "Biannual",
    365:   "Annual",
    730:   "Biennial",
}

# ──────────────────────────────────────────────────────────────
# DOCUMENT TYPE INFERENCE (keyword → type, applied to topic + source)
# ──────────────────────────────────────────────────────────────

_TYPE_RULES: list[tuple[list[str], DocumentType]] = [
    # Most specific first
    (["constitution", "article 1", "article 2", "article 3", "article 12", "article 13",
      "article 14", "article 19", "article 20", "article 21", "article 22", "article 23",
      "article 25", "article 32", "article 51", "article 226", "article 370",
      "fundamental right", "directive principle", "habeas corpus", "mandamus"],
     DocumentType.CONSTITUTION),

    (["helpline", "hotline", "1091", "1098", "1930", "112", "100", "101", "108",
      "181", "14567", "15100", "aasra", "icall", "vandrevala", "tele-manas",
      "nimhans helpline", "women helpline", "child helpline", "cyber helpline",
      "elderline", "emergency number"],
     DocumentType.HELPLINE),

    (["scholarship", "fellowship", "stipend", "nsp", "national scholarship",
      "merit scholarship", "post matric", "pre matric"],
     DocumentType.SCHOLARSHIP),

    (["judgment", "case", "supreme court held", "high court held", "bench", "plaintiff",
      "defendant", "petitioner", "respondent", "writ petition", "sos"],
     DocumentType.JUDGMENT),

    (["scheme", "yojana", "pradhan mantri", "pm-jay", "pmay", "pm kisan", "mgnrega",
      "pmkvy", "ujjwala", "mudra", "ayushman", "sukanya", "beti bachao",
      "e-shram", "atal pension", "stand up india", "pmfby", "ladli",
      "swadhar", "ujjwala", "maternity benefit", "kisan credit"],
     DocumentType.SCHEME),

    (["notification", "gazette notification", "g.s.r.", "s.o.", "no. f.", "ministry of",
      "department of", "office memorandum", "circular no", "order no"],
     DocumentType.NOTIFICATION),

    (["act", "ipc", "crpc", "bns", "bnss", "bsa", "pocso", "rti act", "posh",
      "consumer protection act", "negotiable instruments act", "transfer of property",
      "industrial disputes", "factories act", "dowry prohibition", "prevention of",
      "protection of", "rights of", "hindu marriage act", "special marriage act",
      "maintenance act", "senior citizens act", "it act", "information technology"],
     DocumentType.ACT),

    (["rule", "regulation", "rules 20", "procedure rules", "conduct rules"],
     DocumentType.RULE),

    (["policy", "national policy", "programme", "action plan", "five year plan"],
     DocumentType.POLICY),

    (["research", "study", "survey", "report", "findings", "prevalence", "analysis"],
     DocumentType.RESEARCH),

    (["faq", "frequently asked", "common questions", "q&a"],
     DocumentType.FAQ),

    (["manual", "handbook", "guide for", "user guide"],
     DocumentType.MANUAL),

    (["guideline", "advisory", "recommendation", "protocol"],
     DocumentType.GUIDELINE),

    (["portal", "website", "apply online", "register at", "gov.in", "nic.in",
      "apply at", "check at"],
     DocumentType.PORTAL),
]

# ──────────────────────────────────────────────────────────────
# SOURCE AUTHORITY INFERENCE
# ──────────────────────────────────────────────────────────────

_AUTHORITY_RULES: list[tuple[list[str], SourceAuthority]] = [
    # AUTHORITATIVE — primary law sources, apex courts, gazette
    (["legislative.gov.in", "indiacode.nic.in", "supremecourt.gov.in",
      "highcourts.gov.in", "ecourts.gov.in", "nalsa.gov.in", "rbi.org.in",
      "sebi.gov.in", "trai.gov.in", "cci.gov.in", "gazette.india.gov.in",
      "ncw.nic.in", "ncrb.gov.in", "nhrc.nic.in", "shebox.wcd.gov.in",
      "bar council", "india code", "gazette of india"],
     SourceAuthority.AUTHORITATIVE),

    # OFFICIAL — government portals, ministry sites
    ([".gov.in", ".nic.in", "pmjay.gov.in", "pmkisan.gov.in", "myscheme.gov.in",
      "scholarships.gov.in", "cybercrime.gov.in", "rtionline.gov.in",
      "consumerhelpline.gov.in", "nrega.nic.in", "shramsuvidha.gov.in",
      "pmaymis.gov.in", "mudra.org.in", "startupindia.gov.in", "wcd.nic.in",
      "mca.gov.in", "pfms.nic.in", "nsdl.co.in", "india.gov.in", "pib.gov.in",
      "niti.gov.in", "mhfw.gov.in", "labour.gov.in", "ncrb.gov.in"],
     SourceAuthority.OFFICIAL),

    # INSTITUTIONAL — universities, professional bodies, statutory institutions
    (["nimhans.ac.in", "iitk.ac.in", "nlsiu.ac.in", "nlu", "iima.ac.in",
      "who.int", "ilo.org", "unicef.org", "unwomen.org", "undp.org"],
     SourceAuthority.INSTITUTIONAL),

    # SECONDARY — informational / reference / news
    (["wikipedia", "blog", "medium.com", "quora", "reddit", "news", "hindustan times",
      "times of india", "ndtv", "scroll.in", "wire.in", "barandbench",
      "livelaw", "advocatekhoj"],
     SourceAuthority.SECONDARY),
]

# ──────────────────────────────────────────────────────────────
# SOURCE URL RESOLVER
# Maps known authority patterns → canonical official URLs.
# Order matters: more specific patterns come first.
# Never fabricates — returns None when no mapping exists.
# ──────────────────────────────────────────────────────────────

_SOURCE_URL_MAP: list[tuple[str, str]] = [
    # ── Primary law / Judiciary ────────────────────────────────
    ("indiacode.nic.in",            "https://www.indiacode.nic.in/"),
    ("india code",                  "https://www.indiacode.nic.in/"),
    ("legislative.gov.in",          "https://www.legislative.gov.in/"),
    ("supremecourt.gov.in",         "https://www.supremecourt.gov.in/"),
    ("supreme court",               "https://www.supremecourt.gov.in/"),
    ("ecourts.gov.in",              "https://services.ecourts.gov.in/"),
    ("ecourts",                     "https://services.ecourts.gov.in/"),
    ("gazette.india.gov.in",        "https://egazette.gov.in/"),
    ("gazette of india",            "https://egazette.gov.in/"),
    # ── Legal bodies ──────────────────────────────────────────
    ("nalsa.gov.in",                "https://nalsa.gov.in/"),
    ("nalsa",                       "https://nalsa.gov.in/"),
    ("ncw.nic.in",                  "https://ncw.nic.in/"),
    ("ncw",                         "https://ncw.nic.in/"),
    ("nhrc.nic.in",                 "https://nhrc.nic.in/"),
    ("nhrc",                        "https://nhrc.nic.in/"),
    ("shebox.wcd.gov.in",           "https://shebox.wcd.gov.in/"),
    ("she-box",                     "https://shebox.wcd.gov.in/"),
    ("shebox",                      "https://shebox.wcd.gov.in/"),
    ("ncrb.gov.in",                 "https://ncrb.gov.in/"),
    ("ncrb",                        "https://ncrb.gov.in/"),
    ("bar council",                 "https://www.barcouncilofindia.org/"),
    # ── Specific acts / portals ───────────────────────────────
    ("rtionline.gov.in",            "https://rtionline.gov.in/"),
    ("rti act",                     "https://rtionline.gov.in/"),
    ("right to information",        "https://rtionline.gov.in/"),
    ("consumerhelpline.gov.in",     "https://consumerhelpline.gov.in/"),
    ("consumer helpline",           "https://consumerhelpline.gov.in/"),
    ("consumer protection act",     "https://consumerhelpline.gov.in/"),
    ("posh act",                    "https://shebox.wcd.gov.in/"),
    ("pwdva",                       "https://ncw.nic.in/Acts-Rules-and-Policies/acts"),
    ("domestic violence act",       "https://ncw.nic.in/Acts-Rules-and-Policies/acts"),
    ("pocso",                       "https://www.indiacode.nic.in/"),
    ("bns 2023",                    "https://www.indiacode.nic.in/"),
    ("bnss 2023",                   "https://www.indiacode.nic.in/"),
    ("bharatiya nyaya sanhita",     "https://www.indiacode.nic.in/"),
    ("bharatiya nagarik suraksha",  "https://www.indiacode.nic.in/"),
    ("it act",                      "https://www.indiacode.nic.in/"),
    ("information technology act",  "https://www.indiacode.nic.in/"),
    ("dowry prohibition",           "https://www.indiacode.nic.in/"),
    ("negotiable instruments act",  "https://www.indiacode.nic.in/"),
    ("senior citizens act",         "https://www.indiacode.nic.in/"),
    ("hindu marriage act",          "https://www.indiacode.nic.in/"),
    ("special marriage act",        "https://www.indiacode.nic.in/"),
    ("hindu succession act",        "https://www.indiacode.nic.in/"),
    ("transfer of property",        "https://www.indiacode.nic.in/"),
    # ── Central schemes ───────────────────────────────────────
    ("pmjay.gov.in",                "https://pmjay.gov.in/"),
    ("ayushman bharat",             "https://pmjay.gov.in/"),
    ("pm-jay",                      "https://pmjay.gov.in/"),
    ("pmkisan.gov.in",              "https://pmkisan.gov.in/"),
    ("pm kisan",                    "https://pmkisan.gov.in/"),
    ("pm-kisan",                    "https://pmkisan.gov.in/"),
    ("scholarships.gov.in",         "https://scholarships.gov.in/"),
    ("national scholarship portal", "https://scholarships.gov.in/"),
    ("nsp portal",                  "https://scholarships.gov.in/"),
    ("nrega.nic.in",                "https://nrega.nic.in/"),
    ("mgnrega",                     "https://nrega.nic.in/"),
    ("pmaymis.gov.in",              "https://pmaymis.gov.in/"),
    ("pm awas yojana",              "https://pmaymis.gov.in/"),
    ("pmay",                        "https://pmaymis.gov.in/"),
    ("mudra.org.in",                "https://www.mudra.org.in/"),
    ("mudra loan",                  "https://www.mudra.org.in/"),
    ("pmvishwakarma.gov.in",        "https://pmvishwakarma.gov.in/"),
    ("pm vishwakarma",              "https://pmvishwakarma.gov.in/"),
    ("jansuraksha.gov.in",          "https://www.jansuraksha.gov.in/"),
    ("atal pension",                "https://www.jansuraksha.gov.in/"),
    ("pmsby",                       "https://www.jansuraksha.gov.in/"),
    ("pmjjby",                      "https://www.jansuraksha.gov.in/"),
    ("pmjdy.gov.in",                "https://pmjdy.gov.in/"),
    ("jan dhan",                    "https://pmjdy.gov.in/"),
    ("myscheme.gov.in",             "https://www.myscheme.gov.in/"),
    ("myscheme",                    "https://www.myscheme.gov.in/"),
    ("eshram.gov.in",               "https://eshram.gov.in/"),
    ("e-shram",                     "https://eshram.gov.in/"),
    ("eshram",                      "https://eshram.gov.in/"),
    ("pmkvy",                       "https://www.pmkvy.gov.in/"),
    ("skill india",                 "https://www.skillindia.gov.in/"),
    ("startup india",               "https://www.startupindia.gov.in/"),
    ("startupindia.gov.in",         "https://www.startupindia.gov.in/"),
    ("stand up india",              "https://www.standupmitra.in/"),
    ("sukanya samriddhi",           "https://www.nsiindia.gov.in/"),
    ("nps.gov.in",                  "https://enps.nsdl.com/"),
    ("atal pension yojana",         "https://enps.nsdl.com/"),
    ("india.gov.in",                "https://www.india.gov.in/"),
    ("national portal of india",    "https://www.india.gov.in/"),
    ("pfms.nic.in",                 "https://pfms.nic.in/"),
    ("dpiit",                       "https://dpiit.gov.in/"),
    ("mohua.gov.in",                "https://mohua.gov.in/"),
    # ── Ministry sites ────────────────────────────────────────
    ("wcd.nic.in",                  "https://wcd.nic.in/"),
    ("women and child development", "https://wcd.nic.in/"),
    ("mohfw.gov.in",                "https://www.mohfw.gov.in/"),
    ("ministry of health",          "https://www.mohfw.gov.in/"),
    ("labour.gov.in",               "https://labour.gov.in/"),
    ("mca.gov.in",                  "https://www.mca.gov.in/"),
    ("moe.gov.in",                  "https://www.education.gov.in/"),
    ("education ministry",          "https://www.education.gov.in/"),
    ("agriculture ministry",        "https://agricoop.nic.in/"),
    ("sebi.gov.in",                 "https://www.sebi.gov.in/"),
    ("rbi.org.in",                  "https://www.rbi.org.in/"),
    ("pib.gov.in",                  "https://pib.gov.in/"),
    # ── Safety / emergency / cyber ────────────────────────────
    ("cybercrime.gov.in",           "https://cybercrime.gov.in/"),
    ("national cyber crime",        "https://cybercrime.gov.in/"),
    ("cyber crime portal",          "https://cybercrime.gov.in/"),
    ("1930",                        "https://cybercrime.gov.in/"),
    ("cert-in",                     "https://www.cert-in.org.in/"),
    ("certin",                      "https://www.cert-in.org.in/"),
    ("ndrf.gov.in",                 "https://www.ndrf.gov.in/"),
    ("ndrf",                        "https://www.ndrf.gov.in/"),
    ("112.gov.in",                  "https://www.112.gov.in/"),
    ("mha.gov.in",                  "https://www.mha.gov.in/"),
    ("mha ",                        "https://www.mha.gov.in/"),
    # ── Mental health / helplines ─────────────────────────────
    ("nimhans.ac.in",               "https://nimhans.ac.in/"),
    ("nimhans",                     "https://nimhans.ac.in/"),
    ("icallhelpline.org",           "https://icallhelpline.org/"),
    ("icall",                       "https://icallhelpline.org/"),
    ("tele-manas",                  "https://telemanas.mohfw.gov.in/"),
    ("telemanas",                   "https://telemanas.mohfw.gov.in/"),
    ("vandrevala",                  "https://www.vandrevalafoundation.com/"),
    ("aasra",                       "https://www.aasra.info/"),
    ("who.int",                     "https://www.who.int/"),
    ("who ",                        "https://www.who.int/"),
    # ── State portals ─────────────────────────────────────────
    ("karnataka.gov.in",            "https://www.karnataka.gov.in/"),
    ("maharashtra.gov.in",          "https://www.maharashtra.gov.in/"),
    ("up.gov.in",                   "https://www.up.gov.in/"),
    ("tn.gov.in",                   "https://www.tn.gov.in/"),
    ("delhigovt.nic.in",            "https://www.delhi.gov.in/"),
    ("wb.gov.in",                   "https://wb.gov.in/"),
    ("kerala.gov.in",               "https://www.kerala.gov.in/"),
    ("mp.gov.in",                   "https://www.mp.gov.in/"),
    ("rajasthan.gov.in",            "https://www.rajasthan.gov.in/"),
    ("gujarat.gov.in",              "https://www.gujarat.gov.in/"),
    ("telangana.gov.in",            "https://www.telangana.gov.in/"),
    ("ap.gov.in",                   "https://www.ap.gov.in/"),
    ("assam.gov.in",                "https://assam.gov.in/"),
    ("odisha.gov.in",               "https://odisha.gov.in/"),
    # ── International ─────────────────────────────────────────
    ("who.int",                     "https://www.who.int/"),
    ("unicef.org",                  "https://www.unicef.org/"),
    ("ilo.org",                     "https://www.ilo.org/"),
    # ── Additional ministry abbreviations ─────────────────────
    ("dsm-5",                       "https://www.psychiatry.org/psychiatrists/practice/dsm"),
    ("dsm-iv",                      "https://www.psychiatry.org/psychiatrists/practice/dsm"),
    ("mohfw",                       "https://www.mohfw.gov.in/"),
    ("mofw",                        "https://www.mohfw.gov.in/"),
    ("mhfw",                        "https://www.mohfw.gov.in/"),
    ("mwcd",                        "https://wcd.nic.in/"),
    ("mohua",                       "https://mohua.gov.in/"),
    ("ministry of housing",         "https://mohua.gov.in/"),
    ("ministry of agriculture",     "https://agricoop.nic.in/"),
    ("department of agriculture",   "https://agricoop.nic.in/"),
    ("ministry of education",       "https://www.education.gov.in/"),
    ("ministry of social justice",  "https://socialjustice.gov.in/"),
    ("ministry of tribal affairs",  "https://tribal.gov.in/"),
    ("ministry of jal shakti",      "https://jalshakti-ddws.gov.in/"),
    ("ministry of finance",         "https://www.finmin.nic.in/"),
    ("ndma",                        "https://ndma.gov.in/"),
    ("ndma fire",                   "https://ndma.gov.in/"),
    ("nsap",                        "https://nsap.nic.in/"),
    ("national social assistance",  "https://nsap.nic.in/"),
    ("i4c",                         "https://www.cybercrime.gov.in/"),
    ("pmmy",                        "https://www.mudra.org.in/"),
    ("aasm",                        "https://aasm.org/"),
    ("nami",                        "https://www.nami.org/"),
    ("icmr",                        "https://www.icmr.gov.in/"),
    ("dpdp act",                    "https://www.meity.gov.in/"),
    ("digital personal data",       "https://www.meity.gov.in/"),
    ("limitation act",              "https://www.indiacode.nic.in/"),
    ("legal services authorities",  "https://nalsa.gov.in/"),
    ("indian succession act",       "https://www.indiacode.nic.in/"),
    ("citizenship act",             "https://www.indiacode.nic.in/"),
]


def resolve_source_url(chunk: dict) -> Optional[str]:
    """
    Resolve the best known official URL for a chunk.

    Priority order:
      1. Explicit sourceUrl field already set on the chunk
      2. Match against _SOURCE_URL_MAP using source + topic strings
      3. None — never fabricates a URL

    Safe to call with any chunk; returns None if no mapping exists.
    """
    if chunk.get("sourceUrl"):
        return chunk["sourceUrl"]

    haystack = (
        (chunk.get("source") or "") + " " + (chunk.get("topic") or "")
    ).lower()

    if not haystack.strip():
        return None

    for pattern, url in _SOURCE_URL_MAP:
        if pattern in haystack:
            return url

    return None


# ──────────────────────────────────────────────────────────────
# SCORES FOR WEIGHTED CONFIDENCE
# ──────────────────────────────────────────────────────────────

_AUTHORITY_SCORE: dict[SourceAuthority, float] = {
    SourceAuthority.AUTHORITATIVE: 1.00,
    SourceAuthority.OFFICIAL:      0.85,
    SourceAuthority.INSTITUTIONAL: 0.60,
    SourceAuthority.SECONDARY:     0.25,
    SourceAuthority.UNKNOWN:       0.40,  # benefit of the doubt for knowledge base entries
}

_REVIEW_STATUS_SCORE: dict[ReviewStatus, float] = {
    ReviewStatus.VERIFIED:     1.00,
    ReviewStatus.UNKNOWN:      0.70,
    ReviewStatus.NEEDS_REVIEW: 0.55,  # penalty for overdue review — not zero
    ReviewStatus.SUPERSEDED:   0.15,
    ReviewStatus.DEPRECATED:   0.05,
}

# ──────────────────────────────────────────────────────────────
# INFERENCE FUNCTIONS
# ──────────────────────────────────────────────────────────────

def infer_document_type(chunk: dict) -> DocumentType:
    """
    Infer document type from topic + source text.
    Tried in order — first match wins.
    """
    haystack = (
        (chunk.get("topic") or "") + " " + (chunk.get("source") or "") + " " + (chunk.get("text") or "")[:300]
    ).lower()

    for keywords, doc_type in _TYPE_RULES:
        if any(kw in haystack for kw in keywords):
            return doc_type

    # Domain-based fallback
    domain = (chunk.get("domain") or "").lower()
    if "mental health" in domain:
        return DocumentType.GENERAL
    if "safety" in domain:
        return DocumentType.GENERAL
    return DocumentType.GENERAL


def infer_source_authority(chunk: dict) -> SourceAuthority:
    """
    Infer source authority from the source URL / citation string.
    """
    haystack = (
        (chunk.get("source") or "") + " " + (chunk.get("topic") or "")
    ).lower()

    if not haystack.strip():
        return SourceAuthority.UNKNOWN

    for keywords, authority in _AUTHORITY_RULES:
        if any(kw in haystack for kw in keywords):
            return authority

    # If source field exists but didn't match, give benefit of the doubt
    if chunk.get("source"):
        return SourceAuthority.INSTITUTIONAL
    return SourceAuthority.UNKNOWN


def compute_review_status(chunk: dict, doc_type: DocumentType, today: Optional[date] = None) -> ReviewStatus:
    """
    Compute review status based on document type's review window.

    NEVER marks a document as needing review based on age alone.
    Instead: does the document type have a review frequency, and has that
    window elapsed since the last verification?

    Constitution articles → VERIFIED forever (no window).
    Helpline numbers → NEEDS_REVIEW after 30 days.
    """
    # Explicit overrides from chunk metadata
    if chunk.get("currentStatus") == "Superseded" or chunk.get("supersededBy"):
        return ReviewStatus.SUPERSEDED
    if chunk.get("currentStatus") == "Deprecated" or chunk.get("deprecated"):
        return ReviewStatus.DEPRECATED

    # No review frequency → document is considered always valid
    window_days = REVIEW_DAYS.get(doc_type)
    if window_days is None:
        return ReviewStatus.VERIFIED

    lv = chunk.get("lastVerifiedOn")
    if not lv:
        return ReviewStatus.UNKNOWN

    try:
        last_verified = date.fromisoformat(str(lv))
        elapsed = ((today or date.today()) - last_verified).days
        return ReviewStatus.NEEDS_REVIEW if elapsed > window_days else ReviewStatus.VERIFIED
    except Exception:
        return ReviewStatus.UNKNOWN


def get_review_note(doc_type: DocumentType, status: ReviewStatus, last_verified: Optional[str]) -> str:
    """
    Generate a human-readable explanation for the frontend.
    Replaces bare 'STALE' with meaningful context.
    """
    lv_str = f" Last verified {last_verified}." if last_verified else ""
    freq = _REVIEW_LABEL.get(REVIEW_DAYS.get(doc_type), "periodically")

    notes = {
        (DocumentType.CONSTITUTION, ReviewStatus.VERIFIED):
            f"Constitutional provision — does not expire.{lv_str}",
        (DocumentType.HELPLINE, ReviewStatus.NEEDS_REVIEW):
            "Helpline numbers are verified monthly. This number is due for re-verification. Please confirm before calling.",
        (DocumentType.HELPLINE, ReviewStatus.VERIFIED):
            f"Recently verified helpline number.{lv_str}",
        (DocumentType.SCHEME, ReviewStatus.NEEDS_REVIEW):
            f"Government schemes change with budget cycles (quarterly review). Eligibility or benefits may have been updated.{lv_str}",
        (DocumentType.SCHEME, ReviewStatus.VERIFIED):
            f"Scheme information verified within the quarterly review window.{lv_str}",
        (DocumentType.ACT, ReviewStatus.NEEDS_REVIEW):
            f"This law is reviewed annually. Verify the latest version at legislative.gov.in.{lv_str}",
        (DocumentType.ACT, ReviewStatus.VERIFIED):
            f"Active legislation verified within the annual review window.{lv_str}",
        (DocumentType.SCHOLARSHIP, ReviewStatus.NEEDS_REVIEW):
            f"Scholarship eligibility and deadlines change every academic cycle. Verify at scholarships.gov.in.{lv_str}",
        (ReviewStatus.SUPERSEDED, ReviewStatus.SUPERSEDED):  # catch-all
            "This document may have been replaced by a newer version. Please verify at the official source.",
        (ReviewStatus.DEPRECATED, ReviewStatus.DEPRECATED):
            "This document has been retired and may no longer be applicable.",
    }

    # Look up specific combination first, then fallback
    result = notes.get((doc_type, status))
    if result:
        return result

    if status == ReviewStatus.VERIFIED:
        return f"Verified within the {freq.lower()} review window.{lv_str}"
    if status == ReviewStatus.NEEDS_REVIEW:
        return f"Due for {freq.lower()} review. Content may have changed.{lv_str}"
    if status == ReviewStatus.SUPERSEDED:
        return "This document may have been replaced. Please verify at the official source."
    if status == ReviewStatus.DEPRECATED:
        return "This document is no longer current."
    return f"Verification status unknown.{lv_str}"


def enrich_chunk(chunk: dict, today: Optional[date] = None) -> dict:
    """
    Enrich an existing chunk with derived metadata fields.
    Non-destructive: existing fields take precedence over inferred ones.
    Called once at index build time — not at every retrieval.
    """
    doc_type  = DocumentType(chunk.get("documentType") or infer_document_type(chunk).value)
    authority = SourceAuthority(chunk.get("sourceAuthority") or infer_source_authority(chunk).value)
    status    = ReviewStatus(chunk.get("reviewStatus") or compute_review_status(chunk, doc_type, today).value)
    note      = chunk.get("reviewNote") or get_review_note(doc_type, status, chunk.get("lastVerifiedOn"))
    freq_days = REVIEW_DAYS.get(doc_type)
    freq_label = _REVIEW_LABEL.get(freq_days, "Periodic")

    return {
        **chunk,
        "documentType":    doc_type.value,
        "sourceAuthority": authority.value,
        "reviewStatus":    status.value,
        "reviewNote":      note,
        "reviewFrequency": freq_label,
        "sourceUrl":       resolve_source_url(chunk),
    }


# ──────────────────────────────────────────────────────────────
# WEIGHTED CONFIDENCE SCORING
# ──────────────────────────────────────────────────────────────

def _normalise_faiss(score: float) -> float:
    """Normalise FAISS cosine similarity (typically 0.5–1.0) to 0–1."""
    return max(0.0, min(1.0, (score - 0.5) / 0.5))


def _normalise_rerank(score: float) -> float:
    """Normalise cross-encoder rerank score (typically -10 to +10) to 0–1."""
    return max(0.0, min(1.0, (score + 10) / 20))


def compute_weighted_score(chunk: dict) -> float:
    """
    Compute a weighted confidence score for a single retrieved chunk.

    Weights:
      Source authority:     30%
      Retrieval similarity: 20%
      Reranker score:       20%
      Review status:        10%
      Source present:       10%
      (cross-doc handled separately)
    """
    authority_str = chunk.get("sourceAuthority", SourceAuthority.UNKNOWN.value)
    try:
        authority = SourceAuthority(authority_str)
    except ValueError:
        authority = SourceAuthority.UNKNOWN

    status_str = chunk.get("reviewStatus", ReviewStatus.UNKNOWN.value)
    try:
        status = ReviewStatus(status_str)
    except ValueError:
        status = ReviewStatus.UNKNOWN

    a = _AUTHORITY_SCORE.get(authority, 0.4)
    r = _normalise_faiss(float(chunk.get("score", 0.7)))
    rr = _normalise_rerank(float(chunk.get("rerank_score", 0.0))) if "rerank_score" in chunk else r
    rs = _REVIEW_STATUS_SCORE.get(status, 0.7)
    src = 1.0 if chunk.get("source") else 0.4

    return 0.30 * a + 0.20 * r + 0.20 * rr + 0.10 * rs + 0.10 * src
    # Note: cross-doc agreement (10%) is computed in compute_confidence() below


def compute_confidence(hits: list[dict]) -> str:
    """
    Multi-factor confidence calculation replacing the old pure retrieval-score approach.

    Returns "High" | "Medium" | "Low" | "None".
    """
    rag_hits = [h for h in hits if not str(h.get("id", "")).startswith("web_")]
    if not rag_hits:
        return "None"

    # Cross-document agreement bonus: more independent sources → higher confidence
    unique_authorities = len({h.get("sourceAuthority", "unknown") for h in rag_hits})
    agreement_bonus = min(0.10, unique_authorities * 0.03)   # max +0.10 for 3+ sources

    # Use top-3 hits for scoring (not just top-1)
    top_hits = rag_hits[:3]
    scores = [compute_weighted_score(h) + agreement_bonus for h in top_hits]
    avg_score = sum(scores) / len(scores)

    if avg_score >= 0.72:
        return "High"
    if avg_score >= 0.52:
        return "Medium"
    return "Low"


def build_source_meta(chunk: dict) -> dict:
    """
    Build the source metadata dict returned to the frontend via _build_sources().
    Includes all fields needed for rich badge rendering.
    """
    return {
        "id":              chunk["id"],
        "topic":           chunk["topic"],
        "domain":          chunk["domain"],
        "score":           float(chunk.get("score", 0.0)),
        "rerankScore":     float(chunk["rerank_score"]) if "rerank_score" in chunk else None,
        "source":          chunk.get("source"),
        "lastVerifiedOn":  chunk.get("lastVerifiedOn"),
        "verifiedBy":      chunk.get("verifiedBy", "human"),
        # Enriched fields
        "documentType":    chunk.get("documentType", DocumentType.GENERAL.value),
        "sourceAuthority": chunk.get("sourceAuthority", SourceAuthority.UNKNOWN.value),
        "reviewStatus":    chunk.get("reviewStatus", ReviewStatus.UNKNOWN.value),
        "reviewNote":      chunk.get("reviewNote", ""),
        "reviewFrequency": chunk.get("reviewFrequency", "Periodic"),
        "weightedScore":   round(compute_weighted_score(chunk), 3),
        "sourceUrl":       chunk.get("sourceUrl") or resolve_source_url(chunk),
    }
