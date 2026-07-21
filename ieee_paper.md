# Seelenruh: A Multilingual Agentic RAG System for Mental Health, Legal, and Social Welfare Assistance in India

**Aradhya Stuti**  
Department of Computer Science and Engineering  
B.Tech Final Year Project, 2026

---

## Abstract

Seelenruh is an agentic conversational AI system designed to provide Indian users with accessible, accurate, and empathetic assistance across four high-need domains: mental health support, legal guidance, government scheme navigation, and emergency safety response. The system combines a LangGraph-orchestrated multi-agent pipeline with hybrid retrieval-augmented generation (RAG), real-time web search fallback, and persona-specific response composition. A seven-node agentic graph — load\_memory → classify → route → retrieve → maybe\_search → generate → save\_memory — processes each request with parallel intent classification, 11-state emotion detection, and goal tracking. Retrieval uses a dual-pass FAISS vector search fused with BM25 via reciprocal rank fusion (RRF), followed by cross-encoder reranking (ms-marco-MiniLM-L-6-v2), achieving P@1 = 84.0% and MRR = 0.896 on a 100-query frozen evaluation set across four languages. Routing accuracy is 95% (CI: 91–99%) on the same set. Domain-specific hallucination guardrails reduce fabricated citations to 0 out of 14 adversarial probes. The system is deployed as a Docker container on Hugging Face Spaces with a React 18 progressive web app frontend.

**Keywords** — retrieval-augmented generation, LangGraph, agentic AI, multilingual NLP, mental health AI, legal AI, FAISS, BM25, India

---

## I. Introduction

Access to timely and accurate information in mental health, law, and social welfare remains deeply unequal in India. An estimated 150 million people require mental health interventions but fewer than 10% receive any care [1]. Legal aid is inaccessible to most citizens due to cost and complexity. Government scheme uptake is low because eligibility criteria are scattered across dozens of portals in formal English.

Large language models (LLMs) offer a promising path to democratizing such access, but their tendency to hallucinate authoritative-sounding but incorrect information makes them unsafe to deploy without grounding mechanisms. Retrieval-augmented generation (RAG) partially addresses this by conditioning responses on retrieved evidence, but standard single-pass RAG fails for multilingual queries and for domains requiring structured, deterministic outputs (e.g., crisis detection, legal citations).

This paper presents **Seelenruh** (German: *peace of mind*), a production-deployed agentic RAG system that addresses these gaps through:

1. A LangGraph-orchestrated seven-node agentic pipeline with parallel classification nodes.
2. Hybrid dual-pass retrieval (FAISS + BM25 + RRF + cross-encoder) with bilingual Hindi support.
3. Four domain-specific personas (Usha, Umang, Aarogya, Raksha) with tailored knowledge bases and deterministic safety overrides.
4. A 6-hour automated knowledge updater crawling 14 government sources.
5. Hallucination guardrails with section-number range checking and foreign law detection.

The system serves English, Hindi (Devanagari), Hinglish (Roman script), and German queries with a single unified retrieval backend.

---

## II. Related Work

### A. Retrieval-Augmented Generation

Lewis et al. [2] introduced RAG as a method of grounding LLM outputs in retrieved passages, substantially reducing hallucination on knowledge-intensive tasks. Subsequent work (RAG-Fusion [3], HyDE [4]) improved retrieval quality through query reformulation. This work adopts a simpler but effective dual-pass strategy: one FAISS pass on the original query and one on English-only tokens extracted from Hinglish, fused by RRF [5].

### B. Agentic Pipelines

LangGraph [6] extends LangChain with a directed graph abstraction for stateful multi-step agent workflows. Unlike single-chain RAG, agentic pipelines can branch conditionally (e.g., only trigger web search when RAG confidence is low) and run multiple nodes in parallel. This work exploits LangGraph's parallel edge support to run intent classification, emotion detection, and goal detection concurrently, reducing classify-stage latency by approximately 60% versus serial execution.

### C. Mental Health NLP

Prior systems for mental health NLP (e.g., Woebot [7], Koko [8]) operate as rule-based chatbots or fine-tuned classifiers. More recent LLM-based systems raise safety concerns around crisis handling. This work deliberately separates crisis detection (hard-coded regex across 35+ phrases in four languages, sub-millisecond) from LLM generation, ensuring safety routing never depends on probabilistic model outputs.

### D. Legal AI in India

Legal-domain LLMs face acute hallucination risk because section numbers and statute names are easily confabulated. IPC Section 600 does not exist, yet standard LLMs cite it with confidence. CaseSummarizer [9] and similar systems use fine-tuning; this work instead uses retrieval grounding plus pattern-based post-generation checks that flag section numbers outside known statutory ranges.

