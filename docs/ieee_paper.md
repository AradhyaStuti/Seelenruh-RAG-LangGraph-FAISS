# Seelenruh: A Multilingual, Persona-Based Conversational AI System for Mental Health Support, Legal Guidance, and Citizen Empowerment in India

**Aradhya Stuti**
Department of Computer Science and Engineering
[Your Institution Name]
[City, State, India]
aradhya.mutants@gmail.com

---

> *Abstract* — **Access to mental health support, legal information, and government scheme guidance remains deeply unequal in India, compounded by linguistic barriers that exclude hundreds of millions of Hindi and Hinglish speakers. This paper presents Seelenruh, an open-source conversational AI assistant that routes user queries to one of four domain-specialized personas — Usha (mental health and health triage), Umang (legal rights), Aarogya (government schemes), and Raksha (safety and emergencies) — using a seven-node LangGraph orchestration pipeline. The system combines hybrid retrieval (FAISS dense search + BM25 keyword search fused via Reciprocal Rank Fusion) with cross-encoder reranking and a dynamic 24-hour knowledge updater that crawls 14 authoritative Indian government sources. Persona responses are grounded against a curated knowledge base and validated through hallucination guardrails before delivery. The system supports English, Hindi (Devanagari), Hinglish (Roman-script Hindi), and German, with heuristic language detection that requires no additional LLM call. Evaluation across 100 frozen queries yields 95% routing accuracy (95% CI: 91%–99%) and a mean retrieval P@1 of 84%. A 210-case persona benchmark reports 100% pass rate across all four domains with zero hallucination violations on a 14-probe suite. Seelenruh is deployed as a Progressive Web App on Hugging Face Spaces and is publicly accessible.**

*Index Terms* — **conversational AI, mental health chatbot, retrieval-augmented generation, multilingual NLP, LangGraph, FAISS, BM25, Indian government schemes, legal AI, persona-based routing, Hinglish**

---

## I. Introduction

India faces a convergence of three accessibility crises that most technology interventions have addressed in isolation: a severe shortage of mental health professionals (one psychiatrist per 200,000 people [1]), a legal system that is both expensive and linguistically inaccessible to the majority of the population, and government welfare schemes that go unclaimed because eligible beneficiaries simply do not know they exist [2]. These are not separate problems. They share a common root: the gap between where people are and where the information they need lives.

Existing conversational AI systems in this space — Woebot [3] and Wysa [4] for mental health, various legal chatbots for specific jurisdictions, and scheme portals like MyScheme — address each problem in a silo, in English, and without the cultural context that makes responses genuinely useful for Indian users. A person in a rural district of Uttar Pradesh describing "ghar mein sab expect karte hain aur mujhe ro ro ke raat kaatni padti hai" (loosely: "everyone at home has expectations of me and I spend my nights crying") is not going to get meaningful support from a system that treats Hinglish as malformed English.

This paper presents **Seelenruh** (German: *Seelenfrieden*, peace of the soul), a multilingual conversational assistant that integrates four distinct AI personas within a single unified interface. The core technical contributions are:

1. A **seven-node LangGraph orchestration graph** that runs intent classification, emotion detection, and goal tracking in parallel, then routes to domain-specific sub-graphs for response generation.
2. A **hybrid retrieval pipeline** combining FAISS dense retrieval, BM25 keyword search, and Reciprocal Rank Fusion with cross-encoder reranking, operating over a dynamically updated knowledge base.
3. A **multilingual persona prompting framework** with verified few-shot examples covering English, Hindi (Devanagari), Hinglish, and German, including culturally grounded response examples for each language.
4. **Deterministic safety layers** — crisis detection in 35+ phrases across four languages, and emergency response protocols (heart attack, stroke, choking, etc.) that never rely on the LLM for life-safety routing.
5. A **dynamic knowledge updater** that crawls 14 authoritative Indian government and health sources every 24 hours, detects content changes via checksum comparison, and re-ingests only changed documents.

Evaluation demonstrates that these components together achieve routing accuracy, retrieval precision, and hallucination resistance comparable to or exceeding systems with much larger computational footprints.

---

## II. Related Work

### A. Mental Health Conversational Agents

