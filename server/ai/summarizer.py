"""Rolling conversation summary with best-effort PII redaction before sending to Groq."""
import re

from ai.provider import chat
from config import GROQ_MODEL_FAST
from logger import get_logger

log = get_logger("summarizer")


# Order matters — try the longer / more specific patterns first so an
# Aadhaar number doesn't get partially eaten by the phone-number regex.
_PII_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Emails
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[email]"),
    # Credit-card-shaped 13-19 digit runs, optionally space- or dash-grouped.
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[card]"),
    # Aadhaar — 12 digits, often spaced 4-4-4. Match before the phone regex.
    (re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b"), "[aadhaar]"),
    # Indian PAN — five letters, four digits, one letter.
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[pan]"),
    # Phone numbers: optional +91/+, optional separators, 10-12 digit total.
    # Deliberately conservative to avoid eating helpline numbers like 112 / 1930
    # (those are 3-4 digit, fall below the threshold).
    (re.compile(r"\+?\d{1,3}[ -]?\d{3,5}[ -]?\d{3,4}[ -]?\d{3,4}"), "[phone]"),
]


def _redact_pii(text: str) -> str:
    out = text
    for pat, repl in _PII_PATTERNS:
        out = pat.sub(repl, out)
    return out

SYSTEM = """You are an assistant that writes one short paragraph summarising a
chat between a user and a wellbeing / legal / scheme / safety assistant.

Rules:
- 2–4 sentences. ≤ 80 words.
- Start with: "Summary: ".
- Capture what the user discussed and any decisions / facts that matter for follow-up turns.
- No advice, no caveats, no quoting verbatim, no headers, no bullet points.
- Refer to the user as "the user" in third person."""


async def summarize(messages: list[dict]) -> str:
    if not messages:
        return ""
    transcript = "\n".join(
        f"{m.get('role','user').upper()}: {_redact_pii(m.get('content','').strip())}"
        for m in messages
    )
    try:
        result = await chat(
            model=GROQ_MODEL_FAST,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": transcript},
            ],
        )
        text = (result.get("content") or "").strip()
        if text and not text.lower().startswith("summary:"):
            text = "Summary: " + text
        return text
    except Exception as err:
        log.warning("summarization failed", error=str(err))
        return ""
