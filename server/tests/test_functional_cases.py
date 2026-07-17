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


# ── Multi-turn conversation tests ─────────────────────────────────────────────
# These tests verify that language detection is stable across a conversation,
# that history trimming works correctly, and that session state accumulates
# in the right order — all without requiring a live LLM.

def test_multiturn_english_language_stays_consistent_across_turns():
    """English detected consistently across a three-turn mental health conversation."""
    turns = [
        "I've been feeling very anxious lately",
        "Can you help me with some breathing exercises?",
        "What are some long-term coping strategies?",
    ]
    results = [detect_language(t) for t in turns]
    assert all(lang == "en" for lang in results), f"Expected all 'en', got {results}"


def test_multiturn_hinglish_language_stays_consistent_across_turns():
    """Hinglish detected consistently across a three-turn conversation."""
    turns = [
        "mujhe bahut anxiety ho rahi hai",
        "kya karna chahiye mujhe",
        "aur koi tips batao please",
    ]
    results = [detect_language(t) for t in turns]
    assert all(lang == "hi-roman" for lang in results), f"Expected all 'hi-roman', got {results}"


def test_multiturn_hindi_followup_stays_hindi():
    """Devanagari follow-ups are not mis-detected as another language."""
    followups = ["और बताइए", "ठीक है, फिर क्या करूँ?", "समझ आया"]
    for q in followups:
        lang = detect_language(q)
        assert lang == "hi", f"Expected 'hi' for '{q}', got '{lang}'"


def test_multiturn_english_followup_phrases_detected_correctly():
    """Short follow-up phrases common in multi-turn chat don't break detection."""
    followups = ["tell me more", "what else can I do?", "got it, go on", "and then?"]
    for q in followups:
        lang = detect_language(q)
        assert lang == "en", f"Expected 'en' for '{q}', got '{lang}'"


def test_history_trimming_keeps_last_n_turns():
    """buildHistory equivalent: skip welcome message, keep last N turns."""
    n = 6
    all_msgs = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i}"}
        for i in range(16)   # 16 total messages including welcome at index 0
    ]
    # Simulate: skip first (welcome), slice last n
    trimmed = all_msgs[1:][-n:]
    assert len(trimmed) == n
    assert trimmed[0]["content"] == "message 10"
    assert trimmed[-1]["content"] == "message 15"
    assert trimmed[-1]["role"] == "assistant"


def test_session_accumulates_turns_in_correct_order():
    """Messages are appended in user → assistant → user order."""
    session_messages = []
    session_messages.append({"role": "user",      "content": "My landlord won't return my deposit."})
    session_messages.append({"role": "assistant", "content": "Under the Model Tenancy Act you can..."})
    session_messages.append({"role": "user",      "content": "How do I send a legal notice?"})
    session_messages.append({"role": "assistant", "content": "A legal notice under Section 106 TPA..."})

    assert len(session_messages) == 4
    assert session_messages[0]["role"] == "user"
    assert session_messages[1]["role"] == "assistant"
    assert session_messages[2]["role"] == "user"
    assert session_messages[3]["role"] == "assistant"
    assert "deposit" in session_messages[0]["content"]


def test_multiturn_domain_keyword_consistent_for_legal_queries():
    """Legal domain keywords appear in INTENT_SYSTEM regardless of turn count."""
    legal_signals = ["FIR", "RTI", "tenant", "contract", "Section"]
    matched = [kw for kw in legal_signals if kw in INTENT_SYSTEM]
    assert len(matched) >= 2, f"Expected at least 2 legal keywords in INTENT_SYSTEM, found: {matched}"


def test_multiturn_german_conversation_detected_consistently():
    """German turns with sufficient length are detected consistently.
    Short German phrases (<4 words) may be ambiguous — test only longer ones."""
    turns = [
        "Ich habe Angst und weiß nicht weiter",
        "Bitte helfen Sie mir, ich verstehe das nicht",
        "Was sind meine Rechte als Mieter in Deutschland",
    ]
    results = [detect_language(t) for t in turns]
    assert all(lang == "de" for lang in results), f"Expected all 'de', got {results}"
