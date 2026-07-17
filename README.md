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
- Cross-session memory — the system remembers context within a session.
- Goal tracking — detects what you're trying to accomplish and tracks it across turns.
- Session history per persona — browse and restore past conversations.
- Copy, save (bookmark), and thumbs up/down feedback on any response.
- Export conversation as a text file.
- Attach a document (.txt, .md, .pdf, .docx, .csv) to provide as context for your next message.

### Retrieval
- Hybrid retrieval: FAISS vector search + BM25 keyword search combined with reciprocal rank fusion.
- Cross-encoder reranking before the final response.
- Confidence scoring (High / Medium / Low / None) shown per response.
- Source citations with authority badges — Authoritative, Official, Institutional.
- Automatic web search fallback when knowledge base confidence is low.
- Hallucination guardrails: section number range checks, foreign law detection, overpromising language flags.

### Persona-specific tools

**Usha (Mental Health)**
- Mood check-in button in the toolbar. Pick from five moods (Joyful, Calm, Tired, Anxious, Sad); shows an affirmation and a practical tip. Mood history tracked over 14 days with a streak counter. Mood context only influences Usha — it does not leak into other personas.
- Breathing companion: three guided patterns (Calm 4-6, Box 4-4-4-4, 4-7-8) with animated visual guidance. Accessible from the header.

**Umang (Legal)**
- Embedded legal timelines for salary recovery, eviction, consumer complaints, and divorce — shows steps, typical duration, documents needed, and approximate costs.

**Aarogya (Government Schemes)**
- Eligibility checker tool: fill in state, age, income, student/farmer status and get matched schemes instantly without hitting the LLM. Lazy-loaded, opens as a modal from the chat toolbar.

**Raksha (Safety)**
- Emergency contacts bar (Police 100, Fire 101, Ambulance 102, Women's helpline 1091) appears automatically when emergency language is detected.

### Language
- English, Hindi, Hinglish, and German supported.
- Language toggle in the header; the selected language is sent to the backend and the persona responds accordingly.
- When chatting in German, a translate button appears on each assistant response — click to see an English translation inline, click again to hide.

### Account
- Email/password signup and login with email verification.
- Forgot password and reset password flow via email token.
- Change password from the account menu (Ctrl+Shift+Q opens sign out).
- Sign out with optional local data wipe.
- Account deletion with confirmation.

### Saved moments
- Bookmark any response with the heart icon.
- View all saved responses in the Saved drawer from the header.
- Copy or delete saved entries.

### Explainability
- Every response shows a "Why?" panel that visualises the RAG pipeline: Embed → FAISS → BM25 → RRF → Rerank → LLM.
- Routing trace shows which domain was selected and why.
- Source panel shows which knowledge chunks were retrieved and cited.

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Radix UI, shadcn/ui |
| Backend | Python 3.10, FastAPI, LangGraph |
| LLM providers | Groq (primary), Anthropic, Ollama (fallbacks) |
| Embeddings | intfloat/multilingual-e5-small |
| Retrieval | FAISS + BM25 + cross-encoder reranker |
| Database | MongoDB Atlas |
| Auth | PyJWT + bcrypt |
| TTS | ElevenLabs (primary), gTTS (fallback) |
| STT | Groq Whisper |
| Deployment | Docker, Hugging Face Spaces |

## Architecture

The project splits into a frontend and a backend:

- The frontend lives in `client/` and handles the chat UI, session history, saved moments, mood tracking, and breathing exercises.
- The backend lives in `server/` and contains the FastAPI app, the LangGraph workflow, and the retrieval modules.
- The LangGraph graph runs six nodes per request: load_memory → classify → route → retrieve → maybe_search → generate → save_memory.
- The retrieval pipeline combines vector search (FAISS) with sparse retrieval (BM25), merges the results using reciprocal rank fusion, and reranks the candidates with a cross-encoder before passing them to the LLM.
- Each domain has its own sub-graph (usha_graph, legal_graph, aarogya_graph, raksha_graph) that handles domain-specific reasoning and output formatting.

One thing I spent a lot of time on was making sure the system doesn't make things up when it doesn't know something. The knowledge base is curated, and there are guardrails that check for hallucinated section numbers, overpromising language, and foreign law bleed-in (German law leaking into what's supposed to be Indian legal advice was a real problem early on).

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
| `JWT_SECRET` | Yes | Secret for signing JWTs |
| `MONGODB_URI` | Yes | MongoDB Atlas connection string |
| `ANTHROPIC_API_KEY` | No | Fallback LLM provider |
| `OLLAMA_URL` | No | Local Ollama instance URL |
| `ELEVENLABS_KEY` | No | TTS provider (gTTS used if absent) |

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

The evaluation scripts under `evaluation/` and the top-level `evaluate.py` are for offline checks on routing accuracy, response quality, retrieval behaviour, and latency.

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

## Known issues

- Response quality depends on which LLM provider is available. Groq is the default; Anthropic and Ollama are fallbacks. If all three are down, it fails.
- The retrieval layer occasionally misses edge cases — especially for very specific scheme eligibility questions or obscure legal provisions.
- Email sending (verification, password reset) requires SMTP credentials which aren't set up in the demo deployment.
- This is not a substitute for professional legal or medical advice, and the app says so explicitly.

## Future work

- Voice interface — TTS and Whisper STT are already wired into the backend, but there's no polished mic UI in the frontend yet.
- Better test coverage, especially for multi-turn conversations.
- More consistent handling of state-specific legal variations (rent control, stamp duty, etc.).
- Broader scheme coverage beyond the central government schemes currently in the knowledge base.

## Acknowledgements

This project wouldn't have gotten very far without LangGraph, FAISS, sentence-transformers, FastAPI, and the shadcn/ui component library. These covered enough infrastructure that I could spend most of my time on the parts that were specific to this problem — the routing logic, retrieval tuning, and multilingual handling — rather than rebuilding generic plumbing.
