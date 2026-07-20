import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.language_engine import build_language_instruction, detect_language  # noqa: E402
from ai.intent import SYSTEM as INTENT_SYSTEM  # noqa: E402


# ── Language detection ────────────────────────────────────────────────────────

def test_detects_english_query():
    assert detect_language("How do I file an RTI application?") == "en"


def test_detects_hinglish_query():
    assert detect_language("mujhe bohot anxiety ho rahi hai") == "hi-roman"


def test_detects_hindi_query():
    assert detect_language("मैं अपने अधिकारों के बारे में जानना चाहता हूँ") == "hi"


def test_detects_german_query():
    assert detect_language("Ich habe Angst und brauche Hilfe") == "de"


def test_empty_and_whitespace_defaults_to_english():
    assert detect_language("") == "en"
    assert detect_language("   ") == "en"


def test_none_input_defaults_to_english():
    assert detect_language(None) == "en"


# ── Language instruction builder ──────────────────────────────────────────────

def test_instruction_english():
    inst = build_language_instruction("auto", "How do I file a complaint?")
    assert "English" in inst or "plain" in inst.lower()


def test_instruction_hinglish():
    inst = build_language_instruction("auto", "mujhe yojana kaise apply karni hai")
    assert "Hinglish" in inst or "conversational" in inst.lower()


def test_instruction_hindi():
    inst = build_language_instruction("auto", "मुझे कानूनी सलाह चाहिए")
    assert "हिंदी" in inst or "Hindi" in inst


def test_instruction_german():
    inst = build_language_instruction("auto", "Ich brauche Hilfe wegen Wohnung")
    assert "German" in inst or "Deutsch" in inst or "deutsche" in inst.lower()


# ── Intent system prompt ──────────────────────────────────────────────────────

def test_intent_system_contains_all_domains():
    assert '"Mental Health"' in INTENT_SYSTEM
    assert '"Legal"' in INTENT_SYSTEM
    assert '"Government Schemes"' in INTENT_SYSTEM
    assert '"Safety"' in INTENT_SYSTEM


def test_intent_system_has_hinglish_guidance():
    assert "HINGLISH GUIDANCE" in INTENT_SYSTEM


def test_intent_system_has_domain_guidance_section():
    assert "DOMAIN GUIDANCE" in INTENT_SYSTEM


def test_intent_system_has_few_shot_examples():
    assert "FEW-SHOT EXAMPLES" in INTENT_SYSTEM


def test_intent_system_has_legal_keywords():
    matched = [kw for kw in ["FIR", "RTI", "tenant", "contract", "Section"] if kw in INTENT_SYSTEM]
    assert len(matched) >= 2


# ── Multi-turn language stability ─────────────────────────────────────────────

def test_multiturn_english_stays_consistent():
    turns = ["I've been feeling very anxious lately", "Can you help me with breathing exercises?",
             "What are long-term coping strategies?"]
    assert all(detect_language(t) == "en" for t in turns)


def test_multiturn_hinglish_stays_consistent():
    turns = ["mujhe bahut anxiety ho rahi hai", "kya karna chahiye mujhe", "aur koi upay batao mujhe"]
    assert all(detect_language(t) == "hi-roman" for t in turns)


def test_multiturn_hindi_followups_stay_hindi():
    for q in ["और बताइए", "ठीक है, फिर क्या करूँ?", "समझ आया"]:
        assert detect_language(q) == "hi", f"Expected 'hi' for '{q}'"


def test_multiturn_german_stays_consistent():
    turns = ["Ich habe Angst und weiß nicht weiter",
             "Bitte helfen Sie mir, ich verstehe das nicht",
             "Was sind meine Rechte als Mieter in Deutschland"]
    assert all(detect_language(t) == "de" for t in turns)


# ── Session / history logic ───────────────────────────────────────────────────

def test_history_trimming_keeps_last_n_turns():
    all_msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i}"}
                for i in range(16)]
    trimmed = all_msgs[1:][-6:]
    assert len(trimmed) == 6
    assert trimmed[0]["content"] == "message 10"
    assert trimmed[-1]["content"] == "message 15"


def test_session_accumulates_turns_in_correct_order():
    msgs = []
    msgs.append({"role": "user",      "content": "My landlord won't return my deposit."})
    msgs.append({"role": "assistant", "content": "Under the Model Tenancy Act you can..."})
    msgs.append({"role": "user",      "content": "How do I send a legal notice?"})
    msgs.append({"role": "assistant", "content": "A legal notice under Section 106 TPA..."})
    assert len(msgs) == 4
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert "deposit" in msgs[0]["content"]