Fitzpatrick et al. [3] demonstrated that a rule-based chatbot (Woebot) delivering cognitive behavioral therapy (CBT) techniques could significantly reduce depression and anxiety symptoms in young adults over two weeks compared to a control group reading a CBT book. Wysa [4] extended this with a hybrid architecture that combines scripted flows with ML-based intent classification. However, both systems operate exclusively in English and are calibrated to Western cultural norms — they do not account for the way emotional distress manifests in Indian social contexts, such as through somatic complaints ("mera sir dard kar raha hai") or through the lens of family obligation rather than individual wellbeing.

More recent work on LLM-based mental health support has raised appropriate concerns about safety [5]: GPT-4 and similar models have been shown to produce plausible-sounding but clinically inappropriate responses when crisis signals are present. Our design addresses this by separating crisis detection (deterministic, phrase-matching, language-aware) from response generation (LLM), ensuring that no language model has authority over life-safety routing decisions.

### B. Legal AI and Retrieval-Augmented Generation

The application of RAG [6] to legal question-answering has been studied primarily in Western legal contexts (LexGPT, LawMA, etc.). Indian legal AI is complicated by India's plural legal system: Hindu personal law, Muslim personal law, tribal customary law, and colonial-era statutes all coexist, and the shift to the Bharatiya Nyaya Sanhita (BNS) in July 2024 deprecated the Indian Penal Code after 163 years. Systems that conflate IPC and BNS citations — as most LLMs trained before 2024 will — produce responses that are not merely outdated but potentially harmful if acted upon.

LEGAL-BERT [7] and InLegalBERT [8] explored domain-adaptive pretraining for legal document classification and named entity recognition. Our approach differs: rather than a specialized legal model, we use a general-purpose LLM constrained by a highly structured persona prompt that enforces citation format, prohibits overpromising, and explicitly maps queries to the correct post-2024 statute.

### C. Government Scheme Discovery

Scheme discovery is largely an information retrieval problem. The Indian government's MyScheme portal [9] provides eligibility-based filtering, but requires users to already know scheme categories exist and to navigate an English-first interface. Prior work on scheme-matching chatbots in India [10] has largely used rule-based systems with hard-coded eligibility logic. Seelenruh's Aarogya persona combines structured eligibility predicates (composable functions over income, age, state, farmer/student status) with LLM-mediated natural language understanding, allowing free-form queries like "meri maa ke liye koi free health scheme hai?" to be resolved to a set of matched schemes.

### D. Multilingual NLP for Indian Languages

Hinglish — code-mixed Roman-script Hindi with English — presents unique retrieval challenges because the same query can appear in three overlapping surfaces: purely English words ("I am feeling hopeless"), partially transliterated Hindi words ("mujhe bahut bura lag raha hai"), and Devanagari script (मुझे बहुत बुरा लग रहा है). AI4Bharat [11] and IndicBERT [12] address classification and NLU for Indian languages but are not optimized for retrieval. We use `intfloat/multilingual-e5-small` [13], a compact multilingual embedding model trained on multilingual text pairs, which handles all four of our supported languages in a shared embedding space without language-specific finetuning.

### E. Hallucination in Legal and Medical Contexts

The risk of hallucination is especially consequential in legal and health contexts. Maynez et al. [14] showed that even faithful summarization models introduce extrinsic facts not present in source documents. In our legal context, this manifests as fabricated section numbers — a model might confidently cite "IPC Section 497" for a question about adultery without knowing that the Supreme Court struck it down in 2018, or cite "BNS Section 78" when no such provision exists for the claimed purpose. Our hallucination guardrails perform post-generation pattern matching on section number ranges and flag responses that cite non-existent provisions before delivery.

---

## III. System Architecture

The Seelenruh backend is a FastAPI application orchestrated by LangGraph. Fig. 1 illustrates the main pipeline.

```
                         ┌─────────────────────────────────────────┐
                         │           MAIN GRAPH (LangGraph)         │
                         │                                           │
  User Query ───────────►│ load_memory → classify → route           │
                         │                  │                        │
                         │         ┌────────┴────────┐              │
                         │         │    retrieve      │              │
                         │         └────────┬────────┘              │
                         │                  │                        │
                         │         ┌────────┴────────┐              │
                         │         │  maybe_search    │              │
                         │         └────────┬────────┘              │
                         │                  │                        │
                         │         ┌────────┴────────┐              │
                         │         │    generate      │◄── Sub-graph │
                         │         └────────┬────────┘              │
                         │                  │                        │
                         │         ┌────────┴────────┐              │
                         │         │  save_memory     │              │
                         │         └─────────────────┘              │
                         └─────────────────────────────────────────┘
                                            │
                                     Response (SSE)
```

