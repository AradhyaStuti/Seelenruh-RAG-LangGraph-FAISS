"""Emotion classifier — 6-way categorical for tone adaptation."""
from ai.provider import chat_json
from config import GROQ_MODEL_FAST
from logger import get_logger

log = get_logger("emotion")

VALID = {"sad", "angry", "happy", "scared", "confused", "neutral"}
SYSTEM = """Detect the dominant emotion in a user message. The user may write in English, Hindi, or Hinglish.

Return ONLY valid JSON: {"emotion": "<value>"}
Values: "sad", "angry", "happy", "scared", "confused", "neutral"

Rules:
- Use "neutral" only when the message is a plain information request with no emotional signal.
- Prefer the more specific emotion over "neutral" when in doubt.

Examples:
"I feel so lost and empty" → sad
"I can't sleep, mind keeps racing" → sad
"This is so unfair I hate everything" → angry
"Finally got the scholarship!" → happy
"Someone is following me home" → scared
"I don't understand this form at all" → confused
"How do I file an RTI" → neutral
"mujhe bohot dard ho raha hai" → sad
"rone ka mann kar raha hai" → sad
"itna gussa aa raha hai boss pe" → angry
"koi maar raha hai mujhe" → scared
"bilkul samajh nahi aaya yeh process" → confused
"mujhe khushi ho rahi hai aaj" → happy
"ration card kaise banwate hain" → neutral
"mera account hack ho gaya" → scared
"thak gayi hoon sab se" → sad"""


async def detect(query: str) -> dict:
    """Returns {emotion, fallback_used}. `fallback_used` is True when the
    LLM call failed and the function returned the default "neutral"."""
    try:
        result = await chat_json(
            model=GROQ_MODEL_FAST,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": query},
            ],
        )
        e = (result["data"].get("emotion") or "neutral").lower()
        return {"emotion": e if e in VALID else "neutral", "fallback_used": False}
    except Exception as err:
        log.warning("fallback to neutral", error=str(err))
        return {"emotion": "neutral", "fallback_used": True}
