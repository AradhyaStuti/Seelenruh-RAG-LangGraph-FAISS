"""Emotion classifier — 11-way categorical for tone adaptation.

Expanded from 6 → 11 states to give composers finer-grained tone signals:
  hopeless, overwhelmed, anxious, frustrated, numb
  (added to the existing: sad, angry, scared, confused, happy, neutral)

The classifier runs in parallel with intent detection. It falls back to
"neutral" on any failure so it never blocks a response.
"""
from ai.provider import chat_json
from config import GROQ_MODEL_FAST
from logger import get_logger

log = get_logger("emotion")

VALID = {
    "sad", "angry", "happy", "scared", "confused", "neutral",
    "hopeless", "overwhelmed", "anxious", "frustrated", "numb",
}

SYSTEM = """\
Detect the dominant emotion in a user message. The user may write in English, Hindi (Devanagari or Roman), Hinglish, or German.

Return ONLY valid JSON: {"emotion": "<value>", "secondary": "<value or null>"}

Primary values (choose the most specific match):
  sad         — grief, sorrow, crying, heartbreak
  hopeless    — despair, "no point", giving up, "nothing matters", zindagi mein kuch nahi
  overwhelmed — too much at once, can't cope, drowning in responsibilities, sab kuch zyada ho gaya
  anxious     — worry, nervousness, racing thoughts, what-ifs, dar lag raha hai
  frustrated  — blocked, repeatedly failing, unfair situation, gussa aata hai but directed at circumstances
  angry       — intense rage, lashing out, injustice, taunt, betrayal
  numb        — disconnected, empty, nothing feels real, "I don't feel anything", andar se khali
  scared      — immediate fear, threat, danger, koi maar raha hai
  confused    — lost, unclear, don't know what to do, samajh nahi aa raha
  happy       — positive, grateful, relieved, excited, khushi
  neutral     — purely informational, no emotional signal present

secondary: the second-strongest emotion if clearly present; null otherwise

Rules:
- hopeless and numb are DIFFERENT: hopeless = pain + despair; numb = absence of feeling
- overwhelmed ≠ anxious: overwhelmed = too much happening; anxious = fear of what might happen
- frustrated ≠ angry: frustrated = blocked/helpless anger; angry = outward, blaming
- Use "neutral" ONLY when there is genuinely no emotional signal — not as a default
- Prefer the more specific emotion over a general one when in doubt

Few-shot examples:
"I feel so lost and empty" → hopeless
"rone ka mann kar raha hai" → sad
"koi raasta nahi dikh raha, kya fayda" → hopeless
"bahut zyada ho gaya sab kuch, handle nahi ho raha" → overwhelmed
"kya hoga mere saath, sab galat ho raha hai" → anxious
"boss ne phir se meri baat nahi suni, bahut irritating hai" → frustrated
"mujhe itna gussa aa raha hai, sab barbad kar dena chahta hoon" → angry
"andar se kuch feel hi nahi hota" → numb
"koi mujhe maar raha hai" → scared
"mujhe bilkul samajh nahi aata yeh process" → confused
"scholarship mil gayi! bahut khush hoon" → happy
"RTI kaise file karte hain" → neutral
"mera account hack ho gaya" → scared
"I can't sleep, mind keeps racing" → anxious
"Nothing feels real anymore. Just going through the motions." → numb
"Everyone expects so much and I'm running on empty." → overwhelmed
"What's even the point anymore. Nothing is going to change." → hopeless
"Ich bin müde und fühle mich allein" → sad, secondary: numb
"Ich weiß nicht mehr weiter" → hopeless
"thak gayi hoon, sab se thak gayi" → overwhelmed
"itna dard hai ki kuch feel hi nahi hota" → numb
"parents ka pressure, studies ka pressure, sab ek saath aa gaya" → overwhelmed
"usse baat ki toh roya — pata nahi kyun" → sad"""


async def detect(query: str) -> dict:
    """Returns {emotion, secondary, fallback_used}.

    Falls back to 'neutral' if the LLM call fails.
    """
    try:
        result = await chat_json(
            model=GROQ_MODEL_FAST,
            temperature=0.15,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": query},
            ],
        )
        data = result["data"]
        e = (data.get("emotion") or "neutral").lower().strip()
        sec = (data.get("secondary") or "").lower().strip() or None
        return {
            "emotion": e if e in VALID else "neutral",
            "secondary": sec if sec and sec in VALID else None,
            "fallback_used": False,
        }
    except Exception as err:
        log.warning("emotion detect failed — fallback to neutral", error=str(err))
        return {"emotion": "neutral", "secondary": None, "fallback_used": True}
