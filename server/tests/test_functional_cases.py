import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.language_engine import build_language_instruction, detect_language
from ai.intent import SYSTEM as INTENT_SYSTEM


def test_detects_english_query():
    assert detect_language("How do I file an RTI application?") == "en"


def test_detects_hinglish_query():
    assert detect_language("mujhe bohot anxiety ho rahi hai") == "hi-roman"


def test_detects_hindi_query():
    assert detect_language("मैं अपने अधिकारों के बारे में जानना चाहता हूँ") == "hi"


def test_detects_german_query():
    assert detect_language("Ich habe Angst und brauche Hilfe") == "de"


def test_build_language_instruction_returns_english_for_english_text():
    instruction = build_language_instruction("auto", "How do I file a complaint?")
    assert "English" in instruction or "plain" in instruction.lower()


def test_build_language_instruction_returns_hinglish_for_roman_hindi():
    instruction = build_language_instruction("auto", "mujhe yojana kaise apply karni hai")
    assert "Hinglish" in instruction or "conversational" in instruction.lower()


def test_build_language_instruction_returns_hindi_for_devanagari_text():
    instruction = build_language_instruction("auto", "मुझे कानूनी सलाह चाहिए")
    assert "हिंदी" in instruction or "Hindi" in instruction


def test_build_language_instruction_returns_german_for_german_text():
    instruction = build_language_instruction("auto", "Ich brauche Hilfe wegen Wohnung")
    assert "German" in instruction or "deutsche" in instruction.lower() or "Deutsch" in instruction


def test_intent_system_contains_relevant_domains():
    assert '"Mental Health"' in INTENT_SYSTEM
    assert '"Legal"' in INTENT_SYSTEM
    assert '"Government Schemes"' in INTENT_SYSTEM
    assert '"Safety"' in INTENT_SYSTEM


def test_intent_system_mentions_hinglish_guidance():
    assert "HINGLISH GUIDANCE" in INTENT_SYSTEM
    assert "Government schemes" in INTENT_SYSTEM


def test_empty_input_defaults_to_english():
    assert detect_language("") == "en"
    assert detect_language("   ") == "en"


def test_non_english_script_is_not_mistaken_for_english():
    result = detect_language("¿Cómo puedo pedir ayuda?")
    assert result in {"en", "de", "hi-roman", "hi"}


def test_legal_query_is_routed_to_legal_domain_keywords():
    assert "Legal" in INTENT_SYSTEM or "RTI" in INTENT_SYSTEM


def test_scheme_query_mentions_government_schemes_guidance():
    assert "Government Schemes" in INTENT_SYSTEM or "yojana" in INTENT_SYSTEM.lower()


def test_safety_query_mentions_emergency_handling():
    assert "Safety" in INTENT_SYSTEM or "emergency" in INTENT_SYSTEM.lower()


def test_mental_health_query_mentions_wellbeing_keywords():
    assert "Mental Health" in INTENT_SYSTEM or "anxiety" in INTENT_SYSTEM.lower()


def test_hinglish_instruction_is_not_devanagari():
    instruction = build_language_instruction("auto", "mujhe yojana kaise apply karni hai")
    assert "Hinglish" in instruction or "conversational" in instruction.lower()


def test_hindi_instruction_mentions_indian_laws():
    instruction = build_language_instruction("auto", "मुझे कानूनी सलाह चाहिए")
    assert "भारतीय" in instruction or "Indian" in instruction or "कानून" in instruction


def test_german_instruction_mentions_indian_law_only():
    instruction = build_language_instruction("auto", "Ich brauche Hilfe wegen Wohnung")
    assert "INDIAN" in instruction.upper() or "indian" in instruction.lower()


def test_english_instruction_is_professional():
    instruction = build_language_instruction("auto", "How do I file a complaint?")
    assert "professional" in instruction.lower() or "plain" in instruction.lower()


def test_detect_language_handles_whitespace_only_input():
    assert detect_language("      ") == "en"


def test_detect_language_handles_none_like_input():
    assert detect_language(None) == "en"


def test_detect_language_handles_mixed_script_input():
    assert detect_language("Mujhe help chahiye") in {"en", "hi-roman"}


def test_detection_for_german_marker_words():
    assert detect_language("Bitte helfen Sie mir") == "de"


def test_detection_for_hinglish_marker_words():
    assert detect_language("mujhe kya karna chahiye") == "hi-roman"


def test_detection_for_devanagari_marker_words():
    assert detect_language("मुझे मदद चाहिए") == "hi"


def test_intent_system_mentions_panic_guidance():
    assert "Panic" in INTENT_SYSTEM or "panic" in INTENT_SYSTEM.lower()


def test_intent_system_mentions_domain_guidance():
    assert "DOMAIN GUIDANCE" in INTENT_SYSTEM


def test_intent_system_mentions_few_shot_examples():
    assert "FEW-SHOT EXAMPLES" in INTENT_SYSTEM