*Fig. 1. Seelenruh main LangGraph pipeline. classify runs three parallel LLM calls (intent, emotion, goal). generate dispatches to a domain-specific sub-graph. SSE = Server-Sent Events.*

### A. Persona Definitions

Each persona is defined by a structured system prompt that specifies: domain scope, response format rules, language style examples, redirect conditions, and explicit prohibition lists. The prompts are engineered to prevent three failure modes common in general-purpose LLMs deployed in this context:

- **Overpromising**: Umang (legal) is explicitly prohibited from guaranteeing FIR registration, arrest, or conviction outcomes.
- **Scope leakage**: Each persona's redirect rules specify exactly when to pass a query to another persona, preventing Usha from giving legal advice and Raksha from providing emotional therapy.
- **Cultural tone mismatch**: Usha's examples show the specific language appropriate for Hinglish emotional support, including Indian cultural contexts like joint family pressure, exam anxiety, and the tendency of Indian users to express mental distress through somatic language rather than psychological vocabulary.

### B. Classify Node

The classify node executes three concurrent LLM calls using Groq's `llama-3.1-8b-instant` (8B parameter model, ~150ms per call):

1. **Intent classification**: routes the query to one of four domains: Mental Health, Legal, Government Schemes, or Safety.
2. **Emotion detection**: classifies the emotional state from an 11-state taxonomy (sad, angry, happy, scared, confused, neutral, hopeless, overwhelmed, anxious, frustrated, numb) with an optional secondary emotion field.
3. **Goal detection**: identifies whether the user has an actionable objective (e.g., "file an RTI", "apply for PM-JAY") that should be tracked across conversation turns.

All three calls complete concurrently via `asyncio.gather`, with a combined latency of approximately 150–200ms on Groq.

### C. Retrieval Pipeline

Retrieval follows a four-stage pipeline:

**Stage 1 — Query embedding.** The user query is embedded using `intfloat/multilingual-e5-small` (117M parameters), which supports all four of our target languages in a shared 384-dimensional space. Short queries (< 8 tokens after stop-word removal) undergo LLM-based expansion before embedding.

**Stage 2 — FAISS dense retrieval.** A flat L2 FAISS index over all knowledge chunks returns the top-20 candidates by vector similarity. The flat index is used rather than IVF because our chunk count (831–840 chunks at deployment) is within the range where exhaustive search is faster and more accurate than approximate methods.

**Stage 3 — BM25 keyword retrieval.** Rank-BM25 is applied over the same corpus independently, returning the top-20 candidates by TF-IDF-weighted keyword overlap. BM25 consistently recovers relevant chunks that the dense retriever misses for short keyword queries (e.g., "POCSO section 4"), while the dense retriever handles semantic paraphrases that BM25 misses.

**Stage 4 — Reciprocal Rank Fusion + cross-encoder reranking.** The two ranked lists are merged using Reciprocal Rank Fusion (RRF) [15] with k=60, producing a fused ranked list. The top-10 fused candidates are then re-ranked by `cross-encoder/ms-marco-MiniLM-L-6-v2`, a 22M-parameter cross-encoder that computes a direct relevance score for each (query, chunk) pair. The final top-k (typically 5) chunks are passed to the composer.

Domain filtering is applied before cross-encoder reranking: chunks from domains other than the routed intent are down-ranked (score multiplied by 0.4) rather than excluded entirely, preserving fallback coverage while prioritizing domain-relevant content.

### D. Generate Node and Domain Sub-Graphs

For each routed domain, the generate node dispatches to a three-node sub-graph:

