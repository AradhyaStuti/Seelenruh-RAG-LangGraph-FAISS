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

Seelenruh is a student-built assistant for Indian users who need help with mental health support, legal rights, government schemes, and safety information. The project combines a React/Vite frontend with a FastAPI backend, a LangGraph orchestration layer, and a retrieval pipeline built around FAISS and BM25.

Live demo: [Hugging Face Spaces](https://huggingface.co/spaces/aradhyastuti/seelenruh)

## Project overview

The app routes user messages to one of four personas:

- Usha for mental health and emotional support.
- Umang for legal guidance and rights-based advice.
- Aarogya for government schemes and entitlements.
- Raksha for safety and emergency-style support.

The system can retrieve relevant knowledge from a local corpus, trigger web search when confidence is low, and keep short conversation memory across turns.

## Features

- Persona-based assistance for mental health, legal, schemes, and safety topics.
- Hybrid retrieval using FAISS and BM25, followed by reranking.
- Rule-based eligibility checks for selected scheme workflows.
- Conversation memory, goal tracking, and saved moments in the UI.
- Multi-language handling for English, Hindi, Hinglish, and German.
- Admin endpoints for inspecting or updating retrieval knowledge.

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

The repository is split into a frontend and a backend service:

- The frontend lives in the client folder and provides the chat UI, session flows, and saved-history views.
- The backend lives in the server folder and contains the FastAPI app, routing logic, LangGraph graph definitions, and retrieval modules.
- The retrieval stack is built around vector search plus sparse retrieval, with domain-aware scoring and a few quality checks before replies are returned to the user.

## Installation

The project can be installed from the repository root:

```bash
npm run install:all
```

After installation, create a local environment file for the server:

```bash
cp .env.example server/.env
```

Fill in the required values for the API keys, JWT secret, and MongoDB connection string before running the app.

## Usage

Start the backend and frontend together:

```bash
npm run dev
```

The backend runs from the server folder and the frontend is served by Vite. The default local URLs are usually http://localhost:5000 for the API and http://localhost:5173 for the client.

## Evaluation

The repository includes a small evaluation harness and a functional test suite:

```bash
cd server
./.venv/Scripts/python -m pytest tests/test_functional_cases.py -q
```

The evaluation scripts under the evaluation folder and the top-level evaluate.py file are used for offline checks around routing, response quality, retrieval behaviour, and latency.

## Deployment

The app can be run with Docker, and the repository also includes configuration for Hugging Face Spaces deployment.

## Limitations

- Some answers depend on the availability of external providers and on the freshness of the underlying knowledge base.
- This is not a substitute for professional legal or medical advice.
- The retrieval layer is useful, but it can still miss edge cases or produce incomplete guidance in unusual cases.

## Future work

Possible improvements include broader evaluation coverage, better source verification, and more consistent handling of edge cases across personas.
