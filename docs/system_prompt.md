# Umang System Prompt Architecture

## Overview

Umang's system prompt is **assembled dynamically** from multiple modules at request time,
rather than stored as a single static string. This allows each component to be tested,
updated, and token-budgeted independently.

## Components (injected in order)

| Component | Source | ~Tokens | Purpose |
|-----------|--------|---------|---------|
| Persona | `server/ai/responder.py` → `PERSONA["Legal"]` | ~730 | Identity, 10 core behavioural rules |
| Language instruction | `server/ai/language_engine.py` → `build_language_instruction()` | ~80–120 | Language-specific response rules |
| Response format | `server/ai/response_template.py` → `RESPONSE_TEMPLATE_DESCRIPTION` | ~350 | Section headings and what goes in each |
| Few-shot examples | `server/ai/few_shot_examples.py` → `get_few_shot_examples()` | ~400–600 | 1–2 ideal examples for the category |
| Case analysis block | `server/ai/legal_agents.py` internal | ~80–120 | Structured output from Case Analyzer (Agent 1) |
| Reasoning context | `server/ai/legal_agents.py` → `build_reasoning_context()` | ~300–800 | Deterministic `_LEGAL_KNOWLEDGE` + chunked RAG |
| Retrieved knowledge | FAISS + BM25 hybrid via `server/rag/retriever.py` | ~800–1,200 | Top-k retrieved chunks with citation indices |
| Source prompt | `server/ai/responder.py` → `SOURCES_SECTION_PROMPT` | ~80 | Instructions for the `## Sources` section |

**Estimated total (typical Legal query): ~3,000–4,000 tokens** (well within Groq's 12,000 TPM limit).

## Budget Management

The previous monolithic `PERSONA["Legal"]` was ~19,000 characters (~4,800 tokens), which
combined with RAG and history exceeded Groq's 12,000 token/minute limit.

After the refactor:
- Persona: ~730 tokens (down from ~4,800)
- Format rules: ~350 tokens (was embedded in persona)
- Language instruction: ~80–120 tokens (was embedded in persona)
- Few-shot: ~400–600 tokens (new, replaces implicit examples in persona)
- Total persona-group: ~1,680–1,800 tokens

This leaves ~3,000+ tokens for RAG chunks and history at the 5,000 token ceiling.

## Adding or Modifying Components

- **Change response format**: edit `server/ai/response_template.py` → `RESPONSE_TEMPLATE_DESCRIPTION`
- **Change language behaviour**: edit `server/ai/language_engine.py` → `_LANG_INSTRUCTIONS`
- **Add/modify few-shot examples**: edit `server/ai/few_shot_examples.py` → `EXAMPLES`
- **Change core rules**: edit `server/ai/responder.py` → `PERSONA["Legal"]`
- **Change citation guardrails**: edit `server/ai/hallucination_guardrails.py` → `KNOWN_ACTS`