### E. Government Scheme Navigation

Scheme eligibility systems in India are typically static web portals with no natural-language interface. This work implements a composable eligibility predicate engine (Python, no LLM) that evaluates income thresholds, age ranges, farmer/student flags, and state restrictions against user-provided parameters, returning matched schemes in under 50 ms without an LLM call.

---

## III. System Architecture

### A. Overview

The system follows a client–server architecture. The frontend (React 18, Vite, Tailwind CSS) communicates with the backend (FastAPI, Python 3.10+) over HTTP and SSE. The backend hosts the LangGraph pipeline, retrieval modules, web search cascade, and MongoDB integration.

```
┌─────────────────────────────────────┐
│           React Frontend            │
│  (Chat UI, Session History, Mood,   │
│   Breathing, PWA, Admin Dashboard)  │
└────────────────┬────────────────────┘
                 │ HTTP / SSE
┌────────────────▼────────────────────┐
│         FastAPI Backend             │
│  ┌──────────────────────────────┐   │
│  │     LangGraph Agentic Graph  │   │
│  │  load_memory → classify →    │   │
│  │  route → retrieve →          │   │
│  │  maybe_search → generate →   │   │
│  │  save_memory                 │   │
│  └──────────────────────────────┘   │
│  ┌──────────┐  ┌────────────────┐   │
│  │  FAISS   │  │  MongoDB Atlas │   │
│  │  BM25    │  │  (sessions,    │   │
│  │  Reranker│  │   memory, gaps)│   │
│  └──────────┘  └────────────────┘   │
└─────────────────────────────────────┘
```

### B. LangGraph Agentic Pipeline

Each user message traverses a seven-node directed graph:

**load\_memory**: Retrieves rolling session summary (last 8 sessions), emotion arc (last 10 turns), and cross-session user memory from MongoDB. Adds to graph state.

**classify**: Three parallel LLM calls using Groq llama-3.1-8b-instant (~150 ms each):
- *Intent classifier*: routes to one of four domains (Mental Health, Legal, Government Schemes, Safety).
- *Emotion detector*: classifies into 11 states (sad, angry, happy, scared, confused, neutral, hopeless, overwhelmed, anxious, frustrated, numb) plus a secondary emotion field.
- *Goal tracker*: extracts the user's current goal (e.g., "file RTI") and checks if it persists from prior turns.

**route**: Selects the domain sub-graph based on intent classifier output. Injects domain-specific system prompt and persona voice.

**retrieve**: Executes the hybrid retrieval pipeline (Section III.C).

**maybe\_search**: Triggered when RAG confidence is Low or None, or when retrieval hits fall below a threshold. Cascades through Brave Search → Tavily → DuckDuckGo → SerpAPI → Wikipedia.

**generate**: Dispatches to domain sub-graph (analyze → prepare → compose). compose uses Groq llama-3.3-70b-versatile for final response generation.

**save\_memory**: Updates session summary and emotion arc in MongoDB asynchronously, never blocking the main response path.

### C. Hybrid Retrieval Pipeline

```
Query
  │
  ├── Embed (multilingual-e5-small, 32 ms p50)
  │     ├── FAISS ANN search (1 ms p50)
  │     └── [Hindi/Hinglish] second FAISS pass on English tokens
  │
  ├── BM25 keyword search
  │
  ├── Reciprocal Rank Fusion (RRF, k=60)
  │
  └── Cross-encoder reranker (ms-marco-MiniLM-L-6-v2)
        └── Top-k chunks → composer
```

For Hindi and Hinglish queries, a token-level transliteration map converts common Hinglish words to English (e.g., "pareshan" → "troubled anxious disturbed stressed"). A second FAISS pass on the English-only tokens runs in parallel with the main pass; both result lists are RRF-fused before reranking.

**Query rewriting**: Short queries (< 8 tokens) are expanded by the 8B model before embedding. Results are cached by query hash to avoid duplicate LLM calls.

### D. Domain Sub-graphs

Each of the four domains runs a three-node sub-graph:

| Node | Model | Role |
|---|---|---|
| analyze | llama-3.1-8b-instant | Classify emotional/legal/scheme/safety context |
| prepare | Python (no LLM) | Organise chunks, run deterministic checks |
| compose | llama-3.3-70b-versatile | Generate final persona response |

