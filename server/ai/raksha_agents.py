"""Internal pipeline for Raksha's safety responses. 2 LLM calls: 8B classifier + 70B composer."""
import json
from typing import Optional

from ai.context import trim_history
from ai.provider import chat
from ai.utils import _kw_score
from config import GROQ_MODEL_FAST
from logger import get_logger

log = get_logger("raksha_agents")

# AGENT 1 — SITUATION CLASSIFIER
_SITUATION_CLASSIFIER_SYSTEM = """\
You are a safety situation classifier for Raksha, an Indian personal safety assistant.
Analyse the user's message and output ONLY valid JSON — no markdown, no explanation.

{
  "situation_type": "active_emergency|recent_incident|cyber_crime|safety_awareness|disaster",
  "threat_category": "violence|domestic_violence|sexual_assault|stalking|blackmail|trafficking|medical|fire|accident|cyber_fraud|upi_scam|identity_theft|natural_disaster|general",
  "urgency": "immediate|recent|informational",
  "needs_helpline": true,
  "needs_evidence_preservation": false,
  "needs_safety_plan": false,
  "needs_reporting_steps": false,
  "is_child_involved": false,
  "follow_up": null
}

Rules:
- situation_type: "active_emergency" = happening right now; "recent_incident" = happened, now safe;
                  "cyber_crime" = online fraud/hack/blackmail; "safety_awareness" = general info;
                  "disaster" = flood/earthquake/fire/cyclone
- threat_category: single most specific match
- urgency: "immediate" = danger right now; "recent" = happened in last days/weeks; "informational" = general
- needs_helpline: true for immediate/recent incidents or if user asks for numbers
- needs_evidence_preservation: true for cyber crimes, recent incidents, harassment cases
- needs_safety_plan: true for active_emergency or domestic violence situations
- needs_reporting_steps: true if user asks how or where to report
- is_child_involved: true if a minor appears to be at risk (POCSO triggers)
- follow_up: ONE question that changes the safety advice; null if sufficient context
Output ONLY the JSON object."""

