"""Groq SDK wrapper. Exposes chat, chat_json, transcribe — the
provider layer wraps these with auto-fallback."""
import base64
import io
import json
from typing import AsyncIterator

from groq import AsyncGroq, APIStatusError

from config import GROQ_API_KEY, GROQ_MODEL_FAST, GROQ_MODEL_WHISPER

_client: AsyncGroq | None = None


def _get() -> AsyncGroq:
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set")
        _client = AsyncGroq(api_key=GROQ_API_KEY)
    return _client


class GroqError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


async def chat(*, messages: list[dict], model: str | None = None, temperature: float = 0.7,
               max_tokens: int = 1024, json_mode: bool = False) -> str:
    try:
        resp = await _get().chat.completions.create(
            model=model or GROQ_MODEL_FAST,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"} if json_mode else None,
        )
        return (resp.choices[0].message.content or "").strip()
    except APIStatusError as err:
        raise GroqError(str(err), status=err.status_code) from err


async def chat_json(*, messages: list[dict], model: str | None = None, temperature: float = 0.2) -> dict:
    raw = await chat(messages=messages, model=model, temperature=temperature, json_mode=True)
    return json.loads(raw)


async def stream_chat(
    *,
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 900,
) -> AsyncIterator[str]:
    """Yield text tokens one by one as Groq streams them."""
    try:
        stream = await _get().chat.completions.create(
            model=model or GROQ_MODEL_FAST,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except APIStatusError as err:
        raise GroqError(str(err), status=err.status_code) from err


async def transcribe(audio_data_uri: str, lang: str = "auto") -> str:
    _, _, payload = audio_data_uri.partition(",")
    audio_bytes = base64.b64decode(payload or audio_data_uri)
    if not audio_bytes:
        raise ValueError("Empty audio payload")
    mime = "audio/wav"
    if audio_data_uri.startswith("data:") and ";" in audio_data_uri:
        mime = audio_data_uri.split(":", 1)[1].split(";", 1)[0]
    ext = mime.split("/")[-1].split(";")[0] or "wav"

    # Lock language for all known languages — without it, Whisper auto-detect often mishears
    # Hindi/Hinglish phonemes as English garbage (e.g. "mujhe acha ni lg rha" → "Milders" or
    # "Topics is a great way to get a job"). "auto" defaults to "hi" because this is an Indian
    # app — language="hi" handles both Devanagari and Hinglish correctly. German/English users
    # must select their language explicitly from the selector.
    _LANG_MAP = {"en": "en", "hi": "hi", "de": "de", "auto": "hi"}
    whisper_lang = _LANG_MAP.get(lang, "hi")

    _PROMPTS = {
        "en": "The user is speaking in English or Hinglish. Topics: mental health, legal, government schemes, safety.",
        "hi": "The user is speaking in Hindi or Hinglish (Roman-script Hindi like 'acha nahi lag raha'). Transcribe exactly as spoken. Topics: mental health, legal, government schemes, safety.",
        "de": "Der Benutzer spricht auf Deutsch. Themen: psychische Gesundheit, Recht, staatliche Programme, Sicherheit.",
        "auto": "The user may be speaking in English, Hindi, Hinglish (Roman-script Hindi like 'mujhe acha nahi lag raha'), or German. Transcribe exactly as spoken in the detected language. Topics: mental health, legal, government schemes, safety.",
    }
    prompt = _PROMPTS.get(lang, _PROMPTS["en"])

    file_tuple = (f"audio.{ext}", io.BytesIO(audio_bytes), mime)
    kwargs = dict(
        file=file_tuple,
        model=GROQ_MODEL_WHISPER,
        response_format="json",
        prompt=prompt,
        temperature=0,  # deterministic — dramatically reduces hallucinations on marginal audio
    )
    if whisper_lang:
        kwargs["language"] = whisper_lang

    resp = await _get().audio.transcriptions.create(**kwargs)
    return (resp.text or "").strip()
