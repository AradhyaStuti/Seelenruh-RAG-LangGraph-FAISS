"""Self-evolving memory system — runs autonomously after every response.

Two capabilities:
  1. Rolling summary   — compressed snapshot of the whole conversation so far,
                          stored per (user, session) and fetched at the start of
                          the next turn to give the LLM persistent cross-turn memory.
  2. Goal detection    — detects if the user is working toward a concrete actionable
                          goal (e.g. "file an RTI", "apply for PM-JAY") and tracks it
                          so the agent can proactively guide progress across turns.
"""
from typing import Optional

from ai.provider import chat
from config import GROQ_MODEL_FAST
from logger import get_logger

log = get_logger("memory")


async def build_rolling_summary(messages: list[dict], persona: str) -> Optional[str]:
    """Compress the last 20 exchanges into a concise memory note.

    Called autonomously in the background after every assistant reply —
    never blocks the user-facing response.
    """
    if len(messages) < 2:
        return None
    recent = messages[-20:]
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content'][:250]}" for m in recent
    )
    try:
        result = await chat(
            model=GROQ_MODEL_FAST,
            temperature=0.1,
            max_tokens=180,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are {persona}'s memory system. Write a concise memory note (under 130 words) covering:\n"
                        "1. The user's main situation or concern\n"
                        "2. Their emotional tone (e.g. anxious, hopeful, frustrated)\n"
                        "3. Specific facts mentioned: names, locations, amounts, categories, dates\n"
                        "4. Any steps agreed on or progress made\n"
                        "Third person. Specific and factual. No bullet points. No generic filler."
                    ),
                },
                {"role": "user", "content": history_text},
            ],
        )
        return result["content"].strip() or None
    except Exception as err:
        log.warning("rolling summary failed", error=str(err))
        return None


async def detect_goal(query: str, domain: str, history: list[dict]) -> Optional[str]:
    """Detect if the user is working toward a specific actionable goal.

    Returns a short goal phrase (≤ 10 words) or None.
    Runs as part of the classify step — fast model, low temperature.
    """
    recent = history[-6:] if history else []
    history_text = "\n".join(f"{m['role']}: {m['content'][:150]}" for m in recent)
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
                        "If there is no clear actionable goal yet, reply with exactly: NONE"
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
