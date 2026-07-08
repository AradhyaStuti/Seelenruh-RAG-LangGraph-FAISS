"""Speech-to-text via Groq Whisper."""
from ai import groq_client
from logger import get_logger

log = get_logger("stt")


async def transcribe(audio_data_uri: str, lang: str = "auto") -> dict:
    try:
        text = await groq_client.transcribe(audio_data_uri, lang=lang)
        if not text:
            return {"text": None, "error": "No speech detected"}
        return {"text": text}
    except Exception as err:
        log.error("transcription failed", error=str(err))
        msg = str(err).lower()
        if "invalid" in msg or "format" in msg or "decode" in msg:
            friendly = "Audio format not supported. Please try again."
        elif "timeout" in msg or "timed out" in msg:
            friendly = "Transcription timed out. Please speak again."
        elif "too large" in msg or "size" in msg:
            friendly = "Recording too long. Please keep it under 30 seconds."
        else:
            friendly = "Couldn't hear you clearly. Please try again."
        return {"text": None, "error": friendly}