The prepare node runs domain-specific deterministic logic:
- **Usha**: crisis phrase matching (35+ phrases, four languages), emotion arc trend detection.
- **Umang**: section number range validation, foreign law detection, 9-section response template enforcement.
- **Aarogya**: composable eligibility predicate evaluation, dynamic scheme override merge.
- **Raksha**: threat-type lookup against deterministic safety plan dict, POCSO flag, medical protocol selection.

### E. Knowledge Base and Updater

The knowledge base contains curated chunks from Indian government sources indexed into FAISS and stored in MongoDB. A background scheduler runs every 6 hours:

1. Fetches each of 14 government URLs (via Jina Reader for JS-heavy portals).
2. Checksums responses against last-fetched SHA-256.
3. Re-ingests changed content, auto-chunking by paragraph (60-character overlap, sentence-level fallback for long paragraphs).
4. Snapshots the FAISS index (up to 5 retained for rollback).
5. Writes knowledge gaps (low-confidence queries) to MongoDB for admin triage.

### F. Security Architecture

- **JWT auth**: Access token (15 min TTL) + refresh token (30 days). Refresh tokens rotate on every use; password changes invalidate all tokens. Client-side expiry check prevents silent token reuse.
- **Field encryption**: Fernet AES-128 encryption on MongoDB name/email fields when `FIELD_ENCRYPTION_KEY` is set. HMAC-SHA256 digest stored separately for indexed email lookups.
- **Client-side encryption**: Session data (chat history, mood log) encrypted in localStorage with AES-GCM 256-bit. Key derived via PBKDF2 (100,000 iterations, SHA-256) from user ID + random per-device salt. Key exists only in memory; wiped on logout.
- **Prompt injection detection**: Instruction override detection, persona replacement patterns, jailbreak keywords, Llama delimiter tokens, second-order injection via retrieved documents.
- **Rate limiting**: slowapi with Redis backend. Auth: 5–10 req/min; chat: 30 req/min; admin: 5–20 req/min per endpoint.
- **Account lockout**: After 10 consecutive failed logins, account locked for 15 minutes. Timing-safe bcrypt comparison prevents email enumeration.

---

## IV. Implementation

### A. Frontend

React 18 with concurrent rendering, lazy-loaded heavy components (admin dashboard, eligibility checker, breathing companion, sign-out dialog), and error boundaries. Vite 5 with Rollup bundling. Tailwind CSS with four theme variants (one per persona domain). Radix UI primitives for accessible modals, tooltips, dropdowns. PWA with service worker (cache-first assets, stale-while-revalidate app shell) and manifest shortcuts for direct persona launch.

### B. Backend

FastAPI with async route handlers and SSE streaming. LangGraph 0.2+ for graph orchestration. Motor async driver for MongoDB. sentence-transformers (multilingual-e5-small) for query embedding. faiss-cpu for ANN search. rank-bm25 for keyword retrieval. cross-encoder/ms-marco-MiniLM-L-6-v2 for reranking. slowapi for rate limiting. PyJWT + bcrypt for authentication. cryptography (Fernet) for field encryption.

### C. LLM Providers

| Role | Primary | Fallback 1 | Fallback 2 |
|---|---|---|---|
| Text generation | Groq (llama-3.3-70b) | Anthropic Claude | Ollama (local) |
| Fast classification | Groq (llama-3.1-8b) | Anthropic Claude | Ollama |
| Vision/image | OpenRouter (free tier) | Anthropic Claude | — |

Provider selection uses a circuit breaker per provider (3-failure threshold, 30-second reset) to fast-fail on unavailable providers without waiting for timeout.

### D. Deployment

Docker multi-stage build: Stage 1 builds React client (Node 20); Stage 2 copies static bundle into Python 3.11 image. `prebuild_rag.py` downloads embedding model and builds FAISS index at image build time so cold starts are instant. Deployed on Hugging Face Spaces (free tier, 16 GB RAM, CPU-only).

---

## V. Evaluation

### A. Routing Accuracy

Evaluated on a frozen 100-query set (25 per domain), with bootstrap 95% confidence interval (1,000 resamples, seed=1729).

| Domain | Accuracy | n |
|---|---|---|
| Government Schemes | 100% | 25 |
| Legal | 100% | 25 |
| Mental Health | 92% | 25 |
| Safety | 88% | 25 |
| **Overall** | **95%** (CI: 91–99%) | **100** |

Misrouting occurs primarily at the Mental Health / Safety boundary, where distress queries overlap with safety-adjacent intent. Both personas escalate to crisis resources when emergency language is present, making misrouting at this boundary low-risk.

### B. Retrieval Quality

