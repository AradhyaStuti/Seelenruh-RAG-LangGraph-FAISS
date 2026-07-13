# Retrieval Evaluation Report

**Generated:** 2026-07-13 18:38 UTC  
**Queries evaluated:** 100  
**K (max retrieved):** 10

---

## Overall Metrics

| Metric | Score |
|---|---|
| P@1 | 84.0% |
| P@10 | 25.8% |
| Recall@5 | 69.3% |
| Recall@10 | 80.6% |
| MRR | 0.896 |
| NDCG@5 | 0.716 |
| NDCG@10 | 0.766 |

### Latency

| Stat | Value |
|---|---|
| p50 | 93 ms |
| mean | 97 ms |
| max | 188 ms |
| std | 23 ms |

---

## Per-Domain Breakdown

| Domain | n | P@1 | Recall@5 | Recall@10 | MRR | NDCG@5 | NDCG@10 | p50 ms |
|---|---|---|---|---|---|---|---|---|
| Government Schemes | 25 | 96.0% | 63.1% | 77.6% | 0.970 | 0.702 | 0.769 | 93 |
| Legal | 25 | 84.0% | 79.2% | 88.6% | 0.901 | 0.793 | 0.831 | 104 |
| Mental Health | 25 | 72.0% | 70.7% | 79.3% | 0.827 | 0.683 | 0.719 | 79 |
| Safety | 25 | 84.0% | 64.3% | 76.8% | 0.887 | 0.686 | 0.743 | 98 |

> **Weakest domain (Recall@5):** Government Schemes

---

## Metric Definitions

| Metric | Definition |
|---|---|
| P@1 | Is the top-ranked chunk a gold chunk? (0 or 1) |
| P@10 | Fraction of top-10 results that are gold chunks |
| Recall@K | Fraction of gold chunks found in top-K results |
| MRR | Mean Reciprocal Rank of first gold chunk across queries |
| NDCG@K | Normalised Discounted Cumulative Gain (binary relevance) |

---

## Improvement Suggestions
