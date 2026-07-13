# RAG Architecture

## Pipeline Overview

```
User query
    │
    ▼
_normalize_query()          ← Hinglish expansion, OCR artifact removal
    │
    ▼  (if domain == "Legal")
_expand_legal_query()       ← Append domain-specific terminology (37+ patterns)
    │
    ├──────────────────────────────────────┐
    │                                      │
    ▼                                      ▼
FAISS dense retrieval              BM25 sparse retrieval
(multilingual-e5-small)            (rank-bm25, graceful fallback)
    │                                      │
    └──────────────────┬───────────────────┘
                       │
                       ▼
              _rrf_fuse()             ← Reciprocal Rank Fusion (k=60)
                       │
                       ▼
  cross-encoder reranker              ← ms-marco-MiniLM-L-6-v2 (optional)
  (ms-marco-MiniLM-L-6-v2)
                       │
                       ▼
             _dedup()                 ← Remove near-duplicates by topic
                       │
                       ▼
           Top-k chunks returned
```

## Components

### Embedding model
- **Model**: `intfloat/multilingual-e5-small`
- **Dimensions**: 384
- **Languages**: Supports English, Hindi, German, and 90+ others
- **Query prefix**: `"query: "` prepended at retrieval time
- **Passage prefix**: `"passage: "` prepended at index build time

### Vector store
- **Backend**: FAISS (IndexFlatL2) via `server/rag/store.py`
- **Persistence**: Pickled to disk; invalidated when chunk count changes

### BM25 sparse index
- **Library**: `rank-bm25` (BM25Okapi variant)
- **Graceful fallback**: If `rank-bm25` is not installed, only FAISS is used
- **Tokenizer**: whitespace + punctuation split, lowercased

### Reciprocal Rank Fusion
- **Formula**: `score(d) = Σ 1/(k + rank_i(d))` where `k=60`
- **Benefit**: Combines lexical (BM25) and semantic (FAISS) signals without score normalisation

### Cross-encoder reranker
- **Model**: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **Role**: Reranks fused candidates by true query-document relevance
- **Optional**: Falls back to score-ordered fusion if reranker is disabled

## Query Expansion

37+ regex patterns in `_LEGAL_EXPANSIONS` append domain-specific terms to vague queries.

Examples:
- "salary nahi mili" → `+ "Code on Wages 2019 Payment of Wages Act unpaid salary labour commissioner..."`
- "landlord ne lock lagaya" → `+ "Transfer of Property Act rent control eviction notice tenant rights..."`

## Hinglish Map

80+ Hinglish/Roman-script Hindi terms mapped to English equivalents before embedding:
- `"tankhwaah"` → `"salary wages"`
- `"vakeel"` → `"lawyer"`
- `"kirayedaar"` → `"tenant renter"`

## Configuration

```python
# config.py
RETRIEVAL_TOP_K = 5       # Final chunks returned to composer
RETRIEVAL_OVERFETCH = 15  # Candidates fetched before reranking
```

Overfetch multipliers (applied before cross-encoder):
- Legal: `max(15, 25)` = 25 candidates
- Government Schemes: `max(15, 20)` = 20 candidates
- Other: 15 candidates