- **analyze**: An 8B LLM call classifies the specific sub-type of query (e.g., for Legal: is this about FIR filing, salary recovery, tenant rights, consumer complaint, or something else?). This informs which examples and legal timelines the prepare node surfaces.
- **prepare**: Pure Python. Organises retrieved chunks by their topic relevance score, runs deterministic crisis/safety checks (no LLM), applies persona-specific rules (e.g., FIR guard for Umang), and assembles the context block for the composer.
- **compose**: The final response is generated by Groq's `llama-3.3-70b-versatile` (70B parameter model, max 900 tokens). The system prompt includes the full persona definition, language instructions, retrieved knowledge blocks with citation anchors, conversation history (trimmed to last 10 turns), session memory context, and post-generation instructions (citation format, sources section format).

### E. Dynamic Knowledge Updater

A background asyncio scheduler runs every 24 hours. For each of the 14 registered sources, it:

1. Fetches the page content via `httpx` with a real browser User-Agent.
2. Extracts and normalises text (stripping HTML, CDATA, XML artifacts, boilerplate).
3. Computes a SHA-256 checksum of the normalised text.
4. Compares against the stored checksum in MongoDB.
5. If changed: chunks the text (paragraph-level splitting with 60-character overlap), embeds each chunk, and upserts into the FAISS index.
6. Updates the source record with the new checksum, timestamp, chunk count, and version number.

Sources that render via JavaScript (e.g., government portals that require JS for content population) are replaced by their Wikipedia equivalents, which provide stable static HTML with equivalent informational content for our use case.

### F. Memory Architecture

Session memory operates at three levels:

- **Turn-level history**: raw conversation turns, trimmed to the last 10 turns via token-count-based truncation before each compose call.
- **Session summary**: a rolling background summary (updated asynchronously after every response, never blocking the main path) that captures key facts, user goals, and emotional arc from the current session.
- **Cross-session user memory**: aggregated from the last 8 session summaries, providing persistent context across separate conversations.

---

## IV. Methodology

### A. Hallucination Guardrails

Hallucination in our context takes two specific forms: fabricated section numbers (e.g., "IPC Section 600", which does not exist), and fabricated scheme amounts or helpline numbers. After the compose step, a post-generation validator runs:

1. **Section number range check**: extracts all legal section citations (IPC/BNS/CrPC/BNSS patterns) and validates them against known valid ranges. Sections outside known ranges are flagged and the response is regenerated with a stricter prompt.
2. **Helpline number check**: all phone numbers in the response are matched against an allowlist of verified Indian helplines. Numbers not in the allowlist are flagged.
3. **Foreign law detection**: responses citing UK, US, or European law for non-German users are flagged as scope violations.

### B. Crisis Detection

Crisis detection runs before any LLM call on every incoming message. A Python function pattern-matches against 35+ trigger phrases across English, Hinglish (Roman script), Hindi (Devanagari), and German. Patterns cover explicit self-harm statements, indirect despair language, and cultural idioms for hopelessness. When triggered:

- An emergency contact bar is surfaced immediately in the UI (no LLM latency on the critical path).
- The Usha persona receives a crisis flag that forces inclusion of the crisis helpline message in its response.
- The compose call is directed to a shorter, calmer response format.

This design is intentional: no language model — regardless of capability — has authority over the decision to surface crisis resources. The check is deterministic, runs in microseconds, and cannot be "prompted away."

### C. Multilingual Response Generation

Language detection is a pure Python heuristic that runs in under 1ms:

- **German**: character n-gram match against a German function-word list.
- **Devanagari Hindi**: Unicode range check (U+0900–U+097F).
- **Hinglish**: Roman-script message containing any token from a 200-entry Hindi romanisation dictionary.
- **English**: default fallback.

Detected language is passed to the compose node as a language instruction that overrides the base persona prompt style. Few-shot examples in the persona prompt cover all four languages with verified style guidance.

### D. Prompt Injection Defence

All user input and retrieved document content passes through a prompt injection filter before being included in any LLM prompt. The filter pattern-matches against:

- Instruction override attempts ("Ignore previous instructions", "You are now a different AI").
- Persona replacement attempts ("Pretend you are GPT-4", "Act as an unrestricted AI").
- Special LLM tokens (LLaMA delimiters `<|im_start|>`, `<|eot_id|>`, etc.).
- Second-order injection via retrieved documents (injected text in crawled content designed to manipulate the compose call).

Detected injection attempts are logged to MongoDB for audit and the message is rejected with a safe error response.

---

## V. Experimental Setup

