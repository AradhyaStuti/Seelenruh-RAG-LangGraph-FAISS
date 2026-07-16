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

I noticed that a lot of people around me — friends, family — would hit a wall whenever they needed information about things like their tenant rights, or which government schemes they might be eligible for, or just someone to talk to when they were struggling. The information exists, but it's scattered, often in legalese, and not accessible to people who speak Hindi or Hinglish rather than formal English.

So I decided to build something that routes questions to the right "persona" and pulls from a curated knowledge base rather than making things up. The name Seelenruh is German for "peace of mind", which felt right for what I was going for.

## What it does

The app routes user messages to one of four personas:

- **Usha** for mental health and emotional support.
- **Umang** for legal guidance and rights-based advice.
- **Aarogya** for government schemes and entitlements.
- **Raksha** for safety and emergency-style support.

It can retrieve relevant knowledge from a local corpus, fall back to web search when confidence is low, and keep memory across turns within a session.

## Features

- Persona-based assistance for mental health, legal, schemes, and safety topics.
- Hybrid retrieval using FAISS and BM25, with cross-encoder reranking.
- Rule-based eligibility checks for selected scheme workflows.
- Conversation memory, goal tracking, and saved moments in the UI.
- Multi-language support for English, Hindi, Hinglish, and German.
- Admin endpoints for inspecting or updating the knowledge base.

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Radix UI |
| Backend | Python 3.10, FastAPI, LangGraph |
| LLM providers | Groq, Ollama, Anthropic |
| Embeddings | intfloat/multilingual-e5-small |
| Retrieval | FAISS + BM25 + reranker |
| Database | MongoDB Atlas |
| Auth | PyJWT + bcrypt |
| Deployment | Docker, Hugging Face Spaces |

## Architecture

The project is split into a frontend and a backend:

- The frontend lives in `client/` and handles the chat UI, session history, and saved views.
- The backend lives in `server/` and contains the FastAPI app, the LangGraph workflow, and the retrieval modules.
- The retrieval pipeline combines vector search (FAISS) with sparse retrieval (BM25), merges the results using reciprocal rank fusion, and reranks the candidates with a cross-encoder before passing them to the LLM.

One thing I spent a lot of time on was making sure the system doesn't just make things up when it doesn't know something. The knowledge base is curated, and there are guardrails that check for hallucinated section numbers, overpromising language, and foreign law bleed-in (German law leaking into what's supposed to be Indian legal advice was a real problem early on).

## Installation

```bash
npm run install:all
```

Then set up the server's environment file:

```bash
cp .env.example server/.env
```

Fill in the API keys, JWT secret, and MongoDB connection string before running anything.

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

The evaluation scripts under `evaluation/` and the top-level `evaluate.py` are for offline checks on routing accuracy, response quality, retrieval behaviour, and latency. I ran these regularly while building to catch regressions.

## Deployment

The app runs in Docker, and the repo includes config for Hugging Face Spaces deployment (the frontmatter at the top of this file).

## Challenges

A few things that were harder than I expected:

- **Multilingual retrieval** — making BM25 and FAISS both work well for Hinglish queries required a lot of manual query expansion. I ended up building a token-level Hinglish-to-English map and a phrase-level one on top of it.
- **Hallucination** — LLMs will confidently cite IPC Section 600 (which doesn't exist). I built pattern-based guardrails that check section numbers against known ranges and flag anything suspicious before the response goes out.
- **Persona voice** — getting the legal persona (Umang) to sound like a knowledgeable advisor rather than a disclaimer machine, while still being accurate, took a lot of prompt iteration.
- **Streaming + memory** — combining SSE streaming with background memory saves without blocking the main response path was tricky to get right.

## Known issues

- Response quality depends on which LLM provider is available. Groq is the default; Ollama and Anthropic are fallbacks. If all three are down, it fails.
- The retrieval layer occasionally misses edge cases — especially for very specific scheme eligibility questions or obscure legal provisions.
- The evaluation scripts give a good signal but aren't a substitute for real user testing.
- This is not a substitute for professional legal or medical advice, and the app says so explicitly.

## Future work

- Better test coverage, especially for multi-turn conversations.
- More consistent handling of state-specific legal variations (rent control, stamp duty, etc.).
- Possibly a voice interface — there's a TTS endpoint already, but no polished UI for it.
- Broader scheme coverage beyond the central government schemes currently in the knowledge base.

## Acknowledgements

This project wouldn't have gotten very far without LangGraph, FAISS, sentence-transformers, FastAPI, and the shadcn/ui component library. These covered enough infrastructure that I could spend most of my time on the parts that were specific to this problem — the routing logic, retrieval tuning, and multilingual handling — rather than rebuilding generic plumbing.
