# Latency Report

**Generated:** 2026-07-13 18:38 UTC  
**Runs per stage:** 30  
**Platform:** CPU (no GPU)

---

## Retrieval Pipeline — Per-Stage Latency

| Stage | p50 (ms) | p90 (ms) | p99 (ms) | mean (ms) | max (ms) |
|---|---|---|---|---|---|
| Embedding (query -> vector) | 32.5 | 43.5 | 48.0 | 31.5 | 48.0 |
| FAISS ANN search | 1.0 | 1.4 | 1.7 | 1.0 | 1.7 |
| BM25 sparse retrieval | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Cross-encoder reranking | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| **Total retrieve()** | 33.3 | 45.0 | 49.5 | 32.6 | 49.5 |

> **BM25:** All zeros — BM25 index not loaded. Run `python prebuild_rag.py` to enable hybrid retrieval.

> **Reranker:** All zeros — either disabled (`RERANKER_ENABLED=0`) or candidate count ≤ TOP_K so reranking was skipped.

---

## LLM Latency (Groq API)

> LLM latency not measured (run without `--skip-llm` and set `GROQ_API_KEY`).


---

## Percentile Distributions

### Total Retrieval Latency (retrieve())

- p50 (median) : **33.3 ms**
- p90          : **45.0 ms**
- p99          : **49.5 ms**
- Std dev      : 7.6 ms
- Max observed : 49.5 ms

---

## Improvement Suggestions
