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
- **Umang** — legal rights. FIR filing, RTI, consumer complaints, tenant rights, divorce — always cited from actual laws and sections.
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

One thing that took a while: getting the intent classifier to correctly handle Hinglish. A lot of edge cases — someone writing `"RTI kaise file karein"` would get misrouted because the classifier saw Hindi words and defaulted to Mental Health. Adding explicit Hinglish examples and keyword guidance to the prompt fixed most of it.

---

## Other features

- **RAG pipeline**: `multilingual-e5-small` embeddings → FAISS vector search (overfetch 15) → cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`). Confidence shown per-response (High / Medium / Low / None). OCR artifact cleanup before embedding lookup. Domain-aware staleness penalties (schemes: 2/6 month thresholds; statutes: 6/18 months).
- **Scheme eligibility checker**: rule-based, not LLM. I tried LLMs for eligibility and they were too vague. The deterministic checker takes state, age, income, and category and returns exactly which schemes match.
- **Legal document templates**: RTI, consumer complaint, rent notice — filled from form inputs, not AI-generated. Keeps them legally consistent.
- **Automatic intent routing**: ask a legal question in the mental health tab and the agent detects it and reroutes. The UI shows the reasoning.
- Mood tracker, breathing companion, session summaries, saved moments, conversation export, offline detection, error boundary.
- **Auth**: JWT with JTI blacklisting on logout, bcrypt (12 rounds), timing-attack-resistant login. Account deletion wipes all messages, summaries, memory, and goals.

---

## Tech stack

| Layer         | What I used                                                                      |
| ------------- | -------------------------------------------------------------------------------- |
| Frontend      | React 18, Vite, Tailwind CSS, shadcn/ui, Radix UI                                |
| Backend       | Python 3.10, FastAPI, LangGraph                                                  |
| LLMs          | Groq API — Llama 3.3 70B (responses), Llama 3.1 8B (intent/emotion/goal/memory) |
| Embeddings    | `intfloat/multilingual-e5-small`                                                 |
| Vector search | FAISS (CPU)                                                                      |
| Reranker      | `cross-encoder/ms-marco-MiniLM-L-6-v2`                                          |
| Database      | MongoDB Atlas (Motor async driver)                                               |
| Auth          | PyJWT + bcrypt                                                                   |
| Rate limiting | slowapi                                                                          |
| Web search    | DuckDuckGo + Wikipedia + Brave Search (concurrent, with retry backoff)           |
| Deployment    | Docker, Hugging Face Spaces                                                      |

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

First startup downloads the embedding model (`multilingual-e5-small`) — takes 1–2 minutes. Subsequent starts load from cache and are instant.

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