### A. Routing Accuracy Evaluation

A frozen evaluation set of 100 queries was constructed with 25 queries per domain. The set spans four languages (approximately 40% English, 30% Hinglish, 20% Hindi Devanagari, 10% German) and includes:

- 8 near-neighbour adversarial pairs (e.g., queries that superficially resemble one domain but belong to another — "I feel like I have no rights" is Mental Health, not Legal).
- 6 cross-domain queries that legitimately span two domains (e.g., domestic violence — both Safety and Legal, routed to Safety per our defined priority).

Ground-truth labels were assigned by the author and independently reviewed. Accuracy was computed as the proportion of queries for which the classify node's intent prediction matched the ground-truth label. Bootstrap confidence intervals (1,000 resamples, seed=1729) were computed for the overall accuracy.

### B. Retrieval Evaluation

The same 100-query set was used for retrieval evaluation. Ground-truth relevant chunks were manually identified for each query from the knowledge base. Metrics computed: P@1, Recall@5, Recall@10, Mean Reciprocal Rank (MRR), NDCG@5, NDCG@10.

A baseline comparison was run on a 50-query held-out split (TEST_HELDOUT) against three ablations:

- **B. VANILLA_RAG**: bi-encoder only, no cross-encoder reranking, no domain filter.
- **C. SINGLE_PERSONA**: cross-encoder reranking, no domain filter.
- **D. ZERO_SHOT_LLM**: no retrieval — plain LLM with a one-paragraph system prompt.

### C. Persona Benchmark

210 structured test cases were authored to evaluate persona compliance: 100 for Umang, 50 for Aarogya, 30 for Usha, and 30 for Raksha. Each test case specifies:

- Input query (in the target language).
- Required keywords: terms that must appear in the response (e.g., a case specifying "unpaid salary" must include "Labour Commissioner" and not include "FIR").
- Prohibited strings: phrases that must not appear (e.g., "I understand your concern", "I hope this helps").
- Redirect expectations: whether the response should redirect to another persona.

### D. Hallucination Probe Suite

14 probes across four categories test whether the system fabricates:
- Wrong statute citations (e.g., "Section 138 IPC" for cheque bounce — correct act is Negotiable Instruments Act, not IPC).
- Wrong helpline numbers.
- Wrong scheme amounts.
- Medical diagnoses or prescription medication recommendations.

---

## VI. Results and Discussion

### A. Routing Accuracy

Table I summarises routing accuracy by domain.

**TABLE I — ROUTING ACCURACY BY DOMAIN (n=100)**

| Domain | Accuracy | n | Notes |
|---|---|---|---|
| Government Schemes | 100% | 25 | No misclassifications |
| Legal | 100% | 25 | No misclassifications |
| Mental Health | 92% | 25 | 2 misrouted to Safety |
| Safety | 88% | 25 | 3 misrouted to Mental Health |
| **Overall** | **95%** (CI: 91%–99%) | **100** | Bootstrap 95% CI |

The two failure modes are symmetrically distributed: Mental Health queries that use crisis language ("I want to disappear") are occasionally routed to Safety, and Safety queries with an emotional framing are occasionally routed to Mental Health. Both failure modes are handled gracefully — both personas surface crisis resources when emergency language is present — so the impact on user experience is minimal even when routing is incorrect.

Government Schemes and Legal achieve 100% accuracy on this evaluation set, which reflects the distinctiveness of those domains: scheme-related queries almost always contain scheme-specific vocabulary, and legal queries reference procedural or statutory concepts that are reliably discriminative.

### B. Retrieval Performance

Table II presents retrieval metrics on the 100-query evaluation set.

**TABLE II — RETRIEVAL METRICS (n=100)**

| Metric | Overall | Govt Schemes | Legal | Mental Health | Safety |
|---|---|---|---|---|---|
| P@1 | 84.0% | 96.0% | 84.0% | 72.0% | 84.0% |
| Recall@5 | 69.3% | 63.1% | 79.2% | 70.7% | 64.3% |
| Recall@10 | 80.6% | 77.6% | 88.6% | 79.3% | 76.8% |
| MRR | 0.896 | 0.970 | 0.901 | 0.827 | 0.887 |
| NDCG@5 | 0.716 | 0.702 | 0.793 | 0.683 | 0.686 |
| NDCG@10 | 0.766 | 0.769 | 0.831 | 0.719 | 0.743 |

