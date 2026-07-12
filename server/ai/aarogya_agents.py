"""
Aarogya's specialized government scheme agents — internal only, invisible to the user.

The user sees ONE assistant (Aarogya). Internally, specialized agents collaborate:

  Agent 1 — Scheme Analyzer    (8B, fast):   classify query, extract user profile, detect missing info
  Agent 2 — Eligibility Filter (Python):     score chunks by scheme category relevance
  Agent 3 — State Specialist   (Python):     boost state-specific scheme chunks
  Agent 4 — Doc Checker        (Python):     derive required document list from scheme category
  Agent 5 — Response Composer  (70B):        synthesize one helpful, practical Aarogya response

LLM calls: 2 total (8B analyzer + 70B composer) vs. 1 previously.
"""
import json
from typing import Optional

from ai.context import trim_history
from ai.provider import chat
from config import GROQ_MODEL_FAST
from logger import get_logger

log = get_logger("aarogya_agents")

# ──────────────────────────────────────────────────────────────
# AGENT 1 — SCHEME ANALYZER
# ──────────────────────────────────────────────────────────────

_SCHEME_ANALYZER_SYSTEM = """\
You are a government scheme classifier for Aarogya, an Indian government benefits assistant.
Analyse the user's query and output ONLY valid JSON — no markdown, no explanation.

{
  "scheme_category": "Health|Education|Housing|Agriculture|Employment|Food|Women|Disability|Pension|Startup|Unorganised|General",
  "state_mentioned": null,
  "income_level": null,
  "social_category": null,
  "occupation": null,
  "gender": null,
  "needs_eligibility_check": true,
  "needs_document_list": false,
  "needs_application_steps": false,
  "is_specific_scheme": false,
  "specific_scheme_name": null,
  "missing_info": null
}

Rules:
- scheme_category: single best match
- state_mentioned: Indian state name if clearly mentioned, else null
- income_level: "BPL" | "APL" | "EWS" | "LIG" | "MIG" | "General" | null (null if not mentioned)
- social_category: "SC" | "ST" | "OBC" | "General" | "Minority" | "Disabled" | null
- occupation: "farmer" | "student" | "employee" | "self_employed" | "unemployed" | "disabled" | "senior_citizen" | "unorganised_worker" | null
- gender: "female" | "male" | null
- needs_eligibility_check: true if we need to verify who qualifies
- needs_document_list: true if user asks what documents are needed
- needs_application_steps: true if user asks how to apply
- is_specific_scheme: true if user named a specific scheme (PM-JAY, PM Kisan, MGNREGA, etc.)
- specific_scheme_name: the scheme name if is_specific_scheme=true, else null
- missing_info: ONE specific question whose answer changes which schemes to recommend; null if sufficient
Output ONLY the JSON object."""


