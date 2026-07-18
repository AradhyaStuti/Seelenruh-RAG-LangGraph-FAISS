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
# Expanded to catch casual, emotional, and crisis-adjacent vocabulary
_HINGLISH_MARKERS = re.compile(
    r"\b(mujhe|mera|meri|mere|hamara|hamari|aap|aapka|tumhara|kya|kyun|"
    r"kaise|kab|kahan|nahi|nhi|nahi|nahin|haan|hoon|hai|hain|tha|thi|the|"
    r"kar|karo|karein|chahiye|chahta|chahti|chahte|"
    # Asking / explaining
    r"bata|batao|bataye|dena|lena|dijiye|dijie|"
    # Emotional / wellbeing
    r"thakan|thakaan|thaka|pareshan|dukhi|udaas|rona|roya|ro|"
    r"darr|darra|dar|akela|akeli|dost|pyaar|nafrat|gussa|tension|"
    r"stress|anxious|depressed|ghabrana|ghabrahat|"
    # Urgency / immediacy
    r"abhi|abhi abhi|jaldi|turant|aaj|kal|parso|"
    r"bahut|bohot|bohat|bilkul|"
    # Money / work
    r"paisa|paise|rupay|rupaye|rupee|lakhs|crore|"
    r"naukri|salary|boss|company|kaam|karna|kaam dhanda|"
    # Housing / property
    r"ghar|makan|zameen|jagah|kiraya|rent|malik|landlord|"
    # Legal / safety
    r"police|court|vakeel|wakeel|judge|case|FIR|notice|kanoon|qanoon|"
    r"darj|complaint|shikayat|"
    # Conversation fillers / pronouns
    r"matlab|samajh|samajhna|bol|bolo|suno|dekho|"
    r"yaar|bhai|didi|sis|bro|sir|madam|ji|bhai sahab|"
    # Agreement / certainty
    r"theek|thik|theek hai|haan ji|zaroor|zaruri|"
    # Problem framing
    r"problem|issue|dikkat|mushkil|pareshani|"
    # Question words (Hinglish style)
    r"kya hua|kya hai|kaisa|kaisi|kaiku|kyunki|isliye|toh|toh phir|"
    # Actions / requests
    r"chahiye kya|help karo|batao na|suno na|dekho na)\b",
    re.IGNORECASE,
)

_HINGLISH_THRESHOLD = 2
_GERMAN_THRESHOLD = 2  # Require ≥2 keyword hits — single common words like "und"/"ist" appear in transliterated text


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
        "Explain legal and bureaucratic terms briefly when first used — never assume the user knows them. "
        "Use simple, direct sentences. Avoid jargon, Latin maxims, and hedging language like 'it is worth noting'. "
        "When giving practical steps, number them clearly. "
        "All laws and schemes referenced must be Indian."
    ),
    "hi": (
        "उत्तर स्वाभाविक, आधुनिक हिंदी में दें — वैसी हिंदी जो आज बोली जाती है। "
        "कानूनी और सरकारी शब्द जैसे 'FIR', 'RTI', 'Labour Commissioner', 'Consumer Forum', "
        "'Aadhaar', 'BPL', 'OBC', 'Section' को अंग्रेज़ी में ही रखें — इनका हिंदी अनुवाद न करें। "
        "संस्कृतनिष्ठ, पुरातन, या अखबारी हिंदी से बचें। "
        "वाक्य छोटे और स्पष्ट रखें। "
        "सभी कानून और योजनाएँ भारतीय हैं — किसी विदेशी कानून का उल्लेख न करें। "
        "helplines हमेशा हिंदी में दें: जैसे 'आप 112 पर कॉल कर सकते हैं'।"
    ),
    "hi-roman": (
        "Respond in conversational Hinglish — Roman-script Hindi naturally mixed with English. "
        "Write the way a helpful, educated friend would speak, not like a textbook or government notice. "
        "Keep technical terms in English: 'FIR', 'Section', 'RTI', 'Labour Commissioner', 'Consumer Forum', "
        "'Aadhaar', 'BPL', 'OBC', 'helpline', 'portal'. "
        "Short, punchy sentences. Numbers and amounts in digits (₹5,000, not 'paanch hazaar rupaye'). "
        "Example tone: 'Aapko pehle Labour Commissioner ke paas jaana chahiye — court baad mein. "
        "Complaint free hoti hai aur fast bhi.' "
        "Do NOT switch to Devanagari script mid-response. Do NOT use archaic Urdu-heavy Hindi. "
        "All laws and schemes referenced must be Indian."
    ),
    "de": (
        "CRITICAL — LANGUAGE AND JURISDICTION RULES FOR GERMAN SPEAKERS:\n"
        "1. Respond in clear, simple German (B2 level — everyday German, not legal or bureaucratic German).\n"
        "2. ALL laws and schemes cited must be INDIAN laws and Indian government schemes. "
        "NEVER cite German, Austrian, Swiss, or EU law.\n"
        "3. Translate Indian legal terms into German explanations where helpful:\n"
        "   - FIR → 'Strafanzeige bei der indischen Polizei (First Information Report)'\n"
        "   - Labour Commissioner → 'Indischer Arbeitskommissar'\n"
        "   - Consumer Forum → 'Indisches Verbraucherschiedsgericht'\n"
        "   - NALSA → 'Indiens kostenloser Rechtshilfedienst (NALSA, Tel: 15100)'\n"
        "   - RTI → 'Informationsfreiheitsantrag nach indischem Recht'\n"
        "4. If user seems unaware they are in India's legal system, clarify gently once: "
        "'Ich beantworte Ihre Frage nach INDISCHEM Recht — nicht nach deutschem oder EU-Recht.'\n"
        "5. Keep section numbers in original form: 'Section 138 des Negotiable Instruments Act'.\n"
        "6. Helplines: always give the Indian number with context — "
        "'Unter 112 erreichen Sie den indischen Notruf (Polizei, Feuerwehr, Krankenwagen)'.\n"
        "7. Use 'Sie' (formal) unless the user has clearly used 'du' first."
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