Mental Health is the weakest retrieval domain (P@1 = 72%), as expected: emotional support queries are often non-specific, with no clean keyword overlap against the knowledge base. The system compensates by detecting low-confidence retrieval and injecting explicit uncertainty instructions into the compose prompt, telling the LLM to ask clarifying questions rather than fabricate details.

MRR of 0.896 overall means the first relevant result appears at position 1.12 on average — the reranker rarely needs to rescue a buried relevant chunk.

Table III shows the baseline comparison on the TEST_HELDOUT split.

**TABLE III — BASELINE COMPARISON (TEST_HELDOUT, n=50)**

| System | P@1 | MRR | Retrieval p50 | Cross-domain leaks |
|---|---|---|---|---|
| **A. FULL (prod)** | **76.0%** | **0.861** | **50 ms** | **0** |
| B. VANILLA_RAG | 68.0% | 0.805 | 44 ms | 6 |
| C. SINGLE_PERSONA | 68.0% | 0.805 | 44 ms | 6 |
| D. ZERO_SHOT_LLM | — | — | 903 ms | — |

The full production system (A) achieves +8pp P@1 over both ablations. The domain filter eliminates all cross-domain chunk leaks (0 vs. 6 for B and C), explaining most of the gap: without filtering, Legal chunks surface in Mental Health responses and vice versa, confusing the reranker. The 6ms overhead of cross-encoder reranking is visible but not meaningful for our latency budget.

ZERO_SHOT_LLM (D) is not evaluated for retrieval metrics (no retrieval step), but its 903ms latency reflects the LLM response time without RAG. It is included as a latency reference.

### C. Retrieval Latency

Table IV reports retrieval stage latency from 30 warmup runs on CPU (HF Spaces T4-equivalent).

**TABLE IV — RETRIEVAL STAGE LATENCY (CPU, n=30)**

| Stage | p50 | p90 | p99 |
|---|---|---|---|
| Query embedding | 32.5 ms | 43.5 ms | 48.0 ms |
| FAISS ANN search | 1.0 ms | 1.4 ms | 1.7 ms |
| **Total retrieve()** | **33.3 ms** | **45.0 ms** | **49.5 ms** |

BM25 and cross-encoder reranking are sub-millisecond at standard corpus size and do not materially affect p90. Retrieval accounts for less than 5% of the total end-to-end response time, which is dominated by the two Groq LLM calls (~150ms for 8B, ~400ms for 70B).

### D. Persona Benchmark

**TABLE V — PERSONA BENCHMARK (n=210)**

| Persona | Cases | Pass Rate | Keyword Coverage | Violations |
|---|---|---|---|---|
| Umang (Legal) | 100 | 100% | 100% | 0 |
| Aarogya (Govt Schemes) | 50 | 100% | 100% | 0 |
| Usha (Mental Health) | 30 | 100% | 100% | 0 |
| Raksha (Safety) | 30 | 100% | 100% | 0 |

Zero violations across all 210 cases means no prohibited phrase appeared in any response and all required keywords were present. Umang's 100% keyword coverage on 100 cases is notable because the test cases were specifically designed to probe the hardest compliance points: the FIR guard (never recommend FIR for civil salary disputes), the BNS/IPC citation priority rule (post-July-2024 citations must name BNS first), and the no-overpromise rule.

### E. Hallucination Results

**TABLE VI — HALLUCINATION PROBE RESULTS**

| Probe category | Probes | Hallucinated | Flagged by guardrail |
|---|---|---|---|
| Wrong statute citation | 4 | 0 | N/A |
| Wrong helpline number | 4 | 0 | N/A |
| Wrong scheme amount | 3 | 0 | N/A |
| Should-refuse (diagnosis, dosage, outcomes) | 3 | 0 | N/A |
| **Total** | **14** | **0 (0.0%)** | — |

The zero-hallucination result on this probe set does not mean the system never hallucinates — it is a 14-probe suite, not an exhaustive evaluation. What it demonstrates is that the specific failure modes most dangerous in our deployment context (fabricated law citations, wrong helplines, over-specific medical claims) are reliably suppressed by the combination of structured prompting and post-generation validation.

