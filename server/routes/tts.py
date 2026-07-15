"""TTS: ElevenLabs when configured, gTTS as fallback."""
import io
import asyncio
import re as _re

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth import current_user
from config import ELEVENLABS_KEY, ELEVENLABS_VOICE_ID
from logger import get_logger

log = get_logger("tts")

router = APIRouter(prefix="/api/tts", tags=["tts"])

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_TIMEOUT = 10.0


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    domain: str = Field(default="Mental Health")
    lang: str = Field(default="en")


# Per-persona voice tuning for ElevenLabs
# Usha: warm, slightly expressive, slightly slower
# Umang/Aarogya/Raksha: clear, composed, authoritative
_PERSONA_VOICE = {
    "Mental Health":      {"stability": 0.55, "similarity_boost": 0.78, "style": 0.42, "speed": 0.92},
    "Legal":              {"stability": 0.72, "similarity_boost": 0.70, "style": 0.18, "speed": 1.0},
    "Government Schemes": {"stability": 0.62, "similarity_boost": 0.80, "style": 0.28, "speed": 0.94},
    "Safety":             {"stability": 0.80, "similarity_boost": 0.75, "style": 0.10, "speed": 1.05},
}

# gTTS language codes — German needs "de", Hindi "hi", English "en"
_GTTS_LANG = {"en": "en", "hi": "hi", "de": "de", "auto": "en"}


def _clean(text: str, lang: str = "en") -> str:
    """Strip markdown and normalize text for natural TTS output."""
    t = text
    # Remove markdown formatting
    t = _re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', t)   # bold/italic
    t = _re.sub(r'#{1,6}\s*', '', t)                    # headings
    t = _re.sub(r'`{1,3}[^`]*`{1,3}', '', t)            # code
    t = _re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)     # links → label only
    t = _re.sub(r'^\s*[-*>]\s+', '', t, flags=_re.M)    # list markers
    t = _re.sub(r'\n{2,}', '. ', t)                     # paragraph breaks → pause
    t = _re.sub(r'\n', ' ', t)

    if lang == "hi":
        # Normalize Hindi-specific punctuation
        t = t.replace('।', '.')        # Hindi danda → period (better TTS pause)
        t = t.replace('॥', '.')        # Double danda
        # Expand common abbreviations spoken in Hindi context
        t = _re.sub(r'\bRS\.?\s*(\d)', r'rupaye \1', t, flags=_re.I)
        t = _re.sub(r'\bINR\b', 'rupaye', t, flags=_re.I)
        t = _re.sub(r'(\d+)%', r'\1 pratishat', t)
        # Remove URLs entirely — don't read them
        t = _re.sub(r'https?://\S+', '', t)
    else:
        t = _re.sub(r'https?://\S+', '', t)

    # Collapse whitespace
    t = _re.sub(r'\s{2,}', ' ', t)
    return t[:800].strip()


async def _elevenlabs(text: str, lang: str = "en", domain: str = "Mental Health") -> bytes:
    """Call ElevenLabs v1 text-to-speech and return raw MP3 bytes."""
    cfg = _PERSONA_VOICE.get(domain, _PERSONA_VOICE["Mental Health"])
    # Hindi needs slightly more stability for clear Devanagari pronunciation
    stability = max(cfg["stability"], 0.62) if lang == "hi" else cfg["stability"]
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": stability,
            "similarity_boost": cfg["similarity_boost"],
            "style": cfg["style"],
            "use_speaker_boost": True,
        },
    }
    async with httpx.AsyncClient(timeout=ELEVENLABS_TIMEOUT) as client:
        r = await client.post(
            f"{ELEVENLABS_TTS_URL}/{ELEVENLABS_VOICE_ID}",
            json=payload,
            headers={
                "xi-api-key": ELEVENLABS_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
        )
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs returned {r.status_code}: {r.text[:200]}")
    return r.content


def _gtts_sync(text: str, lang: str) -> bytes:
    """gTTS is synchronous — call inside asyncio.to_thread."""
    from gtts import gTTS
    # slow=False always — slow mode sounds unnatural; gTTS pacing is acceptable at normal speed
    tts = gTTS(text=text, lang=lang, slow=False)
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    return buf.read()


def _detect_lang(text: str, requested_lang: str) -> str:
    """Use requested lang if set; fall back to detecting Devanagari in text."""
    if requested_lang and requested_lang != "auto":
        return requested_lang
    # Auto-detect: if text contains Devanagari script → Hindi
    if any('\u0900' <= ch <= '\u097F' for ch in text):
        return "hi"
    return "en"


@router.post("")
async def synthesize(req: TTSRequest, _user: dict = Depends(current_user)):
    lang = _detect_lang(req.text, req.lang)
    clean = _clean(req.text, lang)
    if not clean:
        raise HTTPException(status_code=400, detail="Empty text")

    # ── ElevenLabs path (neural, multilingual) ───────────────────────────────
    if ELEVENLABS_KEY:
        try:
            audio_bytes = await _elevenlabs(clean, lang, req.domain)
            return Response(
                content=audio_bytes,
                media_type="audio/mpeg",
                headers={"Cache-Control": "no-store"},
            )
        except Exception as e:
            log.warning("ElevenLabs failed, falling back to gTTS", error=str(e))

    # ── gTTS fallback (Google TTS — free, decent quality for Hindi) ──────────
    try:
        from gtts import gTTS  # noqa: F401 (import check)
    except ImportError:
        raise HTTPException(status_code=503, detail="TTS not available")

    gtts_lang = _GTTS_LANG.get(lang, "en")
    try:
        audio_bytes = await asyncio.to_thread(_gtts_sync, clean, gtts_lang)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")
