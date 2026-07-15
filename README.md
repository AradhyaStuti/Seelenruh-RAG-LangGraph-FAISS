---
title: Seelenruh
emoji: 🌸
colorFrom: pink
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---
# Seelenruh — A LangGraph-Powered Agentic RAG System for Multi-Domain Civic and Mental Health Support

Live demo: [Hugging Face Spaces](https://huggingface.co/spaces/aradhyastuti/seelenruh)

---

I built this as my final year B.Tech project. The name means "peace of the soul" in German — which felt right for what I was trying to make.

The problem I kept coming back to: most people in India don't know what government schemes they're actually entitled to, don't know their legal rights when something goes wrong, and have very limited access to mental health support. I wanted to build one app that addresses all three, plus safety in emergencies — and do it in a way that works for Indian users, including people who write in Hindi or Hinglish.

What started as a simple RAG chatbot turned into something more interesting once I started working with LangGraph. The agentic features — persistent memory, goal tracking, autonomous web search — weren't in the original plan. They came out of noticing real gaps in how the assistant behaved during testing.

---

## The four assistants

**Usha** — mental health and emotional support. Designed to feel like talking to a calm, older friend, not a clinical chatbot. No bullet-point lists, no "your feelings are valid" every message. Replies mirror the user's language and register — Hinglish stays Hinglish, Devanagari stays Devanagari.

**Umang** — Indian legal rights. Covers criminal law (BNS/BNSS/BSA 2023, the new codes that replaced IPC/CrPC from July 2024), civil rights, family law, consumer protection, labour law (including the four Labour Codes 2020), property/tenant rights, cybercrime, RTI, and more. Every response is structured, cites specific acts and section numbers, distinguishes civil from criminal remedies, and never recommends a police complaint where a Labour Commissioner or consumer forum is the correct first step.

**Aarogya** — government schemes and entitlements. PM-JAY, PM-KISAN, MGNREGA, scholarships, ration cards, Mudra loans, eShram, and state-level schemes for Delhi, Gujarat, Rajasthan, Bihar, Punjab, Kerala, Himachal Pradesh, and Goa. Includes a rule-based eligibility checker (more on why I chose rule-based over LLM below) that matches the user's state, age, income, and category against scheme criteria.

**Raksha** — safety and emergencies. Domestic violence (immediate danger → safety plan; legal procedure → Umang), cybercrime, stalking, online fraud. Active emergencies get the Step 1/2/3 format with helpline numbers upfront; post-incident queries get acknowledgment then concrete reporting steps.

---

## Why LangGraph — and what makes it agentic

I initially used a simple chain: query → retrieve → generate. That worked for basic factual questions but fell apart quickly. The LLM had no memory, couldn't decide when to search the web, and had no idea if the user was working toward a longer-term goal.

Switching to LangGraph let me build a graph where the agent controls its own flow:

```
START → load_memory → classify → route → retrieve → maybe_search → generate → save_memory → END
```

Three things make this genuinely agentic rather than just a chatbot with a knowledge base:

**1. Autonomous web search**
I added a web search step that only runs when the bot doesn't have a confident answer from its own knowledge. It triggers on real-time signals (`latest`, `current`, `2025`, helpline numbers, `abhi`, `naya`…), when RAG returns too few or low-confidence results, or always for Legal and Government Schemes domains where outdated information is especially harmful. DuckDuckGo, Wikipedia, and optionally Brave Search run concurrently with retry backoff.

**2. Self-evolving memory**
After every response, a background task compresses the conversation into a 2–3 sentence summary and extends an emotion arc (`neutral → anxious → calm → …`). Both go into MongoDB. Next turn, `load_memory` fetches them and injects them into the system prompt as a `CONVERSATION CONTEXT` block — in the system prompt, not mixed into the user message, which is the correct placement.

**3. Goal tracking**
Every turn, `detect_goal` runs in parallel with intent and emotion detection. If it finds something actionable — `"file an RTI"`, `"apply for PM-JAY"`, `"find a therapist"` — it stores that goal and surfaces it on every subsequent turn. A live goal badge appears in the UI so the user can see what the agent is tracking.

---

## Umang's legal pipeline

Umang uses a dedicated 3-node LangGraph sub-graph. Each node is a specialised agent; the 70B model only runs once (compose step), keeping latency acceptable on free-tier Groq.

```
query
  │
  ▼  Agent 1 — Case Analyzer (llama-3.1-8b-instant)
  │  Structured JSON output:
  │    category (25 options), issue_type, urgency, employment_type,
  │    property_type, known_facts, missing_facts, follow_up,
  │    limitation_concern, personal_law, jurisdiction
  │
  ▼  Agents 2–6 — Preparation (Python, no LLM call)
  │  Organise RAG chunks by type (rights / procedure / general)
  │  Build deterministic legal reasoning context from _LEGAL_KNOWLEDGE
  │  Detect jurisdiction from query text
  │  Load document template if needed (RTI, consumer complaint, etc.)
  │
  ▼  Agent 7 — Response Composer (llama-3.3-70b-versatile)
  │  System prompt assembled from 7 modular components (see below)
  │  Synthesises one structured response
  │
  ▼  Post-response quality gates (Python, no LLM call)
     Hallucination guardrails + quality checker (see below)
```

### Case Analyzer — 25 legal categories

```
DomesticViolence | Divorce | Maintenance | FIR | Consumer | RTI | Tenant
Employment | Property | Cybercrime | POSH | ChequeBounce | Bail | POCSO
Constitutional | Criminal | Contract | Inheritance | MedicalNegligence
LabourCodes | DPDP | MotorVehicles | ChildCustody | RTE | General
```

Additional schema fields added to guide tailored responses:
- `issue_type` — Civil | Criminal | Family | Consumer | Employment | Property | Cyber | Administrative | Constitutional | Mixed
- `employment_type` — private_employee | government_employee | gig_worker | domestic_worker | intern | apprentice | factory_worker
- `property_type` — rented_residential | pg_hostel | commercial_lease | agricultural | owned_property

These fields determine which legal framework applies (ID Act for private workmen vs. service rules for government employees vs. Code on Social Security for gig workers, etc.).

### Deterministic legal knowledge — `_LEGAL_KNOWLEDGE`

24 categories have a deterministic knowledge dict that is always injected regardless of RAG confidence. Each entry has:

| Field | Contents |
|-------|----------|
| `applicable_laws` | Exact act names + what each covers |
| `dispute_classification` | Labour vs. civil vs. criminal vs. administrative |
| `typical_remedies` | What the user can actually get |
| `evidence_checklist` | Specific documents to preserve |
| `procedure_steps` | Step-by-step correct escalation path |
| `limitation_period` | Filing deadlines (critical — missing these kills the case) |
| `authorities` | Which forum handles which sub-type |
| `typical_timeline` | Realistic expectations |
| `typical_costs` | Filing fees + lawyer estimate |
| `common_mistakes` | What people do wrong |
| `free_legal_aid` | NALSA / DLSA options |

This means Umang always knows the correct escalation order before RAG results even arrive. It also means retrieval failures don't produce empty or hallucinated guidance.

### FIR guard — three layers

The single most common mistake in Indian legal chatbots is recommending a police complaint for salary disputes, rent disputes, or warranty claims. These are civil/labour matters; police cannot recover wages.

Three independent layers block this:

1. **Case Analyzer** classifies `Employment` salary queries as `issue_type: "Employment"` by default, not `"Criminal"`. The `dispute_classification` field explicitly distinguishes labour disputes from criminal offences.
2. **`_LEGAL_KNOWLEDGE["Employment"]`** has a `WARNING` key: "DO NOT recommend FIR merely because salary is unpaid" — directly in the reasoning context the composer reads.
3. **Quality checker** (`quality_checker.py`) pattern-matches the response for "FIR…salary" and "FIR…wages" and flags it as a warning.

The correct escalation order for unpaid wages: written demand → Labour Commissioner (free) → legal notice → Labour Court → FIR **only if fraud/PF misappropriation/forgery**.

### Response format — 9 sections

Every substantive Umang response uses this structure (defined in `response_template.py`, injected into the composer system prompt):

```
## Summary           — 1–2 sentences, hedged language ("you may have the right to...")
## Issue Type        — Civil | Criminal | Employment | etc. + sub-type
## Applicable Law    — specific Act + Section + one sentence on what it says
## Your Rights       — numbered list, concrete entitlements
## What You Can Do   — numbered step-by-step, most accessible/free option first
## Documents Needed  — specific evidence checklist including non-obvious items
## When to Contact Police   — only if cognizable offence present; omitted for civil matters
## When to Contact a Lawyer — trigger conditions; always mentions DLSA/15100 first
## Important Notes   — caveats, state-specific variations, limitation periods
```

### BNS/BNSS/BSA 2023 — new Indian criminal codes

From July 2024, India replaced:
- IPC 1860 → Bharatiya Nyaya Sanhita (BNS) 2023
- CrPC 1973 → Bharatiya Nagarik Suraksha Sanhita (BNSS) 2023
- Evidence Act 1872 → Bharatiya Sakshya Adhiniyam (BSA) 2023

Umang always cites the new code first for post-July-2024 matters: `"BNS Section 85 (formerly IPC 498A)"`. The `_LEGAL_KNOWLEDGE` dicts use the new section numbers throughout, and the hallucination guardrails know the correct section range for each code.

### Modular prompt architecture — token budget

The previous monolithic persona string grew to ~19,000 chars (~4,800 tokens) across iterations and started hitting Groq's 12,000 TPM limit. That was the point where I had to refactor. The system prompt is now assembled from separate modules:

| Component | Module | ~Tokens |
|-----------|--------|---------|
| Persona (10 core rules) | `responder.py → PERSONA["Legal"]` | ~730 |
| Language instruction | `language_engine.py → build_language_instruction()` | ~100 |
| Response format | `response_template.py → RESPONSE_TEMPLATE_DESCRIPTION` | ~350 |
| Few-shot example (1 relevant) | `few_shot_examples.py → get_few_shot_examples()` | ~400–600 |
| Case analysis block | `legal_agents.py` internal | ~100 |
| Legal reasoning context | `_LEGAL_KNOWLEDGE` dict for category | ~400 |
| Retrieved knowledge (top 5 chunks) | FAISS + BM25 hybrid | ~1,000 |
| Source format prompt | `responder.py → SOURCES_SECTION_PROMPT` | ~80 |
| **Total** | | **~3,160–3,360 tokens** |

Each component is independently editable and testable. Changing the response format means editing one file (`response_template.py`), not hunting through a 19,000-char string.

### Post-response quality gates

After every LLM response, two validators run before the text reaches the user:

**Hallucination guardrails** (`hallucination_guardrails.py`):
- Maintains `KNOWN_ACTS` — a whitelist of 39 Indian statutes with valid section ranges (e.g., IPC max section: 511, BNS max: 358, Consumer Protection Act max: 107)
- Scans citations in the response; if a section number exceeds the known maximum, appends a verification note rather than silently passing

**Quality checker** (`quality_checker.py`):
- Detects overpromise language: "you will definitely win", "guaranteed", "you will receive"
- Detects German law bleed-in: "BGB", "Arbeitsrecht", "deutsches Recht"
- Detects FIR misuse for employment/salary disputes
- Detects unverified toll-free helpline numbers not in the approved list
- Errors append a disclaimer; warnings are logged for review

---

## RAG pipeline — hybrid retrieval

```
query
  │
  ▼  _normalize_query()
  │  Hinglish → English (80+ term map), OCR artifact cleanup
  │
  ▼  _expand_legal_query()  [Legal domain only]
  │  37+ regex patterns append domain-specific terminology
  │  e.g. "salary nahi mili" → + "Code on Wages 2019 Labour Commissioner unpaid salary..."
  │
  ├──────────────────────────────────────┐
  │                                      │
  ▼                                      ▼
  FAISS dense retrieval           BM25 sparse retrieval
  (multilingual-e5-small)         (rank-bm25, graceful fallback)
  up to 25 candidates             up to 25 candidates
  │                                      │
  └──────────────────┬───────────────────┘
                     │
                     ▼  _rrf_fuse()
                     │  Reciprocal Rank Fusion  score = Σ 1/(60 + rank)
                     │
                     ▼  cross-encoder reranker
                     │  ms-marco-MiniLM-L-6-v2
                     │
                     ▼  _dedup()
                     │  Remove near-duplicates by topic
                     │
                     ▼  top-5 chunks returned
```

**Why BM25 alongside FAISS**: Dense semantic retrieval misses exact matches. A query like `"Section 138 NI Act"` may not rank highly in embedding space because the embedding conflates `"138"` with numeric context. BM25 nails exact term matches. RRF fusion combines both signals without any score normalisation pain.

**BM25 graceful fallback**: If `rank-bm25` is not installed, the pipeline silently falls back to FAISS-only. No code changes needed.

**Domain-aware confidence thresholds** (from `knowledge_meta.py`):
- Legal: High ≥ 0.80, Medium ≥ 0.60, Low < 0.60
- Other domains: High ≥ 0.75, Medium ≥ 0.55
- Confidence is shown per-response and affects how cautiously the composer words its answer

**Domain-aware staleness penalties**:
- Government scheme chunks: expire at 2 months (soft) / 6 months (hard) — budget allocations change every year
- Legal statutes: expire at 6 months (soft) / 18 months (hard) — acts change rarely
- Recent chunks get a staleness bonus so newer guidance is preferred when scores are similar

**Overfetch multipliers** (before cross-encoder):
- Legal: 25 candidates (dense chunks, exact wording matters)
- Government Schemes: 20 candidates
- Other: 15 candidates

---

## Multilingual support

Language is detected heuristically at request time — no extra LLM call:

1. Devanagari unicode block (U+0900–U+097F) → Hindi (`hi`)
2. German-specific characters (ä, ö, ü, ß) or ≥1 German marker words → German (`de`)
3. ≥2 Hinglish marker words (mujhe, kya, chahiye, nahi, vakeel…) → Hinglish (`hi-roman`)
4. Fallback → English (`en`)

Each detected language gets a different instruction string injected into the system prompt:

| Language | Style |
|----------|-------|
| English | Plain professional; explain legal terms inline |
| Devanagari Hindi | Natural modern Hindi; no archaic bureaucratic phrasing; legal terms stay English |
| Hinglish (Roman) | Conversational mix; `"Labour Commissioner ke paas jaao"` not `"invoke the appropriate remedy"` |
| German | Clear B2-level German; **always Indian law**; Indian terms translated in parentheses — `"FIR (Strafanzeige bei der indischen Polizei)"`, `"NALSA (Indiens kostenloser Rechtshilfedienst)"` — never German courts or agencies |

The 10 few-shot examples include a Hinglish wrongful-termination example and a German tenant-rights example (Indian rent law, not German Mietrecht) to anchor the model's output style.

---

## Hinglish map and legal query expansion

**Hinglish map** — 80+ Roman-script Hindi and mixed terms expanded before embedding:
- `"tankhwaah"` → `"salary wages"` | `"f&f"` → `"full and final settlement dues payable"`
- `"kirayedaar"` → `"tenant renter"` | `"vakeel"` → `"lawyer"` | `"talaq"` → `"divorce Muslim"`
- `"bima"` → `"insurance claim"` | `"durghatna"` → `"accident motor vehicle"`
- `"company bhaag gayi"` → `"employer absconded company closed wages unpaid"`

**Legal query expansion** — 37+ regex patterns fire on vague natural-language queries to append technical terminology that maps onto knowledge chunks:
- Salary withheld → `+ "Code on Wages 2019 Payment of Wages Act unpaid salary labour commissioner complaint..."`
- Wrongful termination → `+ "Industrial Disputes Act 1947 Industrial Relations Code 2020 wrongful termination retrenchment workman reinstatement..."`
- Data breach → `+ "Digital Personal Data Protection Act 2023 DPDP Act Data Protection Board Data Fiduciary consent..."`

---

## Other features

- **Scheme eligibility checker** — rule-based, not LLM. I first tried using the LLM for eligibility checks but it was too vague and sometimes just wrong — it would hedge or hallucinate income thresholds. Switching to deterministic rules (state, age, income, category matched against fixed criteria) made the checker much more reliable. Returns only schemes the user actually qualifies for, with application steps.
- **Legal document templates** — RTI application, consumer complaint, rent demand notice, legal notice for cheque bounce, affidavit. Filled from form inputs, not AI-generated. Keeping documents template-based rather than LLM-generated means clause numbers stay accurate and consistent.
- **Automatic intent routing** — ask a legal question in the mental health tab and the agent detects it and suggests switching. The UI shows the routing reason.
- **Mood tracker** — tracks emotional arc across the session; shown in the Usha tab.
- **Breathing companion** — animated guide for panic/anxiety moments; accessible from Raksha and Usha. Three scientifically validated patterns: Calm 4-6 (extended exhale activates the parasympathetic nervous system), Box 4-4-4-4 (used in clinical stress-regulation research and by the US military), and 4-7-8 (developed by Dr. Andrew Weil from pranayama; peer-reviewed for sleep onset and cortisol reduction). All three work by slowing breathing to ~5–6 breaths/min, which improves heart rate variability (HRV) and stimulates the vagus nerve.
- **Session summaries** — auto-generated 2–3 sentence memory after each conversation.
- **Saved moments** — users can pin specific responses to revisit.
- **Conversation export** — full session downloadable as text.
- **Auth** — JWT with JTI blacklisting on logout, bcrypt (12 rounds), timing-attack-resistant login. Account deletion wipes all messages, summaries, memory, and goals from MongoDB.
- **Offline detection** — UI shows a banner if the connection drops; queues the message and retries.
- **Rate limiting** — `slowapi` per-endpoint limits prevent abuse.

---

## Tech stack

| Layer | What I used |
|-------|-------------|
| Frontend | React 18, Vite, Tailwind CSS, shadcn/ui, Radix UI |
| Backend | Python 3.10, FastAPI, LangGraph |
| LLMs | Groq API — Llama 3.3 70B (response composer), Llama 3.1 8B (case analyzer, intent, emotion, goal, memory) |
| Embeddings | `intfloat/multilingual-e5-small` (384-dim, 90+ languages) |
| Vector search | FAISS (CPU) + BM25 sparse (rank-bm25) — Reciprocal Rank Fusion |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Database | MongoDB Atlas (Motor async driver) |
| Auth | PyJWT + bcrypt |
| Rate limiting | slowapi |
| Web search | DuckDuckGo + Wikipedia + Brave Search (concurrent, with retry backoff) |
| LLM fallback chain | Groq → Ollama (local) → Anthropic (cloud) |
| Deployment | Docker, Hugging Face Spaces |

---

## Project structure

```
server/
├── ai/
│   ├── legal_agents.py               # 7-agent pipeline + _LEGAL_KNOWLEDGE (24 categories)
│   ├── hallucination_guardrails.py   # 39-act KNOWN_ACTS whitelist, section range validation
│   ├── language_engine.py            # Heuristic language detection (en/hi/hi-roman/de)
│   ├── quality_checker.py            # Post-response pattern validation (overpromise, FIR misuse, etc.)
│   ├── few_shot_examples.py          # 10 curated Q&A examples for system prompt injection
│   ├── response_template.py          # 9-section response format (RESPONSE_TEMPLATE_DESCRIPTION)
│   └── responder.py                  # Persona definitions + non-Legal response pipeline
├── rag/
│   ├── retriever.py                  # FAISS + BM25 hybrid retrieval, RRF fusion, Hinglish map
│   ├── knowledge_meta.py             # Domain-aware confidence scoring + staleness penalties
│   ├── store.py                      # FAISS vector store with soft-delete + compaction
│   └── knowledge/                    # RAG chunk source files
├── legal_graph.py                    # LangGraph sub-graph for Umang (3 nodes + quality gates)
├── aarogya_graph.py                  # LangGraph sub-graph for Aarogya
├── graph.py                          # Top-level domain routing graph
├── tests/
│   ├── test_legal_cases.py           # 91 test cases across all legal categories
│   └── test_confidence.py            # Confidence scoring tests
docs/
├── system_prompt.md                  # System prompt component architecture + token budget
├── rag_architecture.md               # Full RAG pipeline diagram and configuration
├── response_template.md              # 9-section response format with guidance per section
├── few_shot_examples.md              # Example bank structure and selection logic
├── knowledge_base_structure.md       # Static _LEGAL_KNOWLEDGE + dynamic RAG chunks
└── developer_documentation.md       # Architecture overview, env vars, adding new knowledge
```

---

## Tests

```bash
cd server
python -m pytest tests/test_legal_cases.py -v
```

91 test cases covering all legal categories: employment (salary withheld, wrongful termination, F&F settlement, POSH, PF disputes), property/tenant (illegal eviction, lockout, rent increase), family law (domestic violence, divorce, maintenance, POCSO, child custody), consumer (warranty, medical negligence), criminal (FIR refusal, bail, cheque bounce), cyber (UPI fraud, data breach, online blackmail), constitutional (RTI, fundamental rights writ), personal law routing (Hindu/Muslim/Christian), and multilingual queries (Hinglish, German).

Tests validate the Case Analyzer's structured JSON output — categories, urgency, issue_type, employment_type, property_type, follow_up questions, and confidence thresholds — without making any LLM calls. They run in under a second.

---

## Evaluation

This project was implemented, integrated, tested, and evaluated by me. AI tools were used as a development aid — for code suggestions, debugging, and documentation — not as a substitute for design decisions, domain understanding, or evaluation judgement. Every metric definition, probe design, threshold choice, and result interpretation in this section is my own work.

---

### How evaluation works

Evaluation is done offline using `evaluate.py`, which sends a fixed probe set to the live `/api/chat` endpoint and scores each response using functions defined in `evaluation/metrics.py`. No external benchmark or third-party scoring service is used — all criteria are defined and annotated by me.

Each probe specifies:
- The query and which domain it should route to (`expected_category`)
- Terms that must appear in the response (`must_contain`) — key legal acts, scheme names, helpline numbers
- Terms that must never appear (`must_not_contain`) — foreign law references, hallucination markers
- Whether a timeline is expected (`expected_timeline`) — step-by-step process responses
- Whether safety helplines are required (`safety_required`, `expected_helplines`) — for emergency queries
- The expected language of the response (`language`)

---

### Metric definitions

| Metric | What it measures | How it is checked |
|--------|-----------------|-------------------|
| **Classification accuracy** | Does the system route the query to the correct domain? | `routedDomain` from API response vs `expected_category` in probe — case-insensitive exact match after alias normalisation |
| **Confidence accuracy** | Is the system's self-reported confidence band correct? | Actual band (High / Medium / Low / None) vs expected — passes if within ±1 band |
| **Content pass rate** | Does the response contain the key information it should? | All strings in `must_contain` checked as case-insensitive substrings of the response |
| **Violation rate** | Does the response contain anything it should not? | Any string in `must_not_contain` found in the response is a violation |
| **Timeline accuracy** | Does a process response include step-by-step structure when expected? | Presence of keywords: "step", "day", "week", "phase", "duration", "पहला", "चरण" etc. matched against `expected_timeline` flag |
| **Language accuracy** | Does the response reply in the same language as the query? | Devanagari Unicode range for Hindi, German function-word regex for German, English common-word regex for English |
| **Safety pass rate** | For emergency queries, does the response include at least one real helpline? | Checks for 181, 100, 1098, 108, 112, 1091, 155260, 14416, iCall, NIMHANS, Vandrevala — and any helplines listed in `expected_helplines` |
| **Hallucination rate** | Does the response fabricate jurisdiction, law, or contact details? | Regex patterns: US federal law (18 USC, Federal Court, Supreme Court of the United States), European law (GDPR, EU law, European Court), non-existent IPC sections (>5000), fake 1800-xxx-xxxx helplines, guarantee language ("we guarantee you will win") |
| **Avg source count** | How many RAG chunks does the system cite per response? | Count of objects in `sources` array returned by the API |
| **Latency** | How long does the system take to respond? | Wall-clock time from HTTP request sent to full JSON response received |

---

### Benchmark results

**Setup:** 18 probes, run live against the server (Groq llama-3.3-70b primary LLM, MongoDB Atlas, local machine, sequential requests). Run via `python evaluate.py --token <JWT> --verbose`.

| Metric | Score | What this means |
|--------|-------|-----------------|
| **Domain classification accuracy** | **100.0%** | Every query routed to the correct assistant (Usha / Umang / Aarogya / Raksha) across all 18 probes |
| **Confidence accuracy** | **100.0%** | Self-reported confidence band matched expectation within ±1 band on all probes |
| **Content pass rate** | **94.4%** (17/18) | 17 of 18 responses contained all required key terms; one miss explained below |
| **Violation rate** | **0.0%** | No response contained any forbidden term |
| **Timeline accuracy** | **100.0%** | All process queries (RTI, UPI fraud, Mudra loan) included step-by-step structure; non-process queries correctly did not |
| **Language accuracy** | **88.9%** (16/18) | 16 of 18 responses were in the expected language; 2 Hindi-script queries returned transliterated responses |
| **Safety pass rate** | **100.0%** | All 3 emergency probes (domestic violence, blackmail, stalking) included at least one valid Indian helpline |
| **Hallucination rate** | **0.0%** | No response triggered any hallucination pattern — no foreign law, no fake helplines, no guarantee language |
| **Avg RAG source count** | **4.8 chunks** | On average, 4–5 knowledge base chunks cited per response |
| **Avg latency** | **22.84s** | Mean end-to-end response time across all 18 probes |
| **p50 latency** | **23.29s** | Half of responses completed within 23.3 seconds |
| **p90 latency** | **30.48s** | 90% of responses completed within 30.5 seconds |
| **Max latency** | **31.35s** | Slowest response (RTI process query — long structured output) |

**By domain:**

| Domain | Probes | Classification | Hallucination | Safety pass | Avg latency |
|--------|--------|---------------|---------------|-------------|-------------|
| Mental Health | 5 | 100% | 0% | 100% | 17.30s |
| Legal | 5 | 100% | 0% | n/a | 29.25s |
| Government Schemes | 5 | 100% | 0% | n/a | 23.98s |
| Safety | 3 | 100% | 0% | 100% | 19.50s |

---

### Honest qualifications

**On the 0% hallucination figure:**
This is measured against a defined set of annotation criteria — regex patterns for foreign law references, non-existent Indian legal sections, fake helpline formats, and guarantee language. It means: on 18 probes, the system produced none of the hallucination patterns I defined and checked for. It is not a claim that the system never hallucinates in any sense or in any real-world query. LLMs can produce plausible-sounding but incorrect information in ways that no finite pattern set can catch. This figure should be read as "zero detected violations under these specific criteria," not as a guarantee.

**On the 100% classification accuracy:**
Routing accuracy is high because the system uses both keyword-based pre-classification and LangGraph conditional edges. However, the probe set is 18 queries designed to have clear domain intent. Real user queries are often ambiguous (e.g., domestic violence has both mental health and legal dimensions). The 100% figure reflects clean-probe accuracy, not ambiguous-query robustness.

**On latency:**
The 22.84s average is measured on a local machine running sequential probes with no warm-up. In this setup, each request waits for the previous one to complete, FAISS retrieval runs cold, and the LLM (llama-3.3-70b via Groq) generates long structured responses for legal and scheme queries. Production latency with a warm server and parallel handling would differ. The latency figures are real measurements — not benchmarked in favourable conditions.

**On the one content miss:**
The PM-KISAN probe checked for the literal string `"6000"` (the annual ₹6,000 transfer amount). The response correctly stated the amount as `"₹6,000"` — the comma-formatted version with currency symbol — which did not match the plain substring check. This is an annotation issue, not a factual error in the response.

**On the evaluation scope:**
18 probes cover representative cases across all four domains and three languages. They do not cover every legal category, every scheme, or every possible query pattern. A larger annotated dataset would give more statistically reliable numbers. What this evaluation does establish is that the core routing, retrieval, safety, and hallucination-prevention mechanisms work correctly on the cases tested.

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

First startup downloads `multilingual-e5-small` and `ms-marco-MiniLM-L-6-v2`, then builds the FAISS + BM25 index — takes 1–2 minutes. Subsequent starts load from cache and are instant.

**Optional: install BM25 support**

```bash
pip install rank-bm25==0.2.2
```

Without it the pipeline falls back to FAISS-only retrieval with no other changes.

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
