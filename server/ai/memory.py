"""Per-session memory: rolling summary + goal detection.

Both run as background tasks after every response so they never block the user.
"""
from typing import Optional

from ai.provider import chat
from config import GROQ_MODEL_FAST
from logger import get_logger

log = get_logger("memory")


async def build_rolling_summary(
    messages: list[dict], persona: str, emotion_arc: Optional[list[str]] = None
) -> Optional[str]:
    """Compress recent messages into a short memory note (≤130 words)."""
    if len(messages) < 2:
        return None
    recent = messages[-20:]
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content'][:400]}" for m in recent
    )
    arc_note = ""
    if emotion_arc and len(emotion_arc) >= 2:
        arc_note = f"\nEmotion arc: {' → '.join(emotion_arc[-6:])}"
    try:
        result = await chat(
            model=GROQ_MODEL_FAST,
            temperature=0.1,
            max_tokens=220,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are {persona}'s memory system. Write a concise memory note (under 130 words) covering:\n"
                        "1. The user's main situation or concern\n"
                        "2. Their emotional trajectory (note any worsening or improvement)\n"
                        "3. Specific facts mentioned: names, locations, amounts, categories, dates\n"
                        "4. Any steps agreed on or progress made\n"
                        "Third person. Specific and factual. No bullet points. No generic filler."
                        + arc_note
                    ),
                },
                {"role": "user", "content": history_text},
            ],
        )
        return result["content"].strip() or None
    except Exception as err:
        log.warning("rolling summary failed", error=str(err))
        return None


async def detect_goal(
    query: str, domain: str, history: list[dict], existing_goal: Optional[str] = None
) -> Optional[str]:
    """Detect if the user has a concrete goal (e.g. 'file an RTI'). Returns ≤10 word phrase or None."""
    recent = history[-6:] if history else []
    history_text = "\n".join(f"{m['role']}: {m['content'][:150]}" for m in recent)

    existing_note = (
        f"\nCurrently tracked goal: '{existing_goal}'. "
        "Only return a goal if you detect something NEW or CHANGED. "
        "If the user is still working toward the same goal, reply NONE."
        if existing_goal
        else ""
    )

    try:
        result = await chat(
            model=GROQ_MODEL_FAST,
            temperature=0.05,
            max_tokens=30,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Detect if the user has a specific actionable goal they're working toward. "
                        "A goal is something concrete: 'file an RTI', 'apply for PM-JAY', "
                        "'draft a consumer complaint', 'find a therapist in Bangalore', "
                        "'understand divorce procedure', 'report cybercrime'. "
                        "If you detect a clear goal, reply with ONLY the goal as a short phrase (max 10 words). "
                        f"If there is no clear actionable goal, reply with exactly: NONE{existing_note}"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Domain: {domain}\nHistory:\n{history_text}\nLatest message: {query}",
                },
            ],
        )
        text = result["content"].strip()
        if not text or text.upper() == "NONE" or len(text) > 80:
            return None
        return text
    except Exception as err:
        log.warning("goal detection failed", error=str(err))
        return None