async def classify_situation(query: str, history: list[dict]) -> dict:
    """
    Agent 1: Situation Classifier — fast 8B model call.
    Falls back to safe, high-urgency defaults on failure.
    """
    # Safe default: assume recent incident, provide helplines
    default: dict = {
        "situation_type": "recent_incident",
        "threat_category": "general",
        "urgency": "informational",
        "needs_helpline": True,
        "needs_evidence_preservation": False,
        "needs_safety_plan": False,
        "needs_reporting_steps": False,
        "is_child_involved": False,
        "follow_up": None,
    }

    recent_text = ""
    if history:
        recent_text = "\nRecent conversation:\n" + "\n".join(
            f"{m['role'].upper()}: {m['content'][:180]}" for m in history[-4:]
        )

    messages = [
        {"role": "system", "content": _SITUATION_CLASSIFIER_SYSTEM},
        {"role": "user", "content": f"User message: {query}{recent_text}"},
    ]

    try:
        result = await chat(model=GROQ_MODEL_FAST, temperature=0.0, max_tokens=220, messages=messages)
        raw = result["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            raw = raw[4:] if raw.startswith("json") else raw
        parsed = json.loads(raw)
        merged = {**default, **{k: v for k, v in parsed.items() if k in default}}
        # Safety-first: if threat is violent/DV/assault, always provide helpline
        if merged["threat_category"] in ("violence", "domestic_violence", "sexual_assault", "stalking", "trafficking"):
            merged["needs_helpline"] = True
        return merged
    except Exception as err:
        log.warning("situation_classifier failed — using defaults", error=str(err))
        return default

# AGENT 2 — RESOURCE FILTER (Python, no LLM)
_EMERGENCY_CONTACT_KW = [
    "112", "100", "1091", "1098", "1930", "181", "14567", "7827170170",
    "helpline", "emergency", "police", "ambulance", "fire brigade", "cybercrime.gov.in",
]

_WOMEN_SAFETY_KW = [
    "domestic violence", "PWDVA", "One Stop Centre", "shelter home", "NCW", "women helpline",
    "1091", "181", "sexual assault", "harassment", "stalking", "safety women",
]

_CYBER_SAFETY_KW = [
    "cybercrime", "UPI", "OTP", "fraud", "phishing", "identity theft", "1930",
    "IT Act", "Section 66", "online scam", "social media", "deepfake", "blackmail",
    "cybercrime.gov.in", "NFT", "investment fraud", "fake job",
]

_LEGAL_RIGHTS_SAFETY_KW = [
    "FIR", "complaint", "protection order", "PWDVA", "POCSO", "evidence",
    "police station", "magistrate", "report", "Section 154",
]

_DISASTER_KW = [
    "flood", "earthquake", "cyclone", "fire", "landslide", "heatwave",
    "tsunami", "disaster", "NDRF", "SDRF", "evacuation", "relief camp",
]

def organize_chunks(retrieved: list[dict], analysis: dict) -> dict:
    """
    Agent 2: Classify retrieved chunks by what they contain.
    Returns {"contacts": [...], "women": [...], "cyber": [...], "legal": [...], "disaster": [...], "general": [...]}.
    """
    contacts: list[dict] = []
    women: list[dict] = []
    cyber: list[dict] = []
    legal: list[dict] = []
    disaster: list[dict] = []
    general: list[dict] = []

    for chunk in retrieved:
        scores = {
            "contacts": _kw_score(chunk, _EMERGENCY_CONTACT_KW),
            "women":    _kw_score(chunk, _WOMEN_SAFETY_KW),
            "cyber":    _kw_score(chunk, _CYBER_SAFETY_KW),
            "legal":    _kw_score(chunk, _LEGAL_RIGHTS_SAFETY_KW),
            "disaster": _kw_score(chunk, _DISASTER_KW),
        }
        best_key = max(scores, key=lambda k: scores[k])
        best_val = scores[best_key]

        if best_val < 0.03:
            general.append(chunk)
        elif best_key == "contacts":
            contacts.append(chunk)
        elif best_key == "women":
            women.append(chunk)
        elif best_key == "cyber":
            cyber.append(chunk)
        elif best_key == "legal":
            legal.append(chunk)
        else:
            disaster.append(chunk)

    return {
        "contacts": contacts,
        "women": women,
        "cyber": cyber,
        "legal": legal,
        "disaster": disaster,
        "general": general,
    }

# AGENT 3 — SAFETY PLAN BUILDER (Python, no LLM)
# Deterministic immediate-action plans for active emergencies.
_SAFETY_PLANS: dict[str, list[str]] = {
    "violence": [
        "Call 112 (unified emergency) immediately — say 'I need police'.",
        "Move to a locked room, neighbour's house, or any public space with other people.",
        "If you can't call, send your location to someone you trust via WhatsApp.",
        "Do not try to reason with or calm an attacker — leave first.",
        "Go to the nearest police station / One Stop Centre once you are safe.",
    ],
    "domestic_violence": [
        "If in immediate danger: call 112 (emergency) or 1091 (women's helpline).",
        "Leave the house if it is safe to do so — take your phone, ID, and any cash.",
        "Go to a trusted neighbour, family member, or the nearest One Stop Centre.",
        "One Stop Centre provides shelter, medical help, police help, and legal aid free of cost.",
        "Once safe, photograph injuries, save threatening messages — this is evidence.",
    ],
    "sexual_assault": [
        "Call 112 immediately. You have the right to a free medical exam and FIR registration.",
        "Do not wash, shower, or change clothes before the medical exam — evidence is critical.",
        "Go to the nearest government hospital's Emergency department.",
        "You can file a Zero FIR at any police station regardless of jurisdiction.",
        "One Stop Centre (at most district hospitals) provides free medical, legal, and counseling support.",
    ],
    "stalking": [
        "Do not engage or respond to the stalker.",
        "Document every incident: date, time, description, screenshots of messages.",
        "File a police complaint immediately — stalking is a cognizable offence under BNS Section 78.",
        "Share your daily schedule only with trusted people.",
        "Consider varying your route and timings if the stalking is physical.",
    ],
    "fire": [
        "Alert everyone and activate the fire alarm.",
        "Call 101 (fire brigade) and 112 immediately.",
        "Evacuate the building using stairs — NEVER use lifts.",
        "Stay low to avoid smoke — crawl if necessary.",
        "Meet at the designated assembly point. Do not go back inside.",
    ],
    "medical": [
        "Call 102 or 108 (ambulance) immediately.",
        "If the person is unconscious: check breathing, do not move them unless in immediate danger.",
        "For choking: perform the Heimlich manoeuvre or call 112 for guidance.",
        "For cardiac arrest: start CPR if trained; the operator can guide you.",
        "Share exact location with the ambulance dispatcher.",
    ],
    "cyber_fraud": [
        "Call 1930 (National Cyber Crime Helpline) immediately — fastest way to freeze a fraudulent transaction.",
        "Block the fraudster's number and all payment access immediately.",
        "Report at cybercrime.gov.in — note the complaint ID for follow-up.",
        "Contact your bank's 24x7 helpline to put a hold on suspicious transactions.",
        "Do NOT share OTP, PIN, CVV, or password with anyone — banks never ask for these.",
    ],
    "upi_scam": [
        "Call 1930 within minutes — the 'golden hour' matters for fund recovery.",
        "Call your bank's 24x7 helpline and report the fraudulent transaction.",
        "Take a screenshot of the transaction ID from your UPI app before anything else.",
        "File a complaint at cybercrime.gov.in with transaction ID, fraudster's UPI ID, and screenshots.",
        "Block the sender on all platforms.",
    ],
    "blackmail": [
        "Do NOT pay the blackmailer — payment escalates demands.",
        "Do NOT delete the threatening messages — they are evidence.",
        "Screenshot everything: messages, profiles, transaction demands.",
        "Report at cybercrime.gov.in and call 1930.",
        "If intimate images are involved: File complaint under IT Act Section 67A/67B.",
        "Help is available — you are not at fault.",
    ],
    "general": [
        "Call 112 if you are in immediate physical danger.",
        "Move to a safe location with other people present.",
        "Contact a trusted person and share your location.",
        "Document the situation as much as possible.",
        "Call 100 (police) to file a formal complaint.",
    ],
}

def get_safety_plan(threat_category: str, urgency: str) -> Optional[list[str]]:
    """
    Agent 3: Return a deterministic immediate-action safety plan.
    Only for active emergencies (urgency='immediate') or high-risk recent incidents.
    """
    if urgency not in ("immediate", "recent"):
        return None
    return _SAFETY_PLANS.get(threat_category, _SAFETY_PLANS["general"])

# AGENT 4 — RESPONSE COMPOSER (message builder for 70B call)
def build_composer_messages(
    *,
    query: str,
    history: list[dict],
    situation_analysis: dict,
    organized_chunks: dict,
    safety_plan: Optional[list[str]],
    lang: str,
    outer_context: str,
    confidence: str = "None",
) -> list[dict]:
    """
    Agent 4: Build the final message list for the 70B Response Composer.
    Improves on plain responder._build_messages() by:
      • Organizing chunks by contact/women/cyber/legal/disaster type
      • Injecting structured situation analysis (type, urgency, threat)
      • Including a deterministic safety plan for emergencies
      • Flagging POCSO when a child is involved
    """
    from ai.responder import PERSONA, LANG_INSTRUCTIONS, FALLBACK_LINKS, SOURCES_SECTION_PROMPT

    history = trim_history(history)
    persona = PERSONA["Safety"]
    lang_instr = LANG_INSTRUCTIONS.get(lang, LANG_INSTRUCTIONS["auto"])

    contacts   = organized_chunks.get("contacts", [])
    women      = organized_chunks.get("women", [])
    cyber      = organized_chunks.get("cyber", [])
    legal_r    = organized_chunks.get("legal", [])
    disaster   = organized_chunks.get("disaster", [])
    general    = organized_chunks.get("general", [])
    all_chunks = contacts + women + cyber + legal_r + disaster + general
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
        _fmt(contacts, "Emergency Contacts & Helplines"),
        _fmt(women,    "Women's Safety Resources"),
        _fmt(cyber,    "Cyber Safety & Fraud"),
        _fmt(legal_r,  "Legal Rights & Reporting"),
        _fmt(disaster, "Disaster Safety"),
        _fmt(general,  "General Safety Information"),
    ]
    knowledge_block = "\n\n".join(s for s in sections if s) or \
        "(No specific safety knowledge retrieved — use general safety guidance)"

    # Situation analysis block
    sit_type   = situation_analysis.get("situation_type", "safety_awareness")
    threat_cat = situation_analysis.get("threat_category", "general")
    urgency    = situation_analysis.get("urgency", "informational")
    child      = situation_analysis.get("is_child_involved", False)
    needs_evid = situation_analysis.get("needs_evidence_preservation", False)
    needs_rep  = situation_analysis.get("needs_reporting_steps", False)
    follow_up  = situation_analysis.get("follow_up")

    analysis_lines = [
        f"Situation type: {sit_type}",
        f"Threat category: {threat_cat}",
        f"Urgency: {urgency}" + (" — RESPOND WITH IMMEDIATE ACTION STEPS FIRST" if urgency == "immediate" else ""),
    ]
    if child:
        analysis_lines.append(
            "CHILD INVOLVED — POCSO Act applies. Mandatory reporting obligations. "
            "Provide CHILDLINE 1098 prominently. Emphasize specialized support."
        )
    if needs_evid:
        analysis_lines.append("User needs evidence preservation guidance.")
    if needs_rep:
        analysis_lines.append("User needs specific reporting steps.")
    if follow_up and urgency != "immediate":
        analysis_lines.append(f"Consider asking: {follow_up}")

    analysis_block = (
        "[INTERNAL SITUATION ANALYSIS — guide your response; do not expose this block]\n"
        + "\n".join(analysis_lines)
    )

    # Safety plan block (only for active/recent emergencies)
    plan_block = ""
    if safety_plan:
        plan_block = (
            "\n[IMMEDIATE SAFETY PLAN — include this in your response for this emergency]\n"
            + "\n".join(f"• {step}" for step in safety_plan)
            + "\n"
        )

    context_section = f"\nCONVERSATION CONTEXT: {outer_context}\n" if outer_context else ""
    fallback = FALLBACK_LINKS.get("Safety", "")

    system_prompt = f"""{persona}

LANGUAGE: {lang_instr}

SCOPE RULE — Raksha handles safety emergencies, physical health symptoms, cybercrime, domestic violence, and disasters.
If the query is about legal rights, government schemes, or emotional/mental health only — respond in 1-2 lines and redirect:
Umang for legal matters, Aarogya for government schemes, Usha for emotional support.

{context_section}
{analysis_block}
{plan_block}
Retrieved knowledge (cite inline with [1] [2] etc.):
{knowledge_block}

UNCERTAINTY RULE — if unsure about a helpline or resource, say so. Never invent phone numbers.

Authoritative resources:
{fallback}

{SOURCES_SECTION_PROMPT}"""

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": m["role"], "content": m["content"]} for m in history)
    messages.append({"role": "user", "content": query})
    return messages