Evaluated on the same 100-query set. Retrieval p50 = 93 ms (CPU, no GPU).

| Metric | Overall | Govt Schemes | Legal | Mental Health | Safety |
|---|---|---|---|---|---|
| P@1 | 84.0% | 96.0% | 84.0% | 72.0% | 84.0% |
| Recall@5 | 69.3% | 63.1% | 79.2% | 70.7% | 64.3% |
| Recall@10 | 80.6% | 77.6% | 88.6% | 79.3% | 76.8% |
| MRR | 0.896 | 0.970 | 0.901 | 0.827 | 0.887 |
| NDCG@5 | 0.716 | 0.702 | 0.793 | 0.683 | 0.686 |
| NDCG@10 | 0.766 | 0.769 | 0.831 | 0.719 | 0.743 |

MRR = 0.896 implies the first relevant result appears at position ≈1.1 on average, indicating the cross-encoder reranker rarely needs to rescue buried results. Mental Health retrieval is weakest because emotional queries ("I feel lost") have minimal keyword overlap with the curated knowledge base.

### C. Retrieval Stage Latency (CPU, 30 runs)

| Stage | p50 | p90 | p99 |
|---|---|---|---|
| Query embedding | 32.5 ms | 43.5 ms | 48.0 ms |
| FAISS ANN search | 1.0 ms | 1.4 ms | 1.7 ms |
| **Total retrieve()** | **33.3 ms** | **45.0 ms** | **49.5 ms** |

Retrieval accounts for less than 5% of total end-to-end latency, which is dominated by the two Groq LLM calls (8B + 70B).

### D. Baseline Comparison

Evaluated on 50-query held-out split (TEST_HELDOUT), never seen during development.

| System | Description |
|---|---|
| **A. FULL** | Bi-encoder + cross-encoder + persona domain filter (production) |
| B. VANILLA_RAG | Bi-encoder only, no reranker, no domain filter |
| C. SINGLE_PERSONA | Cross-encoder, no domain filter |
| D. ZERO_SHOT_LLM | No retrieval — plain LLM with one-paragraph system prompt |

| System | P@1 | MRR | p50 Latency | Cross-domain leaks |
|---|---|---|---|---|
| **A. FULL** | **76.0%** | **0.861** | **50 ms** | **0** |
| B. VANILLA_RAG | 68.0% | 0.805 | 44 ms | 6 |
| C. SINGLE_PERSONA | 68.0% | 0.805 | 44 ms | 6 |
| D. ZERO_SHOT_LLM | — | — | 903 ms | — |

The production system outperforms both RAG baselines by 8 percentage points in P@1. The persona domain filter eliminates all cross-domain retrieval leaks (0 vs. 6 for B and C). The held-out P@1 of 76% is lower than 84% on the full set, as expected given harder edge-case queries.

### E. Persona Benchmark

210 structured test cases with keyword coverage and violation checks.

| Persona | Cases | Pass Rate | Keyword Coverage | Violations |
|---|---|---|---|---|
| Umang (Legal) | 100 | 100% | 100% | 0 |
| Aarogya (Govt Schemes) | 50 | 100% | 100% | 0 |
| Usha (Mental Health) | 30 | 100% | 100% | 0 |
| Raksha (Safety) | 30 | 100% | 100% | 0 |

### F. Hallucination Probe Suite

14 adversarial probes targeting the most common LLM failure modes in this domain.

| Probe Category | Probes | Flagged |
|---|---|---|
| Wrong statute citation (e.g. "Section 138 IPC" for cheque bounce) | 4 | 0 |
| Wrong helpline number | 4 | 0 |
| Wrong scheme benefit amount | 3 | 0 |
| Should-refuse (diagnosis, outcome prediction, dosage) | 3 | 0 |
| **Total** | **14** | **0 (0%)** |

Zero hallucinations flagged across all 14 probes, attributable to retrieval grounding, post-generation section-number range checks, and explicit confidence-aware prompting that instructs the persona to acknowledge uncertainty rather than fabricate details.

---

## VI. Discussion

### A. Design Decisions

**Why LangGraph over a single-chain RAG?** Agentic graphs allow conditional execution (only trigger web search when needed), parallel node execution (three classify calls in parallel), and explicit state management across turns. This reduces average latency by approximately 40% over serial multi-step chains on the same hardware.

**Why hard-coded crisis detection?** LLMs exhibit non-deterministic behavior on safety-critical inputs. A regex-based crisis detector across 35+ phrases in four languages runs in microseconds, never hallucinates, and can be audited line by line. The LLM handles the empathetic response after deterministic routing has already fired.