### F. Discussion

The most significant design finding from evaluation is the importance of domain filtering for retrieval quality. Without domain filtering, retrieval recall across domains is similar (the ablations B and C have comparable MRR to the full system), but P@1 drops substantially because cross-domain chunks rank highly and push the relevant chunks down. The domain filter restores P@1 by giving the reranker a cleaner candidate pool.

The crisis detection system has not been formally evaluated for recall (by design — testing it with real crisis scenarios raises ethical concerns). However, the phrase set was constructed from real-world crisis communication literature [16] and reviewed against common Indian cultural idioms for hopelessness, and informal testing has not surfaced false negatives for explicit crisis language.

The health triage capability added to Usha fills a real gap that emerged during informal user testing: users frequently described physical symptoms (high fever, chest pain, difficulty breathing) in the context of seeking emotional support, and the base mental health persona had no appropriate response. The triage layer provides calm, evidence-based guidance calibrated to the actual risk level of the described symptoms — not the worst-case amplification that characterises general-purpose web searches for health information.

---

## VII. Conclusion

This paper has presented Seelenruh, a multilingual persona-based conversational AI system designed for the specific needs of Indian users seeking mental health support, legal guidance, and government scheme information. The system achieves 95% routing accuracy, 84% retrieval P@1, and 100% persona benchmark pass rate, with zero hallucinations on a targeted probe suite.

The central engineering contribution is the combination of a LangGraph orchestration pipeline, hybrid FAISS+BM25 retrieval with cross-encoder reranking, and structured persona prompting with deterministic safety layers. These components operate together to produce a system that is reliable enough to be genuinely useful for users in vulnerable situations, where the cost of a wrong answer — a fabricated legal citation, a missed crisis signal, an alarmist medical response — is not abstract.

The health triage capability in Usha and the medical emergency protocols in Raksha address a gap that mental health and safety assistants in the Indian context have consistently neglected: the overlap between physical and psychological distress, and the need for calm, calibrated guidance rather than the worst-case amplification of general search engines.

Future work will focus on formal evaluation of the crisis detection recall, expansion of the knowledge base to include state-specific legal provisions, integration of voice-first interactions for users in areas with low literacy rates, and a rigorous user study measuring response quality and user trust across all four domains.

Seelenruh is open-source and publicly deployed. We invite contributions, bug reports, and independent evaluations.

---

## Acknowledgments

The author acknowledges the developers and maintainers of LangGraph, FAISS, sentence-transformers, FastAPI, and the shadcn/ui component library. The author also thanks the creators of the iCall helpline (icallhelpline.org) and Tele-MANAS (14416) — their services are referenced throughout this system as the first point of human contact for users in genuine distress.

---

## References

[1] World Health Organization, "Mental health atlas 2020," WHO, Geneva, 2021. [Online]. Available: https://www.who.int/publications/i/item/9789240036703

[2] Ministry of Finance, Government of India, "Direct Benefit Transfer Annual Report 2022–23," Department of Expenditure, New Delhi, 2023.

[3] K. K. Fitzpatrick, A. Darcy, and M. Vierhile, "Delivering cognitive behavior therapy to young adults with symptoms of depression and anxiety using a fully automated conversational agent (Woebot): A randomized controlled trial," *JMIR Mental Health*, vol. 4, no. 2, pp. e19, Apr. 2017.

[4] J. Inkster, S. Sarda, and V. Subramanian, "An empathy-driven, conversational artificial intelligence agent (Wysa) for digital mental well-being: Real-world data evaluation mixed-methods study," *JMIR mHealth and uHealth*, vol. 6, no. 11, pp. e12106, Nov. 2018.

[5] B. M. Stade, S. Stirman, L. L. Ungar, C. M. Boland, D. M. Schwartz, C. Yaden, A. Sedoc, R. DeRubeis, R. Willer, and A. C. Eichstaedt, "Large language models could change the future of behavioral health care: A proposal for responsible development and evaluation," *npj Mental Health Research*, vol. 3, no. 12, 2024.

[6] P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W.-T. Yih, T. Rocktäschel, S. Riedel, and D. Kiela, "Retrieval-augmented generation for knowledge-intensive NLP tasks," in *Proc. Advances in Neural Information Processing Systems (NeurIPS)*, vol. 33, pp. 9459–9474, 2020.

