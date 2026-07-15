"""Language detection and per-language instruction strings.

Detects en / hi (Devanagari) / hi-roman (Hinglish) / de from the message text.
No extra LLM call — just regex heuristics.
"""

from __future__ import annotations

import re

# Devanagari unicode range U+0900–U+097F
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")

# German marker words that rarely appear in English/Hindi queries
_GERMAN_MARKERS = re.compile(
    r"\b(ich|bitte|habe|mein|meine|mich|mir|aber|oder|und|nicht|ist|sind|"
    r"wurde|wurde|können|müssen|wohnung|vermieter|miete|polizei|zeuge|"
    r"anwalt|gericht|klage|recht|gesetz|vertrag|arbeitgeber|kündigung|"
    r"deutschland|österreich|schweiz|german|deutsch)\b",
    re.IGNORECASE,
)

_GERMAN_CHARS = re.compile(r"[äöüßÄÖÜ]")

# Hinglish markers — Roman-script Hindi words
_HINGLISH_MARKERS = re.compile(
    r"\b(mujhe|mera|meri|mere|hamara|hamari|aap|aapka|tumhara|kya|kyun|"
    r"kaise|kab|kahan|nahi|nhi|haan|hoon|hai|hain|tha|thi|the|kar|karo|"
    r"karein|chahiye|chahta|chahti|please|bata|batao|bataye|dena|lena|"
    r"paisa|paise|rupay|rupaye|lakhs|crore|ghar|makan|zameen|jagah|"
    r"police|court|vakeel|wakeel|judge|case|FIR|notice|kanoon|qanoon|"
    r"malik|landlord|kiraya|rent|naukri|salary|boss|company|kaam|karna|"
    r"matlab|samajh|samajhna|bol|bolo|suno|dekho|yaar|bhai|didi|sir|"
    r"madam|ji|haan ji|theek|thik|bilkul|zaroor|zaruri|problem|issue)\b",
    re.IGNORECASE,
)

_HINGLISH_THRESHOLD = 2
_GERMAN_THRESHOLD = 1


def detect_language(text: str) -> str:
    """Returns "en", "hi", "hi-roman", or "de" based on script/keyword heuristics."""
    if not text or not text.strip():
        return "en"

    if _DEVANAGARI.search(text):
        return "hi"

    if _GERMAN_CHARS.search(text):
        return "de"
    if len(_GERMAN_MARKERS.findall(text)) >= _GERMAN_THRESHOLD:
        return "de"

    hinglish_hits = len(_HINGLISH_MARKERS.findall(text))
    if hinglish_hits >= _HINGLISH_THRESHOLD:
        return "hi-roman"

    return "en"


_LANG_INSTRUCTIONS: dict[str, str] = {
    "en": (
        "Respond in plain, professional English. "
        "Explain legal terms briefly when first used. "
        "Use simple sentences; avoid Latin maxims unless essential."
    ),
    "hi": (
        "उत्तर स्वाभाविक आधुनिक हिंदी में दें। "
        "कानूनी शब्द जैसे 'FIR', 'Labour Commissioner', 'Consumer Forum' को English में ही रखें — "
        "इनका हिंदी अनुवाद न करें। "
        "संस्कृतनिष्ठ या पुरातन हिंदी से बचें। "
        "सभी कानून भारतीय हैं — किसी विदेशी कानून का उल्लेख न करें।"
    ),
    "hi-roman": (
        "Respond in conversational Hinglish (Roman-script Hindi mixed with English). "
        "Write the way a helpful educated friend would speak — natural, not textbook. "
        "Keep legal terms like 'FIR', 'Section', 'Labour Commissioner', 'Consumer Forum' in English. "
        "Example tone: 'Aapko pehle Labour Commissioner ke paas jaana chahiye, court baad mein.' "
        "Do NOT switch to Devanagari script. Do NOT use archaic Hindi. "
        "All laws referenced must be Indian laws."
    ),
    "de": (
        "CRITICAL — LANGUAGE AND JURISDICTION RULES FOR GERMAN SPEAKERS:\n"
        "1. Respond in clear, simple German (B2 level — not legal German).\n"
        "2. ALL laws cited must be INDIAN laws. NEVER cite German, Austrian, or EU law.\n"
        "3. Translate Indian legal terms into German context where helpful:\n"
        "   - FIR → 'Strafanzeige bei der indischen Polizei'\n"
        "   - Labour Commissioner → 'Indischer Arbeitskommissar'\n"
        "   - Consumer Forum → 'Indisches Verbraucherforum'\n"
        "   - NALSA → 'Indiens kostenloser Rechtshilfedienst (NALSA)'\n"
        "4. If user seems unaware they are in India's legal system, gently clarify: "
        "'Ich beantworte Ihre Frage nach INDISCHEM Recht.'\n"
        "5. Keep section numbers in the original form (e.g., 'Section 138 Negotiable Instruments Act')."
    ),
}

def build_language_instruction(lang_code: str, user_text: str = "") -> str:
    """Return the instruction string for the given language code. Detects from user_text when lang_code is 'auto'."""
    code = lang_code.strip().lower() if lang_code else "auto"

    if code in ("auto", ""):
        detected = detect_language(user_text)
        return _LANG_INSTRUCTIONS.get(detected, _LANG_INSTRUCTIONS["en"])

    # Legacy "hi" key — check if actually Hinglish
    if code == "hi" and user_text and not _DEVANAGARI.search(user_text):
        hinglish_hits = len(_HINGLISH_MARKERS.findall(user_text))
        if hinglish_hits >= _HINGLISH_THRESHOLD:
            return _LANG_INSTRUCTIONS["hi-roman"]

    return _LANG_INSTRUCTIONS.get(code, _LANG_INSTRUCTIONS["en"])
