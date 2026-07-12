"""
Usha's specialized mental health agents — internal only, invisible to the user.

The user sees ONE assistant (Usha). Internally, specialized agents collaborate:

  Agent 1 — Emotion Analyzer  (8B, fast):   detect emotional state, intensity, crisis signals
  Agent 2 — Content Organizer (Python):      classify chunks by support type vs. CBT vs. resources
  Agent 3 — Crisis Check      (Python):      hard-code crisis override when suicide/self-harm detected
  Agent 4 — Response Composer (70B):         synthesize one warm, natural Usha response

LLM calls: 2 total (8B analyzer + 70B composer) vs. 1 previously.
Added latency: ~150 ms for the 8B call.
"""
import json

from ai.context import trim_history
from ai.provider import chat
from config import GROQ_MODEL_FAST
from logger import get_logger

log = get_logger("usha_agents")

# ──────────────────────────────────────────────────────────────
# AGENT 1 — EMOTION ANALYZER
# ──────────────────────────────────────────────────────────────

_EMOTION_ANALYZER_SYSTEM = """\
You are an emotion classifier for Usha, a mental health support assistant.
Analyse the user's message and output ONLY valid JSON — no markdown, no explanation.

{
  "emotional_state": "grief|anxiety|depression|burnout|anger|loneliness|panic|hopeless|guilt|confused|neutral",
  "intensity": "low|medium|high|crisis",
  "crisis_type": null,
  "topic_type": "venting|advice_seeking|cbt|mindfulness|information|crisis|follow_up|gratitude",
  "needs_grounding": false,
  "needs_resources": false,
  "follow_up": null
}

Rules:
- emotional_state: single best match; "neutral" only if message is purely informational
- intensity: "crisis" only if there are explicit signals of suicide, self-harm, or imminent danger
- crisis_type: null unless intensity=="crisis" — then: "suicide" | "self_harm" | "abuse" | "violence"
- topic_type: "venting" = sharing feelings; "cbt" = reframing/thinking patterns; "mindfulness" = breathing/calm;
              "information" = asking about a mental health concept; "follow_up" = responding to Usha's question
- needs_grounding: true if user seems panicked, dissociated, or overwhelmed right now
- needs_resources: true if situation may benefit from a helpline or therapist referral
- follow_up: ONE natural question Usha could ask to understand the user better; null if sufficient context exists
Output ONLY the JSON object."""


