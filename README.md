---
title: Seelenruh
emoji: 🌸
colorFrom: pink
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---
# Seelenruh: A LangGraph-Powered Agentic RAG System for Multi-Domain Civic and Mental Health Support

Live demo: [Hugging Face Spaces](https://huggingface.co/spaces/aradhyastuti/seelenruh)

---

I built this as my final year B.Tech project. The name means "peace of the soul" in German — which felt right for what I was trying to make.

The problem I kept coming back to: most people in India don't know what government schemes they're actually entitled to, don't know their legal rights when something goes wrong, and have very limited access to mental health support. I wanted to build one app that addresses all three, plus safety in emergencies — and do it in a way that works for Indian users, including people who write in Hindi or Hinglish.

What started as a simple RAG chatbot turned into something more interesting once I started working with LangGraph. The agentic features — persistent memory, goal tracking, autonomous web search — weren't in the original plan. They came out of noticing real gaps in how the assistant behaved during testing.

---

## The four assistants

- **Usha** — mental health and emotional support. Designed to feel like talking to a calm, older friend, not a clinical chatbot. No bullet-point lists, no "your feelings are valid" every message.
- **Umang** — legal rights. FIR filing, RTI, consumer complaints, tenant rights, labour law, divorce — always grounded in actual Indian law and section numbers. Covers the new BNS/BNSS/BSA 2023 codes replacing IPC/CrPC.
- **Aarogya** — government schemes. PM-JAY, PM-KISAN, MGNREGA, scholarships, ration cards, and state-level schemes for Delhi, Gujarat, Rajasthan, Bihar, Punjab, Kerala, Himachal Pradesh, Goa.
- **Raksha** — safety and emergencies. Domestic violence, cybercrime, stalking, panic response. Returns structured step-by-step cards with helpline numbers, not paragraphs.

Each assistant uses RAG so answers are grounded in actual documents, not just whatever the LLM guesses. Responses cite sources inline, and staleness penalties are domain-aware — government scheme chunks expire aggressively (budget cycles change fast), while legal statutes are treated as stable.

---

## Why LangGraph — and what makes it agentic

I initially used a simple chain: query → retrieve → generate. That worked for basic factual questions but fell apart quickly. The LLM had no memory, couldn't decide when to search the web, and had no idea if the user was working toward a longer-term goal.

Switching to LangGraph let me build a graph where the agent controls its own flow:

```
START → load_memory → classify → route → retrieve → maybe_search → generate → save_memory → END
```

Three things make this genuinely agentic rather than just a chatbot with a knowledge base:

**1. Autonomous web search**
The agent decides on its own whether to run a web search. It triggers when the query has real-time signals (`latest`, `current`, `2025`, helpline numbers, `abhi`, `naya`…), when RAG returns too few or low-confidence results, or always for Legal and Government Schemes domains (those go stale fast). DuckDuckGo, Wikipedia, and optionally Brave Search run concurrently with retry backoff so a flaky network doesn't silently drop results.

**2. Self-evolving memory**
After every response, a background task compresses the conversation into a 2–3 sentence summary and extends an emotion arc (`neutral → anxious → calm → …`). Both go into MongoDB. Next turn, `load_memory` fetches them and injects them into the system prompt as a `CONVERSATION CONTEXT` block — correctly in the system prompt, not mixed into the user message. The user never has to repeat context — the agent just remembers.

**3. Goal tracking**
Every turn, `detect_goal` runs in parallel with intent and emotion detection. If it finds something actionable — `"file an RTI"`, `"apply for PM-JAY"`, `"find a therapist"` — it stores that goal and surfaces it on every subsequent turn. Once a goal is stored, the detector only fires again if it sees a *new or changed* goal — no redundant DB writes. A live goal badge appears in the UI so the user can see what the agent is tracking.

---

## Umang's legal pipeline — multi-agent architecture

Umang uses a dedicated 3-node LangGraph sub-graph with a modular prompt architecture:

```
query → _analyze (8B) → _prepare (Python) → _compose (70B) → quality gates → response
```

**Agent 1 — Case Analyzer (llama-3.1-8b-instant)**
Classifies the query with structured JSON output: `category`, `issue_type` (Civil/Criminal/Employment/Family/Property/Consumer/Cyber/Administrative), `employment_type`, `property_type`, `urgency`, `known_facts`, `missing_facts`, `follow_up`, `limitation_concern`.

**Agents 2–6 — Preparation (Python)**
Organises RAG chunks by type (rights / procedure / general), builds a deterministic legal reasoning context from `_LEGAL_KNOWLEDGE`, detects jurisdiction from the query, loads document templates if needed.

**Agent 7 — Response Composer (llama-3.3-70b-versatile)**
Synthesises the final response with a system prompt assembled from modular components:

| Component | Module | ~Tokens |
|-----------|--------|---------|
| Persona (10 core rules) | `responder.py` → `PERSONA["Legal"]` | ~730 |
| Language instruction | `language_engine.py` → `build_language_instruction()` | ~100 |
| Response format (9 sections) | `response_template.py` → `RESPONSE_TEMPLATE_DESCRIPTION` | ~350 |
| Few-shot example (1 relevant) | `few_shot_examples.py` → `get_few_shot_examples()` | ~400–600 |
| Case analysis block | `legal_agents.py` internal | ~100 |
| Legal reasoning context | `_LEGAL_KNOWLEDGE` dict | ~400 |
| Retrieved knowledge (5 chunks) | FAISS + BM25 hybrid | ~1,000 |
| **Total** | | **~3,100–3,280 tokens** |

**Post-response quality gates**
Every response passes through two validators before being returned:

- **Hallucination guardrails** (`hallucination_guardrails.py`) — checks section numbers against a 40-act whitelist (`KNOWN_ACTS`) with valid section ranges. Sections cited beyond the known maximum trigger a verification note.
- **Quality checker** (`quality_checker.py`) — pattern-based checks for overpromise language ("you will definitely win"), German law bleed-in, FIR misuse for salary disputes, and unverified helpline numbers.

**FIR Guard**
Umang never recommends filing a police complaint for unpaid salary or civil rent/warranty disputes. The Case Analyzer classifies these as `labour_dispute` or `civil_dispute` by default. Escalation order: written demand → Labour Commissioner (free) → Labour Court → FIR only if fraud/forgery/criminal offence.

---

## RAG pipeline — hybrid retrieval

```
query → normalise (Hinglish expansion + OCR cleanup) → legal query expansion (37+ regex patterns)
      → FAISS dense (multilingual-e5-small) + BM25 sparse (rank-bm25)
      → RRF fusion (k=60) → cross-encoder reranking → top-5 chunks
```

**Reciprocal Rank Fusion** combines dense semantic retrieval (FAISS) with lexical retrieval (BM25) without score normalisation issues. BM25 especially helps for exact law citations (`"Section 138 NI Act"`) that dense embeddings may not rank highly.

BM25 degrades gracefully — if `rank-bm25` is not installed, the pipeline falls back to FAISS-only with no code changes needed.

**Hinglish map** — 80+ Roman-script Hindi terms expanded to English equivalents before embedding:
`"tankhwaah"` → `"salary wages"`, `"kirayedaar"` → `"tenant renter"`, `"vakeel"` → `"lawyer"`, `"f&f"` → `"full and final settlement dues"`.

**Legal query expansion** — 37+ regex patterns append domain terminology to vague queries before embedding:
`"salary nahi mili"` → `+ "Code on Wages 2019 Payment of Wages Act unpaid salary labour commissioner..."`

---

## Multilingual support

Language is detected heuristically at request time (no LLM needed):
1. Devanagari unicode block → Hindi (`hi`)
2. German markers/characters (ä, ö, ü, ß + keyword list) → German (`de`)
3. Hinglish marker words (mujhe, kya, chahiye, nahi…) → Hinglish (`hi-roman`)
4. Fallback → English (`en`)

Each language gets a tailored instruction injected into the system prompt. German responses always cite Indian law — never German Mietrecht, BGB, or German courts. Indian legal terms are translated in parentheses: `"FIR (Strafanzeige bei der indischen Polizei)"`.

---

## Other features

- **Scheme eligibility checker**: rule-based, not LLM. The deterministic checker takes state, age, income, and category and returns exactly which schemes match.
- **Legal document templates**: RTI, consumer complaint, rent notice — filled from form inputs, not AI-generated. Keeps them legally consistent.
- **Automatic intent routing**: ask a legal question in the mental health tab and the agent detects it and reroutes. The UI shows the reasoning.
- Mood tracker, breathing companion, session summaries, saved moments, conversation export, offline detection, error boundary.
- **Auth**: JWT with JTI blacklisting on logout, bcrypt (12 rounds), timing-attack-resistant login. Account deletion wipes all messages, summaries, memory, and goals.

---

## Tech stack

| Layer | What I used |
|-------|-------------|
| Frontend | React 18, Vite, Tailwind CSS, shadcn/ui, Radix UI |
| Backend | Python 3.10, FastAPI, LangGraph |
| LLMs | Groq API — Llama 3.3 70B (responses), Llama 3.1 8B (intent/emotion/goal/memory) |
| Embeddings | `intfloat/multilingual-e5-small` |
| Vector search | FAISS (CPU) + BM25 hybrid (rank-bm25, Reciprocal Rank Fusion) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Database | MongoDB Atlas (Motor async driver) |
| Auth | PyJWT + bcrypt |
| Rate limiting | slowapi |
| Web search | DuckDuckGo + Wikipedia + Brave Search (concurrent, with retry backoff) |
| Deployment | Docker, Hugging Face Spaces |

---

## Project structure

```
server/
├── ai/
│   ├── legal_agents.py          # 7-agent pipeline (Case Analyzer → Response Composer)
│   ├── hallucination_guardrails.py  # Citation validation against KNOWN_ACTS whitelist
│   ├── language_engine.py       # Language detection + per-language instructions
│   ├── quality_checker.py       # Post-response pattern validation
│   ├── few_shot_examples.py     # 10 curated Q&A examples for system prompt injection
│   ├── response_template.py     # 9-section response format specification
│   └── responder.py             # Persona definitions + non-Legal response pipeline
├── rag/
│   ├── retriever.py             # FAISS + BM25 hybrid retrieval with RRF fusion
│   ├── knowledge_meta.py        # Domain-aware confidence scoring
│   └── knowledge/               # RAG chunk files
├── legal_graph.py               # LangGraph sub-graph for Umang
├── tests/
│   └── test_legal_cases.py      # 91 test cases across all legal categories
docs/
├── system_prompt.md             # System prompt component architecture + token budget
├── rag_architecture.md          # Full RAG pipeline diagram and configuration
├── response_template.md         # Response section definitions
├── few_shot_examples.md         # Example bank and selection logic
├── knowledge_base_structure.md  # Static knowledge + dynamic RAG chunk structure
└── developer_documentation.md   # Architecture overview, env vars, testing guide
```

---

## Running locally

You'll need Node.js 18+, Python 3.10 (exactly), a MongoDB Atlas URI, and a Groq API key (free at console.groq.com).

```bash
git clone https://github.com/AradhyaStuti/Seelenruh-Generative-AI-Assistant-with-RAG-LangGraph-and-FAISS.git
cd Seelenruh-Generative-AI-Assistant-with-RAG-LangGraph-and-FAISS
```

**Step 1 — Install all dependencies**

```bash
npm run install:all
```

**Step 2 — Set up environment**

```bash
cp .env.example server/.env
# Fill in GROQ_API_KEY, MONGODB_URI, JWT_SECRET
```

Generate JWT_SECRET with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Step 3 — Start the backend** (Terminal 1)

```bash
cd server
# Windows: .\.venv\Scripts\Activate.ps1
# Mac/Linux: source .venv/bin/activate
python -m uvicorn main:app --reload --port 5000
```

Wait for `Application startup complete.`

**Step 4 — Start the frontend** (Terminal 2)

```bash
npm --prefix client run dev
```

Open `http://localhost:5173`. Backend runs on port 5000.

First startup downloads the embedding model (`multilingual-e5-small`) and builds the FAISS + BM25 index — takes 1–2 minutes. Subsequent starts load from cache and are instant.

---

## Deployment

Deployed on Hugging Face Spaces using Docker. The React build is bundled into the image at build time and FastAPI serves it as static files, so everything runs from a single container.

```bash
docker build -t seelenruh .
docker run -p 5000:5000 --env-file server/.env seelenruh
```

Set `MONGODB_URI`, `GROQ_API_KEY`, and `JWT_SECRET` as HF Space secrets before deploying.

---

Built by Aradhya Stuti — final year B.Tech project.
