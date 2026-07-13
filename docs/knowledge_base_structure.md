# Knowledge Base Structure

The knowledge base has two layers: **static deterministic knowledge** (`_LEGAL_KNOWLEDGE`)
and **dynamic RAG chunks** (FAISS + BM25 retrieved at query time).

## Layer 1 — Static Deterministic Knowledge

**File**: `server/ai/legal_agents.py` → `_LEGAL_KNOWLEDGE` dict

This is a Python dictionary keyed by legal category, providing facts that are
always reliable and should not be left to retrieval.

### Structure per category

```python
_LEGAL_KNOWLEDGE["Employment"] = {
    "applicable_laws": [
        "Code on Wages, 2019 — consolidates Payment of Wages Act 1936...",
        "Industrial Relations Code, 2020 — ...",
    ],
    "dispute_classification": {
        "labour_dispute": "Unpaid salary → Labour Commissioner (free)",
        "civil_dispute": "F&F / experience letter → legal notice → civil court",
        "criminal_offence_only_if": "Fraud, PF misappropriation, forgery — FIR then",
        "WARNING": "DO NOT recommend FIR merely because salary is unpaid.",
    },
    "procedure_steps": [
        "Step 1 — PRESERVE EVIDENCE...",
        "Step 9 — FIR ONLY IF CRIMINAL...",
    ],
    "evidence_checklist": [...],
    "limitation_periods": {...},
    "common_mistakes": [...],
}
```

### Categories covered

- Employment (Labour Codes 2020, FIR guard, F&F, EPFO)
- Property / Tenant Rights (Rent Control Acts, TPA, Model Tenancy Act)
- Family Law (HMA, PWDVA, CrPC 125/BNSS 144, Muslim personal law)
- Consumer (CPA 2019, Consumer Commission hierarchy)
- Criminal (BNS/BNSS 2023, FIR procedure, bail)
- Cyber (IT Act, DPDP Act, 1930 helpline)
- Constitutional / RTI (Article 32/226, RTI Act)
- POSH (SHe-Box, ICC obligations)

### How it's used

In `legal_agents.py` → `build_reasoning_context()`:
```python
knowledge = _LEGAL_KNOWLEDGE.get(category, {})
# → injected into system prompt as "LEGAL KNOWLEDGE CONTEXT"
```

## Layer 2 — Dynamic RAG Chunks

**Files**: `server/rag/knowledge/` → indexed in FAISS + BM25

Chunks are structured dicts:
```python
{
    "id": "employment_001",
    "domain": "Legal",
    "topic": "Unpaid wages — Labour Commissioner complaint",
    "text": "Under the Code on Wages, 2019...",
    "source": "Ministry of Labour",
    "sourceUrl": "https://...",
}
```

### Retrieval pipeline

1. Query normalized (Hinglish expansion, OCR cleanup)
2. Legal queries domain-expanded (37+ regex patterns add terminology)
3. FAISS dense retrieval → top-25 candidates
4. BM25 sparse retrieval → top-25 candidates
5. RRF fusion → single ranked list
6. Cross-encoder reranking → top-5 final chunks
7. Deduplication by topic

### Chunk enrichment

`server/rag/knowledge_meta.py` → `enrich_chunk()`:
- Adds `confidence_threshold` based on domain
- Adds `authority_weight` for trusted sources
- Adds `domain_specificity` score

## Confidence Scoring

Legal domain uses stricter thresholds:
- High confidence: ≥ 0.80 reranker score
- Medium confidence: ≥ 0.60 reranker score
- Low confidence: < 0.60 → triggers uncertainty language in response

Source: `server/rag/knowledge_meta.py` → `compute_confidence()`