**Why dual-pass FAISS for Hindi?** The knowledge base is English-only. A single-pass embedding of a Hinglish query ("mujhe chahiye PM Kisan ka paisa") retrieves poorly because multilingual-e5-small encodes Hinglish differently from English. Extracting English-vocabulary tokens and running a second pass, then RRF-fusing, recovers the relevant English chunks. P@1 for Hindi queries improves from approximately 61% (single-pass) to 72% (dual-pass).

### B. Limitations

- Response quality depends on LLM provider availability. All three text providers going offline triggers a graceful offline message, not a crash.
- The retrieval layer occasionally misses very specific eligibility sub-conditions and obscure legal provisions. Web search fallback covers some but not all gaps.
- The HF Spaces free tier cold-start (15–30 seconds after inactivity) affects first-request latency.
- Evaluation of generation quality (faithfulness, helpfulness, persona fit scores from the eval_gen framework) was not completed before submission deadline.

### C. Ethical Considerations

The system explicitly states in every response that it is not a substitute for professional legal or medical advice. Crisis detection routes to human helplines (iCall, Tele-MANAS, CHILDLINE) rather than attempting AI-led crisis intervention. PII redaction (email, Aadhaar, PAN, credit card, phone) is applied before any summarization call. No user data is used for model training.

---

## VII. Conclusion

This paper presented Seelenruh, a production-deployed agentic RAG system for multilingual assistance in mental health, legal, social welfare, and emergency safety domains. The system achieves 95% routing accuracy, MRR = 0.896, and 0% hallucination rate on adversarial probes through a combination of LangGraph-orchestrated parallel classification, hybrid dual-pass retrieval with bilingual Hindi support, deterministic safety overrides, and confidence-aware generation. The system demonstrates that careful engineering — deterministic crisis detection, section-number range guardrails, persona domain filtering, and explicit uncertainty acknowledgment — can substantially reduce LLM failure modes in high-stakes domains without requiring model fine-tuning.

Future work includes: evaluation of generation quality metrics (faithfulness, helpfulness), extension of the knowledge base to state-specific legal provisions, fine-tuning a small classifier to replace the LLM-based intent detector, and evaluation with real users across language groups.

---

## References

[1] World Health Organization, *World Mental Health Report: Transforming Mental Health for All*, Geneva: WHO, 2022.

[2] P. Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 33, pp. 9459–9474, 2020.

[3] A. Rackauckas, "RAG-Fusion: A New Take on Retrieval-Augmented Generation," arXiv:2402.03367, 2024.

[4] L. Gao et al., "Precise Zero-Shot Dense Retrieval without Relevance Labels," in *Proc. ACL*, pp. 1762–1777, 2023.

[5] G. V. Cormack, C. L. A. Clarke, and S. Buettcher, "Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods," in *Proc. SIGIR*, pp. 758–759, 2009.

[6] LangChain, Inc., "LangGraph: Orchestrating Agentic Workflows with Stateful Graphs," GitHub repository, 2024. [Online]. Available: https://github.com/langchain-ai/langgraph

[7] A. Fitzpatrick, K. Darcy, and M. Vierhile, "Delivering Cognitive Behavior Therapy to Young Adults With Symptoms of Depression and Anxiety Using a Fully Automated Conversational Agent (Woebot)," *JMIR Mental Health*, vol. 4, no. 2, e19, 2017.

[8] R. Morris et al., "Efficacy of Peer Support via Text Messaging in a College Mental Health Setting," in *Proc. CHI Extended Abstracts*, 2015.

[9] A. Deroy and S. Sarkar, "A Hybrid Approach for Legal Document Summarization," in *Proc. International Conference on Natural Language Processing (ICON)*, 2022.

[10] N. Thakur et al., "BEIR: A Heterogeneous Benchmark for Zero-Shot Evaluation of Information Retrieval Models," in *Proc. NeurIPS Datasets and Benchmarks*, 2021.

[11] R. Nogueira and K. Cho, "Passage Re-ranking with BERT," arXiv:1901.04085, 2019.

[12] Ministry of Electronics and Information Technology, Government of India, *Digital Personal Data Protection Act 2023*, New Delhi, 2023.

[13] Ministry of Law and Justice, Government of India, *Bharatiya Nyaya Sanhita 2023*, New Delhi, 2023.

[14] National Mental Health Programme, Ministry of Health and Family Welfare, *Tele Mental Health Assistance and Networking Across States (Tele-MANAS)*, New Delhi, 2022.
