---
title: Seelenruh
emoji: 🌸
colorFrom: pink
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---
# Seelenruh

Seelenruh is my final year B.Tech project — a conversational assistant aimed at Indian users who often don't know where to turn when they need mental health support, legal guidance, help navigating government schemes, or emergency safety information.

Live demo: [Hugging Face Spaces](https://huggingface.co/spaces/aradhyastuti/seelenruh)

## Why I built this

A lot of people around me — friends, family — would hit a wall whenever they needed information about things like their tenant rights, which government schemes they might be eligible for, or just someone to talk to when they were struggling. The information exists, but it's scattered, often in legalese, and not accessible to people who speak Hindi or Hinglish rather than formal English.

So I built something that routes questions to the right "persona" and pulls from a curated knowledge base rather than making things up. The name Seelenruh is German for "peace of mind", which felt right for what I was going for.

## What it does

The app routes user messages to one of four personas:

- **Usha** — mental health and emotional support. Warm, non-judgmental, conversational.
- **Umang** — legal guidance and rights-based advice. Plain-language explanations, act/section citations.
- **Aarogya** — government schemes and entitlements. Eligibility checks, application steps.
- **Raksha** — safety and emergency support. Calm, action-oriented, emergency contacts.

## Features

### Chat

- Persona-based routing with a dedicated chat window per persona. Clicking a persona card opens its chat window; a back arrow returns to the selection screen.
- Streaming responses token by token via SSE.
- Quick reply prompts shown when you open a persona's chat for the first time.
- Cross-session memory — the system remembers context within a session, including emotional trajectory.
- Goal tracking — detects what you're trying to accomplish (e.g. "file an RTI") and tracks it across turns.
- Session history per persona — browse and restore past conversations.
- Copy, save (bookmark), and thumbs up/down feedback on any response.
- Export conversation as JSON, Markdown, or plain text (server-side, authenticated).
- Attach a document (.txt, .md, .pdf, .docx, .csv) to provide as context for your next message.
- Voice input — mic button in the chat bar records audio and transcribes it via Groq Whisper STT; fills the input field automatically.
- Read aloud — speaker button on every assistant message plays the response via ElevenLabs TTS (gTTS fallback); click again to stop.

### Retrieval

- Hybrid retrieval: FAISS vector search + BM25 keyword search combined with reciprocal rank fusion.
- Cross-encoder reranking before the final response.
- Query rewriting — short queries are expanded by the LLM before retrieval, cached to avoid duplicate calls.
- Confidence scoring (High / Medium / Low / None) shown per response.
- Source citations with authority badges — Authoritative, Official, Institutional.
- Automatic web search fallback (Brave → Tavily → DuckDuckGo → SerpAPI → Wikipedia cascade) when RAG confidence is Low/None or retrieval hits are insufficient.
- Output grounding for all four personas — verifies cited section numbers and flags hallucinated references before they reach the user.
- Hallucination guardrails: section number range checks, foreign law detection, overpromising language flags.

### AI pipeline

- 11-state emotion taxonomy: sad, angry, happy, scared, confused, neutral, hopeless, overwhelmed, anxious, frustrated, numb. Each state has distinct tone guidance injected into the composer prompt.
- Secondary emotion field — when a message carries a clear second emotion (e.g. sad + numb), both are surfaced to the composer.
- Emotion arc tracking — the rolling emotional trajectory across turns (e.g. calm → anxious → hopeless) is stored per session and surfaced as a TREND FLAG when worsening.
- Confidence-aware prompting — when RAG confidence is Low or None, the persona is explicitly told to acknowledge uncertainty and ask clarifying questions rather than fabricate details.
- Conversation depth awareness — after turn 3, the composer is told not to repeat advice already given.
- Dynamic knowledge updater — a background scheduler (every 24 hours) crawls 13 authoritative government sources, checksums responses, and re-ingests changed content into the knowledge base automatically.

### Persona-specific tools

**Usha (Mental Health)**

- Mood check-in button in the toolbar. Pick from five moods (Joyful, Calm, Tired, Anxious, Sad); shows an affirmation and a practical tip. Mood history tracked with a streak counter and 14-day visual chart. Old entries (> 60 days) are pruned automatically.
- Breathing companion: three guided patterns (Calm 4-6, Box 4-4-4-4, 4-7-8) with animated visual guidance. Accessible from the header.
- Hard-coded crisis detection (Python, no LLM) in 35+ English, Hinglish, Hindi (Devanagari), and German phrases — never relies on the language model for life-safety routing.
- Emergency contacts bar appears automatically on crisis detection: Police 100, Ambulance 102, Women Helpline 1091, iCall 9152987821, Tele-MANAS 14416, CHILDLINE 1098.

**Umang (Legal)**

- Embedded legal timelines for salary recovery, eviction, consumer complaints, and divorce — shows steps, typical duration, documents needed, and approximate costs.
- Response template enforces a structured 9-section format (situation → applicable law → steps → timeline → documents → cost → helpline → disclaimer).
- Few-shot examples seeded into the composer covering 10 common legal scenarios in English and Hinglish.

**Aarogya (Government Schemes)**

- Eligibility checker tool: fill in state, age, income, student/farmer status and get matched schemes instantly without hitting the LLM. Lazy-loaded, opens as a modal from the chat toolbar.
- 20+ schemes with composable eligibility predicates (income thresholds, age ranges, farmer/student flags, state restrictions).

**Raksha (Safety)**

- Deterministic safety plans (Python dict lookup, no LLM) for 8 threat types: domestic violence, cybercrime, workplace harassment, trafficking, natural disaster, and others.
- POCSO detection flag — automatically routes child-protection queries to relevant provisions.

### Security

- Field-level Fernet encryption for sensitive MongoDB fields (name, email) when `FIELD_ENCRYPTION_KEY` is set. HMAC-SHA256 digest stored separately for indexed email lookups.
- Prompt injection detection covering instruction overrides, persona replacement, jailbreak keywords, special LLM tokens (Llama delimiters), and second-order injection via retrieved documents. Attempts are logged to MongoDB for audit.
- Account lockout after 10 consecutive failed logins (15-minute TTL). Timing-safe bcrypt comparison prevents email enumeration.
- JWT refresh-token rotation on every use. Revoked tokens stored in MongoDB with TTL index. Password changes invalidate all previously issued refresh tokens.
- Rate limiting on every endpoint (slowapi, Redis-backed in production): auth routes 5-10/min, chat 30/min, TTS 15/min.
- PII redaction (email, Aadhaar, PAN, credit card, phone) before any summarization call.

### Language

- English, Hindi (Devanagari), Hinglish (Roman script), and German supported.
- Heuristic language detection from message text — no extra LLM call. Upgrades Hinglish queries even when the user has selected "hi".
- Language toggle in the header; the selected language is sent to the backend and the persona responds accordingly.
- When chatting in German, a translate button appears on each assistant response — click to see an English translation inline, click again to hide.
- German speaker guardrails: persona explicitly states it answers under Indian law, never German/EU law, with translated explanations of Indian legal terms.

### Account

- Email/password signup and login. Verification email sent on signup; account requires verification before chat is unlocked.
- Forgot password and reset password flow via email token.
- Change password from the account menu (invalidates all existing sessions on all devices).
- Sign out with optional local data wipe.
- Account deletion with full data purge (messages, summaries, goals, memory, feedback).
- Full data export as JSON from the account menu.

### PWA

- Installable as a Progressive Web App on Android and desktop.
- Service worker: assets cached indefinitely (cache-first), app shell uses stale-while-revalidate. API calls are never intercepted.
- Manifest shortcuts let users launch directly into a specific persona — `?domain=mental-health`, `?domain=legal`, `?domain=schemes`, `?domain=safety`.

### Explainability

- Every response shows a "Why?" panel that visualises the RAG pipeline: Embed → FAISS → BM25 → RRF → Rerank → LLM.
- Routing trace shows which domain was selected and why (intent reasoning from the classifier).
- Source panel shows which knowledge chunks were retrieved and cited, with authority level, review status, and source URLs.

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Radix UI, shadcn/ui |
| Backend | Python 3.10+, FastAPI, LangGraph |
| LLM providers | Groq (primary), Anthropic Claude, Ollama (fallbacks) |
| Embeddings | intfloat/multilingual-e5-small |
| Retrieval | FAISS + BM25 + cross-encoder reranker (ms-marco-MiniLM-L-6-v2) |
| Web search | Brave → Tavily → DuckDuckGo → SerpAPI → Wikipedia (cascade) |
| Database | MongoDB Atlas (motor async driver) |
| Cache/rate limiting | Redis (optional, falls back to in-memory) |
| Auth | PyJWT + bcrypt, field-level Fernet encryption |
| TTS | ElevenLabs (primary), gTTS (fallback) |
| STT | Groq Whisper (whisper-large-v3-turbo) |
| Deployment | Docker, Hugging Face Spaces, nginx reverse proxy |
| PWA | Service worker, Web App Manifest |

## Architecture

The project splits into a frontend and a backend:

- The frontend lives in `client/` and handles the chat UI, session history, saved moments, mood tracking, and breathing exercises.
- The backend lives in `server/` and contains the FastAPI app, the LangGraph workflow, and the retrieval modules.

**Main graph** — six nodes per request:

```
load_memory → classify → route → retrieve → maybe_search → generate → save_memory
```

- `classify` runs intent detection, 11-state emotion detection, and goal detection in parallel (three concurrent LLM calls, ~150ms each on Groq).
- `maybe_search` triggers web search when RAG confidence is Low/None, even if the heuristic threshold isn't met.
- `generate` dispatches to one of four domain sub-graphs depending on the routed domain.

**Domain sub-graphs** — each runs `analyze → prepare → compose`:

- `analyze`: fast 8B LLM call classifying the emotional/legal/scheme/safety context of the query.
- `prepare`: pure Python — organises retrieved chunks by topic relevance, runs deterministic crisis/safety checks.
- `compose`: 70B LLM call building the final response using the prepared context, persona prompt, and conversation history.

**Retrieval pipeline**: FAISS vector search → BM25 keyword search → reciprocal rank fusion → cross-encoder reranker → top-k chunks passed to composer.

**Memory**: rolling session summary (updated in the background after every response, never blocking the main path) + emotion arc (last 10 turns) + cross-session user memory (aggregated from last 8 session summaries).

One thing I spent a lot of time on was making sure the system doesn't make things up when it doesn't know something. The knowledge base is curated, citations are validated against the retrieved corpus before they appear in the response, and the LLM is explicitly told when its knowledge is limited so it asks clarifying questions instead of hallucinating.

## Evaluation results

All numbers below come from saved benchmark runs in `server/results/` and `server/bench/reports/`. Generation quality scores (faithfulness, helpfulness, persona_fit) are measured by the `eval_gen.py` framework but have no saved run yet — those numbers are excluded here.

### Routing accuracy

Evaluated on 100 queries (25 per domain), frozen test set, bootstrap 95% CI (1,000 resamples, seed=1729). Source: `server/results/canonical.json` (2026-05-31).

| Domain | Accuracy | n |
|---|---|---|
| Government Schemes | 100% | 25 |
| Legal | 100% | 25 |
| Mental Health | 92% | 25 |
| Safety | 88% | 25 |
| **Overall** | **95%** (CI: 91%–99%) | **100** |

The two domains where routing misses occur most are Mental Health (queries expressing distress that overlap with Safety intent) and Safety (safety-adjacent queries that the classifier routes to Mental Health). These are handled gracefully — both personas escalate to crisis resources when emergency language is present.

### Retrieval

Evaluated on the same 100-query set. Source: `server/bench/reports/retrieval_report.md` (2026-07-13).

| Metric | Overall | Govt Schemes | Legal | Mental Health | Safety |
|---|---|---|---|---|---|
| P@1 | 84.0% | 96.0% | 84.0% | 72.0% | 84.0% |
| Recall@5 | 69.3% | 63.1% | 79.2% | 70.7% | 64.3% |
| Recall@10 | 80.6% | 77.6% | 88.6% | 79.3% | 76.8% |
| MRR | 0.896 | 0.970 | 0.901 | 0.827 | 0.887 |
| NDCG@5 | 0.716 | 0.702 | 0.793 | 0.683 | 0.686 |
| NDCG@10 | 0.766 | 0.769 | 0.831 | 0.719 | 0.743 |
| Retrieval p50 | 93 ms | 93 ms | 104 ms | 79 ms | 98 ms |

Mental Health is the weakest domain for retrieval because emotional support queries are often non-specific ("I feel lost", "I don't know what to do") with no clean keyword overlap against the knowledge base. Conversely, Government Schemes retrieves well because queries tend to name specific schemes or eligibility conditions.

MRR=0.90 means that on average the first relevant result appears in position 1.1, so the reranker rarely needs to rescue a buried gold chunk.

### Retrieval stage latency (CPU, 30 runs)

Source: `server/bench/reports/latency_report.md` (2026-07-13). Measured on CPU without GPU acceleration.

| Stage | p50 | p90 | p99 |
|---|---|---|---|
| Query embedding | 32.5 ms | 43.5 ms | 48.0 ms |
| FAISS ANN search | 1.0 ms | 1.4 ms | 1.7 ms |
| **Total retrieve()** | **33.3 ms** | **45.0 ms** | **49.5 ms** |

BM25 and cross-encoder reranking times are sub-millisecond on the standard index size and do not materially affect the p90. The full end-to-end response time is dominated by the two Groq LLM calls (8B analyzer + 70B composer); the retrieval step is less than 5% of total latency on a representative request.

### Baseline comparison

Evaluated on the TEST_HELDOUT split (50 queries, never seen during development) using `eval_baselines.py`. Source: `server/results/baselines_test_20260718_103703.json` (2026-07-18, live run).

Four systems compared:

| System | Description |
|---|---|
| **A. FULL** | bi-encoder + cross-encoder reranker + persona-domain filter (production) |
| B. VANILLA_RAG | bi-encoder only, no reranker, no domain filter |
| C. SINGLE_PERSONA | cross-encoder reranker, no domain filter |
| D. ZERO_SHOT_LLM | no retrieval — plain LLM with a one-paragraph system prompt |

**Retrieval results (TEST_HELDOUT, n=50):**

| System | P@1 | MRR | Retrieval p50 | Cross-domain leaks |
|---|---|---|---|---|
| **A. FULL (prod)** | **76.0%** | **0.861** | **50 ms** | **0** |
| B. VANILLA_RAG | 68.0% | 0.805 | 44 ms | 6 |
| C. SINGLE_PERSONA | 68.0% | 0.805 | 44 ms | 6 |
| D. ZERO_SHOT_LLM | — | — | 903 ms | — |

**Deltas (FULL minus baseline, positive = FULL wins):**

| Comparison | ΔP@1 | ΔMRR |
|---|---|---|
| FULL vs VANILLA_RAG | **+8.0 pp** | **+0.056** |
| FULL vs SINGLE_PERSONA | **+8.0 pp** | **+0.056** |

**Zero-shot LLM keyword coverage (6 safety/legal probes):** 100% — the LLM correctly recalled helpline numbers, Section 138 NI Act, and PM-KISAN amounts from its training weights. This is not surprising for widely-known facts; the probes are designed to test recall of stable government information, not niche eligibility conditions. The gap between RAG and zero-shot appears on rare or recently-updated facts where the model has no training signal.

**Reading the numbers:**

The FULL system beats both baselines by 8 percentage points in P@1 on the held-out split. Comparing B and C reveals that the reranker alone (C) provides zero gain over plain bi-encoder (B) when there is no domain filter — the cross-encoder sees candidates from all four domains and the top-ranked chunk ends up in the wrong domain on 6/50 queries (12%). The domain filter eliminates all cross-domain leaks (0 for FULL), giving the reranker a cleaner candidate pool to work with. In other words, the persona-domain filter is doing the heavy lifting, not the reranker in isolation.

The TEST_HELDOUT P@1 of 76% is lower than the 84% on the full 100-query set in `canonical.json` — this is expected. The heldout set was never used during development and contains harder edge cases, so the gap is a realistic estimate of generalisation.

### Hallucination probe suite

14 probes across four categories, evaluated against known-correct reference values. Source: `server/bench/reports/hallucination_report.md` (2026-07-13).

| Probe category | Probes | Flagged |
|---|---|---|
| Wrong statute citation (e.g. "Section 138 IPC" for cheque bounce) | 4 | 0 |
| Wrong helpline number | 4 | 0 |
| Wrong scheme amount | 3 | 0 |
| Should-refuse (diagnosis, outcome prediction, dosage) | 3 | 0 |
| **Total** | **14** | **0 (0.0%)** |

The 0% rate is against a targeted probe set, not an exhaustive one. The probes cover the failure modes I observed during development — specific hallucinated section numbers, wrong helpline digits, and scheme amounts that had changed — not the full space of possible hallucinations.

### Test set composition

The 100-query frozen evaluation set (`eval_data.py`) spans four languages: English, Hindi (Devanagari script), Hinglish (Roman script), and German. It includes three near-neighbour adversarial pairs (queries with similar surface form but different correct domains) and eight queries with no direct knowledge-base match (to test graceful low-confidence handling). The set is split 50/50 into DEV (used during development) and TEST_HELDOUT (run once for final numbers).

## Installation

```bash
npm run install:all
```

Then set up the server's environment file:

```bash
cp .env.example server/.env
```

Fill in the required values before running:

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key for LLM + Whisper STT |
| `JWT_SECRET` | Yes | 32+ byte random string for signing JWTs |
| `MONGODB_URI` | Yes | MongoDB Atlas connection string |
| `ANTHROPIC_API_KEY` | No | Fallback LLM provider (Anthropic Claude) |
| `OLLAMA_URL` | No | Local Ollama instance URL |
| `ELEVENLABS_KEY` | No | Neural TTS (gTTS used if absent) |
| `ELEVENLABS_VOICE_ID` | No | ElevenLabs voice ID |
| `BRAVE_SEARCH_KEY` | No | Brave Search API key (web search cascade) |
| `TAVILY_API_KEY` | No | Tavily Search API key (second web fallback) |
| `SERPAPI_KEY` | No | SerpAPI key (fourth web fallback) |
| `RESEND_API_KEY` | No | Resend API key for transactional email |
| `SMTP_HOST` | No | SMTP server for email (alternative to Resend) |
| `SMTP_USER` | No | SMTP username |
| `SMTP_PASSWORD` | No | SMTP password |
| `FIELD_ENCRYPTION_KEY` | No | 32-byte hex key for Fernet field encryption |
| `REDIS_URL` | No | Redis URL for persistent rate-limit counters |
| `ADMIN_KEY` | No | Secret key for `/api/admin/*` knowledge ingestion endpoints |

## Usage

Start both backend and frontend together:

```bash
npm run dev
```

The backend runs from `server/` and the frontend runs via Vite. Defaults are `http://localhost:5000` for the API and `http://localhost:5173` for the client.

## Evaluation

There's a small evaluation harness and a functional test suite:

```bash
cd server
./.venv/Scripts/python -m pytest tests/test_functional_cases.py -q
```

The evaluation scripts under `evaluation/` and the top-level `evaluate.py` are for offline checks on routing accuracy, response quality, retrieval behaviour, and latency. `evaluate.py` requires a running server and a valid JWT token (`--token`).

## Deployment

The app runs in Docker. The Dockerfile builds the React client in stage one, then copies the static bundle into the Python server image. The `prebuild_rag.py` script downloads the embedding model and builds the FAISS index at image build time so cold starts are instant.

```bash
docker build -t seelenruh .
docker run -p 7860:7860 --env-file server/.env seelenruh
```

For Hugging Face Spaces, push to the `space` remote:

```bash
git push space main
```

## Challenges

A few things that were harder than expected:

- **Multilingual retrieval** — making BM25 and FAISS both work well for Hinglish queries required a lot of manual query expansion. I ended up building a token-level Hinglish-to-English map and a phrase-level one on top.
- **Hallucination** — LLMs will confidently cite IPC Section 600 (which doesn't exist). I built pattern-based guardrails that check section numbers against known ranges and flag anything suspicious before the response goes out.
- **Persona voice** — getting Umang to sound like a knowledgeable advisor rather than a disclaimer machine, while still being accurate, took a lot of prompt iteration.
- **Streaming + memory** — combining SSE streaming with background memory saves without blocking the main response path was tricky to get right.
- **Mood + domain isolation** — the mood check-in should only influence Usha's responses, not Aarogya or Umang. Took careful scoping to make sure the mood hint doesn't leak into unrelated queries.
- **Emotion granularity** — the first version had six emotional states. In practice, the difference between "hopeless" and "sad" or between "overwhelmed" and "anxious" matters a lot for how the persona should respond. Expanding to eleven states and writing distinct tone guidance for each made a noticeable difference in response quality.
- **Crisis safety** — I deliberately don't rely on the LLM for crisis detection. Hard-coded phrase matching in 35+ English, Hinglish, Hindi, and German phrases runs in microseconds and never hallucinates. The LLM gets the final response but the safety routing is deterministic.

## Known issues

- Response quality depends on which LLM provider is available. Groq is the default; Anthropic and Ollama are fallbacks. If all three are down, the app returns a graceful offline message.
- The retrieval layer occasionally misses edge cases — especially for very specific scheme eligibility questions or obscure legal provisions. Web search fills in some gaps but not all.
- Email sending (verification, password reset) requires SMTP or Resend credentials. In the demo deployment these aren't configured, so tokens are logged to the server console instead.
- This is not a substitute for professional legal or medical advice, and the app says so explicitly in every response.

## Acknowledgements

This project wouldn't have gotten very far without LangGraph, FAISS, sentence-transformers, FastAPI, and the shadcn/ui component library. These covered enough infrastructure that I could spend most of my time on the parts that were specific to this problem — the routing logic, retrieval tuning, multilingual handling, and making sure the personas actually help people rather than just sounding helpful.
