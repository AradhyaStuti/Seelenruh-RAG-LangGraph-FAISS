# Seelenruh — Project Diagrams

All diagrams are interactive HTML files. Open any `.html` file directly in a browser — no server required.

## How to use

1. Open any diagram file in Chrome / Firefox / Edge
2. Click **Print / Export PDF** to save a high-quality PDF copy
3. Diagrams are self-contained — no external dependencies, no internet required

---

## Diagram Index

### Architecture

| File | Description |
|------|-------------|
| [architecture.html](diagrams/architecture.html) | Architecture overview — technology choices and design decisions explained |
| [system_architecture.html](diagrams/system_architecture.html) | Full system architecture — all layers from client to storage |
| [detailed_architecture.html](diagrams/detailed_architecture.html) | Detailed architecture — every module annotated with internal details |
| [deployment.html](diagrams/deployment.html) | Deployment — Docker container, Nginx proxy, HF Spaces, external APIs |
| [component.html](diagrams/component.html) | Component diagram — UML-style module interfaces and dependencies |
| [package.html](diagrams/package.html) | Package diagram — import dependency graph between all Python packages |
| [folder_structure.html](diagrams/folder_structure.html) | Annotated folder tree of the entire codebase |

### Data Flow

| File | Description |
|------|-------------|
| [dfd_level0.html](diagrams/dfd_level0.html) | DFD Level 0 (Context) — entire system as one process, external actors |
| [dfd_level1.html](diagrams/dfd_level1.html) | DFD Level 1 — 5 major sub-processes and their data stores |
| [flowchart.html](diagrams/flowchart.html) | End-to-end request flowchart — every decision point from query to SSE |
| [control_flow.html](diagrams/control_flow.html) | Control flow — LangGraph node execution with branches and async notes |

### AI & RAG

| File | Description |
|------|-------------|
| [ai_pipeline.html](diagrams/ai_pipeline.html) | AI pipeline — all AI components staged from input to streamed output |
| [langgraph_workflow.html](diagrams/langgraph_workflow.html) | LangGraph workflow — node-by-node state transitions with ChatState keys |
| [rag_pipeline.html](diagrams/rag_pipeline.html) | RAG pipeline — FAISS + BM25 → RRF → cross-encoder reranker |
| [retrieval_viz.html](diagrams/retrieval_viz.html) | Retrieval visualization — how chunks and confidence reach the ExplainabilityPanel |
| [persona_routing.html](diagrams/persona_routing.html) | Persona routing — query classification into Usha / Umang / Aarogya / Raksha |

### Sequence & Interaction

| File | Description |
|------|-------------|
| [sequence.html](diagrams/sequence.html) | Sequence diagram — browser ↔ FastAPI ↔ LangGraph ↔ RAG ↔ LLM ↔ MongoDB |
| [activity.html](diagrams/activity.html) | Activity diagram — admin knowledge management workflow (add/delete/rollback) |

### Auth & Security

| File | Description |
|------|-------------|
| [auth_flow.html](diagrams/auth_flow.html) | Authentication flow — register, login, refresh, logout, JTI blacklist |
| [error_handling.html](diagrams/error_handling.html) | Error handling — circuit breaker, LLM fallback chain, validation errors, logging |

### Feedback & Knowledge

| File | Description |
|------|-------------|
| [feedback_workflow.html](diagrams/feedback_workflow.html) | Feedback learning — thumbs vote → feedback_logs → admin analytics |
| [knowledge_gap.html](diagrams/knowledge_gap.html) | Knowledge gap detection — low-confidence queries → web search → admin review |

### UML Diagrams

| File | Description |
|------|-------------|
| [class.html](diagrams/class.html) | Class diagram — VectorStore, CircuitBreaker, ChatState, LLMProvider, Pydantic models |
| [use_case.html](diagrams/use_case.html) | Use case diagram — Guest, Registered User, and Admin actor use cases |
| [state.html](diagrams/state.html) | State diagram — user session states and ChatState inference machine |
| [api_flow.html](diagrams/api_flow.html) | API flow — all 8 FastAPI routers with routes, auth levels, response types |

---

## Key Design Decisions Illustrated

- **Hybrid RAG** (rag_pipeline.html): FAISS dense + BM25 sparse → RRF fusion → cross-encoder. Dense alone misses exact keyword matches; BM25 catches those; RRF merges without threshold tuning.

- **LangGraph sub-graphs** (langgraph_workflow.html): each persona (Usha/Umang/Aarogya/Raksha) is an independent compiled graph. Adding a 5th persona is one new file.

- **Rule-based eligibility checker** (persona_routing.html): LLM hallucinated income thresholds during testing; deterministic rules are verifiable.

- **Circuit breaker per LLM provider** (error_handling.html): if Groq rate-limits, falls to Ollama, then Anthropic — no single point of LLM failure.

- **SSE over WebSockets** (sequence.html): simpler server (no connection state), works through CDN/proxy, browser EventSource handles reconnect automatically.

- **JTI blacklist for logout** (auth_flow.html): explicit revocation on logout — no need to wait for token expiry.