async def analyze_scheme_query(query: str, history: list[dict]) -> dict:
    """
    Agent 1: Scheme Analyzer — fast 8B model call.
    Falls back to safe defaults on failure.
    """
    default: dict = {
        "scheme_category": "General",
        "state_mentioned": None,
        "income_level": None,
        "social_category": None,
        "occupation": None,
        "gender": None,
        "needs_eligibility_check": True,
        "needs_document_list": False,
        "needs_application_steps": False,
        "is_specific_scheme": False,
        "specific_scheme_name": None,
        "missing_info": None,
    }

    recent_text = ""
    if history:
        recent_text = "\nRecent conversation:\n" + "\n".join(
            f"{m['role'].upper()}: {m['content'][:180]}" for m in history[-4:]
        )

    messages = [
        {"role": "system", "content": _SCHEME_ANALYZER_SYSTEM},
        {"role": "user", "content": f"User query: {query}{recent_text}"},
    ]

    try:
        result = await chat(model=GROQ_MODEL_FAST, temperature=0.0, max_tokens=220, messages=messages)
        raw = result["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            raw = raw[4:] if raw.startswith("json") else raw
        parsed = json.loads(raw)
        return {**default, **{k: v for k, v in parsed.items() if k in default}}
    except Exception as err:
        log.warning("scheme_analyzer failed — using defaults", error=str(err))
        return default


# ──────────────────────────────────────────────────────────────
# AGENT 2 — ELIGIBILITY FILTER + AGENT 3 — STATE SPECIALIST (Python, no LLM)
# ──────────────────────────────────────────────────────────────

_CATEGORY_KW: dict[str, list[str]] = {
    "Health":      ["health", "ayushman", "PM-JAY", "CGHS", "insurance", "hospital", "medical", "PMJAY", "treatment"],
    "Education":   ["scholarship", "fellowship", "stipend", "education", "student", "NSP", "fee waiver", "coaching"],
    "Housing":     ["housing", "PMAY", "shelter", "awas", "home loan", "pradhan mantri awas", "affordable housing"],
    "Agriculture": ["farmer", "kisan", "PM Kisan", "crop insurance", "PMFBY", "agriculture", "khet", "irrigation"],
    "Employment":  ["employment", "MGNREGA", "PMKVY", "skill", "training", "job", "PMEGP", "Mudra", "rozgar"],
    "Food":        ["ration", "PDS", "food", "ration card", "Ujjwala", "PMGKAY", "BPL ration", "free grain"],
    "Women":       ["women", "mahila", "sukanya", "beti bachao", "maternity", "self-help group", "SHG", "widow"],
    "Disability":  ["disability", "divyang", "ADIP", "handicapped", "specially abled", "disability certificate"],
    "Pension":     ["pension", "atal pension", "APY", "NPS", "old age", "senior citizen", "EPF", "PPF"],
    "Startup":     ["startup", "entrepreneur", "DPIIT", "mudra", "Stand Up India", "incubation", "innovation"],
    "Unorganised": ["unorganised", "e-Shram", "gig worker", "daily wage", "labour", "construction", "migrant"],
}

_APPLICATION_KW = [
    "apply", "application", "how to", "register", "steps", "process", "portal",
    "kaise", "kare", "submit", "enroll", "form", "online", "CSC", "common service",
]

_DOCUMENT_KW = [
    "document", "certificate", "proof", "required", "needed", "aadhaar", "income",
    "caste", "papers", "list", "kya chahiye", "kaun si", "attachment",
]


def _kw_score(chunk: dict, keywords: list[str]) -> float:
    text = (chunk.get("topic", "") + " " + chunk.get("text", "")).lower()
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return hits / max(len(keywords), 1)


def _state_boost(chunk: dict, state: Optional[str]) -> float:
    if not state:
        return 0.0
    text = (chunk.get("topic", "") + " " + chunk.get("text", "")).lower()
    return 0.15 if state.lower() in text else 0.0


def organize_chunks(retrieved: list[dict], analysis: dict) -> dict:
    """
    Agents 2 & 3: Classify retrieved chunks by scheme category and state relevance.
    Returns {"scheme": [...], "application": [...], "document": [...], "general": [...]}.
    """
    category    = analysis.get("scheme_category", "General")
    state       = analysis.get("state_mentioned")
    needs_docs  = analysis.get("needs_document_list", False)
    needs_steps = analysis.get("needs_application_steps", False)

    category_kws  = _CATEGORY_KW.get(category, [])
    app_kws       = _APPLICATION_KW if needs_steps else []
    doc_kws       = _DOCUMENT_KW if needs_docs else []

    scheme: list[dict] = []
    application: list[dict] = []
    document: list[dict] = []
    general: list[dict] = []

    for chunk in retrieved:
        sc = _kw_score(chunk, category_kws) + _state_boost(chunk, state)
        ap = _kw_score(chunk, app_kws) if app_kws else 0.0
        dc = _kw_score(chunk, doc_kws) if doc_kws else 0.0

        best = max(sc, ap, dc)
        if best < 0.03:
            general.append(chunk)
        elif sc >= ap and sc >= dc:
            scheme.append(chunk)
        elif ap >= dc:
            application.append(chunk)
        else:
            document.append(chunk)

    return {
        "scheme":      scheme,
        "application": application,
        "document":    document,
        "general":     general,
    }


# ──────────────────────────────────────────────────────────────
# AGENT 4 — DOCUMENT CHECKER (Python, no LLM)
# ──────────────────────────────────────────────────────────────

_SCHEME_DOCS: dict[str, list[str]] = {
    "Health": [
        "Aadhaar card",
        "Ration card (for BPL families)",
        "Income certificate (from SDM/tehsildar)",
        "Bank account passbook (DBT)",
        "Caste certificate (if SC/ST/OBC)",
        "Age proof (for senior citizen schemes)",
    ],
    "Education": [
        "Aadhaar card",
        "Income certificate (parental)",
        "Caste certificate (if SC/ST/OBC/minority)",
        "Previous year marksheet / result",
        "Bonafide / enrollment certificate from institution",
        "Bank account passbook (for DBT)",
        "Fee receipt from institution",
    ],
    "Housing": [
        "Aadhaar card",
        "Income certificate (below ₹3L/6L/18L depending on category)",
        "Caste certificate (SC/ST/OBC applicants)",
        "Land/property documents (existing property proof for exclusion)",
        "Bank account passbook",
        "Passport-size photographs",
    ],
    "Agriculture": [
        "Aadhaar card (linked to land records)",
        "Land ownership documents (Khasra/Khatauni/ROR)",
        "Bank account passbook (DBT)",
        "PM Kisan registration number (if already registered)",
        "Caste certificate (for SC/ST schemes)",
    ],
    "Employment": [
        "Aadhaar card",
        "Job card / MGNREGA card (for rural employment)",
        "Bank account passbook",
        "Skill certificate (for PMKVY / Skill India)",
        "Educational certificates (for some skill programs)",
        "Income certificate (for subsidized loans)",
    ],
    "Food": [
        "Aadhaar card",
        "Existing ration card OR proof of residence",
        "Income certificate / BPL certificate",
        "Family photograph (for new ration card applications)",
        "Gas connection document (for Ujjwala applicants)",
    ],
    "Women": [
        "Aadhaar card",
        "Birth certificate (for girl child schemes)",
        "Income certificate (for income-based schemes)",
        "Bank account in girl child's name (Sukanya Samriddhi)",
        "Marriage certificate (if applicable)",
        "Caste certificate (if applicable)",
    ],
    "Disability": [
        "Aadhaar card",
        "Disability certificate from government hospital (40%+ disability for most schemes)",
        "Income certificate",
        "Bank account passbook",
        "Passport-size photographs",
    ],
    "Pension": [
        "Aadhaar card",
        "Age proof (birth certificate, school certificate, or Aadhaar)",
        "Bank account passbook",
        "Income certificate (APL/BPL for eligibility)",
        "EPFO UAN (for provident fund related claims)",
    ],
    "Startup": [
        "Aadhaar card / PAN card",
        "DPIIT registration certificate (if registered startup)",
        "Business plan / pitch deck",
        "Bank account in business name",
        "GST registration (if applicable)",
        "Caste / gender certificate (for Stand Up India, SC/ST/Women)",
    ],
    "Unorganised": [
        "Aadhaar card",
        "e-Shram card (register at eshram.gov.in first)",
        "Bank account passbook",
        "Self-declaration of occupation",
        "Mobile number (linked to Aadhaar for OTP)",
    ],
    "General": [
        "Aadhaar card",
        "Income certificate",
        "Caste certificate (if applicable)",
        "Bank account passbook",
        "Age proof",
        "Residence proof",
    ],
}


def get_document_checklist(scheme_category: str) -> list[str]:
    """Agent 4: Return standard document checklist for a scheme category."""
    return _SCHEME_DOCS.get(scheme_category, _SCHEME_DOCS["General"])


# ──────────────────────────────────────────────────────────────
# AGENT 5 — RESPONSE COMPOSER (message builder for 70B call)
# ──────────────────────────────────────────────────────────────

def build_composer_messages(
    *,
    query: str,
    history: list[dict],
    scheme_analysis: dict,
    organized_chunks: dict,
    document_checklist: Optional[list[str]],
    lang: str,
    outer_context: str,
    confidence: str = "None",
) -> list[dict]:
    """
    Agent 5: Build the final message list for the 70B Response Composer.
    Improves on plain responder._build_messages() by:
      • Organizing chunks into scheme vs. application vs. document sections
      • Injecting structured scheme analysis (category, profile, missing info)
      • Surfacing document checklist when needed
    """
    from ai.responder import PERSONA, LANG_INSTRUCTIONS, FALLBACK_LINKS, SOURCES_SECTION_PROMPT

    history = trim_history(history)
    persona = PERSONA["Government Schemes"]
    lang_instr = LANG_INSTRUCTIONS.get(lang, LANG_INSTRUCTIONS["auto"])

    scheme_chunks  = organized_chunks.get("scheme", [])
    app_chunks     = organized_chunks.get("application", [])
    doc_chunks     = organized_chunks.get("document", [])
    general_chunks = organized_chunks.get("general", [])
    all_chunks = scheme_chunks + app_chunks + doc_chunks + general_chunks
    chunk_to_idx = {id(c): i + 1 for i, c in enumerate(all_chunks)}

    def _fmt(chunks: list[dict], title: str) -> str:
        if not chunks:
            return ""
        parts = [f"[{title}]"]
        for c in chunks:
            url_line = f"\n  URL: {c['sourceUrl']}" if c.get("sourceUrl") else ""
            auth_line = f"\n  Authority: {c['source']}" if c.get("source") else ""
            parts.append(
                f"[Source {chunk_to_idx[id(c)]} — {c['topic']}]{url_line}{auth_line}\n{c['text'].strip()}"
            )
        return "\n\n".join(parts)

    sections = [
        _fmt(scheme_chunks,  "Scheme Information"),
        _fmt(app_chunks,     "Application Process"),
        _fmt(doc_chunks,     "Document Requirements"),
        _fmt(general_chunks, "Additional Context"),
    ]
    knowledge_block = "\n\n".join(s for s in sections if s) or \
        "(No specific scheme knowledge retrieved — answer carefully; suggest myscheme.gov.in)"

    # Analysis block
    cat        = scheme_analysis.get("scheme_category", "General")
    state      = scheme_analysis.get("state_mentioned")
    income     = scheme_analysis.get("income_level")
    soc_cat    = scheme_analysis.get("social_category")
    occupation = scheme_analysis.get("occupation")
    gender     = scheme_analysis.get("gender")
    specific   = scheme_analysis.get("specific_scheme_name")
    missing    = scheme_analysis.get("missing_info")
    needs_docs = scheme_analysis.get("needs_document_list", False)
    needs_steps= scheme_analysis.get("needs_application_steps", False)

    analysis_lines = [f"Scheme category: {cat}"]
    profile_parts = [x for x in [state, income, soc_cat, occupation, gender] if x]
    if profile_parts:
        analysis_lines.append(f"User profile: {', '.join(profile_parts)}")
    if specific:
        analysis_lines.append(f"Specific scheme requested: {specific}")
    focus = [x for x, flag in [("application steps", needs_steps), ("document list", needs_docs)] if flag]
    if focus:
        analysis_lines.append(f"Response focus: {', '.join(focus)}")
    if missing:
        analysis_lines.append(f"Missing info — ask if not already answered: {missing}")
    if confidence in ("Low", "None") and not scheme_chunks:
        analysis_lines.append(
            "RAG confidence: LOW — Retrieved scheme information is weak. "
            "Acknowledge uncertainty; direct user to myscheme.gov.in for verification."
        )

    analysis_block = (
        "[INTERNAL SCHEME ANALYSIS — guide your response; do not expose this block]\n"
        + "\n".join(analysis_lines)
    )

    # Document checklist block
    doc_block = ""
    if document_checklist and needs_docs:
        doc_block = (
            "\n[DOCUMENT CHECKLIST for this scheme category — include in response]\n"
            + "\n".join(f"• {d}" for d in document_checklist)
            + "\n"
        )

    context_section = f"\nCONVERSATION CONTEXT: {outer_context}\n" if outer_context else ""
    fallback = FALLBACK_LINKS.get("Government Schemes", "")

    system_prompt = f"""{persona}

LANGUAGE: {lang_instr}
{context_section}
{analysis_block}

Retrieved knowledge (cite inline with [1] [2] etc.):
{knowledge_block}
{doc_block}
UNCERTAINTY RULE — if unsure about a scheme's status or amount, say so. Never invent benefit amounts.
Verify eligibility figures from official portals rather than guessing.

CITATION FORMAT — [1] [2] inline after the sentence.

Authoritative portals:
{fallback}

{SOURCES_SECTION_PROMPT}"""

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": m["role"], "content": m["content"]} for m in history)
    messages.append({"role": "user", "content": query})
    return messages