async def analyze_emotional_state(query: str, history: list[dict]) -> dict:
    """
    Agent 1: Emotion Analyzer — fast 8B model call.
    Classifies the emotional state; falls back to safe defaults on failure.
    """
    default: dict = {
        "emotional_state": "neutral",
        "intensity": "low",
        "crisis_type": None,
        "topic_type": "venting",
        "needs_grounding": False,
        "needs_resources": False,
        "follow_up": None,
    }

    recent_text = ""
    if history:
        recent_text = "\nRecent conversation:\n" + "\n".join(
            f"{m['role'].upper()}: {m['content'][:180]}" for m in history[-4:]
        )

    messages = [
        {"role": "system", "content": _EMOTION_ANALYZER_SYSTEM},
        {"role": "user", "content": f"User message: {query}{recent_text}"},
    ]

    try:
        result = await chat(model=GROQ_MODEL_FAST, temperature=0.0, max_tokens=180, messages=messages)
        raw = result["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            raw = raw[4:] if raw.startswith("json") else raw
        parsed = json.loads(raw)
        return {**default, **{k: v for k, v in parsed.items() if k in default}}
    except Exception as err:
        log.warning("emotion_analyzer failed — using defaults", error=str(err))
        return default


# ──────────────────────────────────────────────────────────────
# AGENT 2 — CONTENT ORGANIZER (Python, no LLM)
# ──────────────────────────────────────────────────────────────

_EMOTIONAL_SUPPORT_KW = [
    "grief", "loss", "sadness", "loneliness", "isolation", "depression", "low mood",
    "feel empty", "hopeless", "worthless", "crying", "breakdown", "overwhelmed",
    "burnout", "exhausted", "tired", "drained", "anxious", "panic", "fear", "worry",
    "anger", "frustration", "stress", "relationship", "breakup", "divorce", "family",
]

_CBT_KW = [
    "thought reframing", "cognitive", "CBT", "cognitive behavioral", "behavior activation",
    "automatic thoughts", "cognitive distortion", "journaling", "thought record",
    "coping strategy", "self-compassion", "rumination", "catastrophizing",
    "mindset", "reframe", "pattern", "trigger", "belief",
]

_MINDFULNESS_KW = [
    "breathing", "meditation", "mindfulness", "grounding", "relaxation", "body scan",
    "present moment", "visualization", "progressive muscle", "deep breath",
    "5-4-3-2-1", "anchor", "calm", "centered", "stillness", "awareness",
]

_CRISIS_KW = [
    "suicide", "suicidal", "end my life", "kill myself", "self-harm", "cutting",
    "hurt myself", "don't want to live", "no reason to live", "crisis",
    "AASRA", "iCall", "helpline", "hotline", "emergency mental",
]

_RESOURCES_KW = [
    "therapist", "counselor", "psychologist", "psychiatrist", "therapy", "counseling",
    "helpline", "NIMHANS", "iCall", "AASRA", "Vandrevala", "Tele-MANAS",
    "professional help", "mental health professional", "appointment", "session",
]


def _kw_score(chunk: dict, keywords: list[str]) -> float:
    text = (chunk.get("topic", "") + " " + chunk.get("text", "")).lower()
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return hits / max(len(keywords), 1)


def organize_chunks(retrieved: list[dict], topic_type: str) -> dict:
    """
    Agent 2: Python-only chunk organizer.
    Classifies chunks into emotional_support, cbt, mindfulness, crisis, resources, general.
    Returns {"primary": [...], "secondary": [...], "general": [...]}.
    """
    # Choose scoring priority based on detected topic type
    if topic_type == "cbt":
        primary_kws, secondary_kws = _CBT_KW, _EMOTIONAL_SUPPORT_KW
    elif topic_type == "mindfulness":
        primary_kws, secondary_kws = _MINDFULNESS_KW, _EMOTIONAL_SUPPORT_KW
    elif topic_type == "crisis":
        primary_kws, secondary_kws = _CRISIS_KW, _RESOURCES_KW
    elif topic_type == "information":
        primary_kws, secondary_kws = _CBT_KW + _MINDFULNESS_KW, _EMOTIONAL_SUPPORT_KW
    else:  # venting, advice_seeking, follow_up, gratitude
        primary_kws, secondary_kws = _EMOTIONAL_SUPPORT_KW, _RESOURCES_KW

    primary: list[dict] = []
    secondary: list[dict] = []
    general: list[dict] = []

    for chunk in retrieved:
        p = _kw_score(chunk, primary_kws)
        s = _kw_score(chunk, secondary_kws)
        if p > 0.05 or s > 0.05:
            (primary if p >= s else secondary).append(chunk)
        else:
            general.append(chunk)

    return {"primary": primary, "secondary": secondary, "general": general}


# ──────────────────────────────────────────────────────────────
# AGENT 3 — CRISIS CHECK (Python, no LLM)
# Hard-coded override — never rely on LLM for life-safety decisions.
# ──────────────────────────────────────────────────────────────

_CRISIS_TRIGGER_PHRASES = [
    "suicide", "suicidal", "kill myself", "end my life", "want to die",
    "don't want to live", "no reason to live", "hurt myself", "self-harm",
    "cutting myself", "overdose", "jump off", "hang myself",
    "khatam kar lena chahta", "zindagi khatam", "jeena nahi chahta",
    "mar jana chahta", "khud ko hurt",
]


def is_crisis(query: str, emotion_analysis: dict) -> bool:
    """
    Agent 3: Hard-coded crisis detection — Python only, runs in microseconds.
    Returns True if the query contains explicit crisis signals OR the analyzer
    flagged intensity='crisis'.
    """
    if emotion_analysis.get("intensity") == "crisis":
        return True
    if emotion_analysis.get("crisis_type") is not None:
        return True
    q_lower = query.lower()
    return any(phrase in q_lower for phrase in _CRISIS_TRIGGER_PHRASES)


# ──────────────────────────────────────────────────────────────
# AGENT 4 — RESPONSE COMPOSER (message builder for 70B call)
# ──────────────────────────────────────────────────────────────

def build_composer_messages(
    *,
    query: str,
    history: list[dict],
    emotion_analysis: dict,
    organized_chunks: dict,
    crisis_override: bool,
    emotion: str,           # from outer graph's emotion detector
    lang: str,
    outer_context: str,
    confidence: str = "None",
) -> list[dict]:
    """
    Agent 4: Build the final message list for the 70B Response Composer.
    Improves on plain responder._build_messages() by:
      • Separating chunks by topic relevance
      • Injecting structured emotional analysis (state, intensity, crisis flag)
      • Hard-coding crisis safety override when detected
      • Surfacing a contextual follow-up question when appropriate
    """
    from ai.responder import PERSONA, LANG_INSTRUCTIONS, FALLBACK_LINKS, SOURCES_SECTION_PROMPT

    history = trim_history(history)
    persona = PERSONA["Mental Health"]
    lang_instr = LANG_INSTRUCTIONS.get(lang, LANG_INSTRUCTIONS["auto"])

    # Build organized knowledge sections
    primary_chunks  = organized_chunks.get("primary", [])
    secondary_chunks = organized_chunks.get("secondary", [])
    general_chunks  = organized_chunks.get("general", [])
    all_chunks = primary_chunks + secondary_chunks + general_chunks
    chunk_to_idx = {id(c): i + 1 for i, c in enumerate(all_chunks)}

    def _fmt_section(chunks: list[dict], title: str) -> str:
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
        _fmt_section(primary_chunks,   "Primary Support Content"),
        _fmt_section(secondary_chunks, "Additional Context"),
        _fmt_section(general_chunks,   "General Reference"),
    ]
    knowledge_block = "\n\n".join(s for s in sections if s) or \
        "(No specific knowledge retrieved — respond from empathy and general awareness)"

    # Emotional analysis block
    em_state    = emotion_analysis.get("emotional_state", "neutral")
    intensity   = emotion_analysis.get("intensity", "low")
    topic_type  = emotion_analysis.get("topic_type", "venting")
    follow_up   = emotion_analysis.get("follow_up")
    needs_ground = emotion_analysis.get("needs_grounding", False)
    needs_res   = emotion_analysis.get("needs_resources", False)

    analysis_lines = [
        f"Detected emotional state: {em_state} (intensity: {intensity})",
        f"Conversation type: {topic_type}",
    ]
    if needs_ground:
        analysis_lines.append(
            "GROUNDING NEEDED — user seems overwhelmed or panicked. "
            "Consider offering a brief breathing or grounding exercise naturally."
        )
    if needs_res and not crisis_override:
        analysis_lines.append(
            "Resources may be helpful — mention a helpline or professional support once, naturally."
        )
    if follow_up and not crisis_override:
        analysis_lines.append(f"Suggested follow-up (ask only if natural): {follow_up}")
    if confidence in ("Low", "None"):
        analysis_lines.append(
            "Knowledge confidence: LOW — prioritize empathy and presence over information."
        )

    analysis_block = (
        "[INTERNAL EMOTIONAL ANALYSIS — guide your response; do not expose this block]\n"
        + "\n".join(analysis_lines)
    )

    # Crisis override block
    crisis_block = ""
    if crisis_override:
        crisis_block = """
[CRISIS OVERRIDE — HIGHEST PRIORITY]
The user has shown signals of suicidal ideation, self-harm, or immediate danger.

MANDATORY response structure:
1. One brief, non-clinical acknowledgment of what they shared (no clichés).
2. AASRA helpline: +91 9820466726 (24x7). iCall: 9152987821. Vandrevala: 1860-2662-345.
3. One grounding sentence — stay with them, don't rush.
4. Ask one simple question: "Can you tell me where you are right now?" or "Is there someone with you?"

DO NOT: start with advice, minimise what they shared, use phrases like "I understand how you feel",
promise that things will get better, or move to resources before acknowledging them.
DO NOT: redirect to another assistant while they are in crisis."""

    context_section = f"\nCONVERSATION CONTEXT: {outer_context}\n" if outer_context else ""
    fallback = FALLBACK_LINKS.get("Mental Health", "")

    system_prompt = f"""{persona}

LANGUAGE: {lang_instr}
{context_section}
{analysis_block}
{crisis_block}

Retrieved knowledge (cite inline with [1] [2] etc. — only when factual content is used):
{knowledge_block}

UNCERTAINTY RULE — if unsure about a psychological concept, say so. Never diagnose or prescribe.

Authoritative resources:
{fallback}

{SOURCES_SECTION_PROMPT}"""

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": m["role"], "content": m["content"]} for m in history)
    messages.append({"role": "user", "content": query})
    return messages