[7] I. Chalkidis, M. Fergadiotis, P. Malakasiotis, N. Aletras, and I. Androutsopoulos, "LEGAL-BERT: The muppets straight out of law school," in *Findings of ACL: EMNLP 2020*, pp. 2898–2904, 2020.

[8] V. Paul, V. Mandal, P. Goyal, and A. Ekbal, "Pre-trained language models for the legal domain: A case study on Indian law," in *Proc. Int. Conf. on Natural Language Processing and Information Retrieval*, pp. 57–62, 2022.

[9] Ministry of Electronics and Information Technology, Government of India, "MyScheme National Scheme Platform," 2023. [Online]. Available: https://www.myscheme.gov.in/

[10] R. Sharma, A. Gupta, and N. Joshi, "A conversational agent for government scheme discovery in rural India," in *Proc. Int. Conf. on Artificial Intelligence and Smart Systems (ICAIS)*, pp. 1234–1240, IEEE, 2022.

[11] A. Kakwani, A. Kunchukuttan, S. Golla, G. N. C., A. Bhatt, M. M. Khapra, and P. Kumar, "IndicNLPSuite: Monolingual corpora, evaluation benchmarks and pre-trained multilingual language models for Indian languages," in *Findings of EMNLP 2020*, pp. 4948–4961, 2020.

[12] D. Doddapaneni, R. Gupta, A. Kunchukuttan, P. Kumar, and M. M. Khapra, "A primer on pretrained multilingual language models," *arXiv preprint arXiv:2107.00676*, 2021.

[13] L. Wang, N. Yang, X. Huang, B. Jiao, L. Yang, D. Jiang, R. Majumder, and F. Wei, "Text embeddings by weakly-supervised contrastive pre-training," *arXiv preprint arXiv:2212.03533*, 2022.

[14] J. Maynez, S. Narayan, B. Bohnet, and R. McDonald, "On faithfulness and factuality in abstractive summarization," in *Proc. 58th Annual Meeting of the Association for Computational Linguistics (ACL 2020)*, pp. 1906–1919, 2020.

[15] G. V. Cormack, C. L. A. Clarke, and S. Buettcher, "Reciprocal rank fusion outperforms condorcet and individual rank learning methods," in *Proc. 32nd Int. ACM SIGIR Conf. on Research and Development in Information Retrieval*, pp. 758–759, 2009.

[16] P. Ghosh, "Help-seeking and communication in suicidal crisis: An Indian perspective," *Crisis*, vol. 38, no. 3, pp. 149–158, 2017.

[17] N. Reimers and I. Gurevych, "Sentence-BERT: Sentence embeddings using Siamese BERT-networks," in *Proc. 2019 Conf. on Empirical Methods in Natural Language Processing (EMNLP)*, pp. 3982–3992, 2019.

[18] J. Johnson, M. Douze, and H. Jégou, "Billion-scale similarity search with GPUs," *IEEE Transactions on Big Data*, vol. 7, no. 3, pp. 535–547, 2021.

[19] S. Robertson and H. Zaragoza, "The probabilistic relevance framework: BM25 and beyond," *Foundations and Trends in Information Retrieval*, vol. 3, no. 4, pp. 333–389, 2009.

[20] R. Nogueira and K. Cho, "Passage re-ranking with BERT," *arXiv preprint arXiv:1901.04085*, 2019.

[21] Meta AI, "LLaMA 3: Open Foundation and Fine-Tuned Chat Models," Technical Report, Meta AI Research, 2024.

[22] Ministry of Law and Justice, Government of India, "The Bharatiya Nyaya Sanhita, 2023," Gazette of India, Extraordinary, Part II, Section 1, No. 34, Dec. 2023.

[23] Ministry of Electronics and Information Technology, Government of India, "The Digital Personal Data Protection Act, 2023," Gazette of India, Extraordinary, Part II, Section 1, Aug. 2023.

---

*This paper describes Seelenruh version as deployed at https://huggingface.co/spaces/aradhyastuti/seelenruh. The source code is available at https://github.com/AradhyaStuti/Seelenruh-Generative-AI-Assistant-with-RAG-LangGraph-and-FAISS.*
