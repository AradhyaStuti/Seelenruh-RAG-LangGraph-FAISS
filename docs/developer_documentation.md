# Developer Documentation

## Architecture Overview

Secure-Soul AI uses a **multi-agent LangGraph pipeline** for the Legal domain (Umang),
with a simpler single-pass pipeline for other domains (Mental Health, Safety, Government Schemes).

```
User request
    │
    ▼
graph.py                    ← Domain router (classifies request)
    │
    ├── "Legal"     → legal_graph.py    ← 3-node LangGraph pipeline
    ├── "Mental Health" → responder.py  ← Direct LLM call
    ├── "Safety"    → responder.py
    └── "Government Schemes" → aarogya_graph.py
```

## Legal Pipeline (Umang)

### Entry point
`server/legal_graph.py` → `run()` (non-streaming) or `stream_run()` (streaming)

### Graph nodes

| Node | Agent | Model | Purpose |
|------|-------|-------|---------|
| `_analyze` | Agent 1 | llama-3.1-8b-instant (fast) | Classify query, extract category/issue_type/urgency/follow_up |
| `_prepare` | Agents 2–6 | Python only | Organize RAG chunks, build reasoning context, detect jurisdiction, load template |
| `_compose` | Agent 7 | llama-3.3-70b-versatile (smart) | Synthesize final response |

### Post-response quality gates (in `_compose`)

1. **Quality checker** (`server/ai/quality_checker.py`) — pattern-based checks:
   - Overpromise language → appends disclaimer
   - German law bleed-in → flags error
   - FIR misuse for salary disputes → warning (logged)
   - Fabricated helpline numbers → flags error

2. **Hallucination guardrails** (`server/ai/hallucination_guardrails.py`) — citation validation:
   - Checks section numbers against `KNOWN_ACTS` whitelist
   - Section > max valid range → appends verification note

### State schema (`LegalState`)

```python
class LegalState(TypedDict):
    query: str
    history: list[dict]
    retrieved: list[dict]
    emotion: str
    lang: str
    outer_context: str
    confidence: str
    fast_mode: bool
    case_analysis: dict      # set by _analyze
    organized_chunks: dict   # set by _prepare
    jurisdiction: str | None # set by _prepare
    reasoning_context: str   # set by _prepare
    doc_template: str | None # set by _prepare
    response: str            # set by _compose
    via: str                 # set by _compose
```

## New Modules (Architecture Refactor)

| Module | Location | Purpose |
|--------|----------|---------|
| `hallucination_guardrails.py` | `server/ai/` | Validate citation section numbers against KNOWN_ACTS whitelist |
| `language_engine.py` | `server/ai/` | Detect language (en/hi/hi-roman/de) and build language instruction |
| `quality_checker.py` | `server/ai/` | Pattern-based post-response validation (overpromise, FIR misuse, etc.) |
| `few_shot_examples.py` | `server/ai/` | 10 curated Q&A examples for system prompt injection |
| `response_template.py` | `server/ai/` | Response section definitions and RESPONSE_TEMPLATE_DESCRIPTION |

## Provider Fallback Chain

All LLM calls use the same fallback chain:
1. **Groq** (primary) — `llama-3.3-70b-versatile` / `llama-3.1-8b-instant`
2. **Ollama** (local fallback) — checked via `_ollama_up()`
3. **Anthropic** (cloud fallback) — if `ANTHROPIC_API_KEY` set
4. **Non-streaming fallback** — for streaming failures only

Circuit breakers (`server/ai/circuit_breaker.py`) prevent cascade failures.

## Environment Variables

```bash
GROQ_API_KEY=...            # Required for Groq
ANTHROPIC_API_KEY=...       # Optional — Anthropic fallback
OLLAMA_HOST=...             # Optional — local Ollama fallback
JWT_SECRET=...              # Auth token signing
```

## Testing

```bash
cd server
python -m pytest tests/test_legal_cases.py -v
```

91 test cases covering:
- All major legal categories
- Multi-language queries (English, Hinglish, German)
- Emergency detection
- FIR guard (salary disputes)
- POSH classification
- Confidence scoring

## Adding Legal Knowledge

**Static knowledge** (always reliable):
Edit `server/ai/legal_agents.py` → `_LEGAL_KNOWLEDGE["YourCategory"]`

**Dynamic RAG chunks**:
POST to `/api/ingest` or add to `server/rag/knowledge/` and rebuild the index.

## Token Budget

Target: < 5,000 tokens per Legal request (Groq limit: 12,000 TPM)

| Component | Target |
|-----------|--------|
| `PERSONA["Legal"]` | ~730 tokens |
| Language instruction | ~100 tokens |
| Response format | ~350 tokens |
| Few-shot examples (1) | ~400–600 tokens |
| Case analysis block | ~100 tokens |
| Reasoning context | ~400 tokens |
| RAG chunks (5×~200) | ~1,000 tokens |
| History (trimmed) | ~300 tokens |
| **Total** | **~3,480–3,680 tokens** |
