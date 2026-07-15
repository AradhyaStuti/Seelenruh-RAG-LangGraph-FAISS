"""
bench_retrieval.py
------------------
Extended retrieval evaluation using the existing 100 labelled test cases
from eval_data.py (which carry gold chunk IDs).

Metrics computed (all @K where K is configurable):
  P@1       -- precision at rank 1 (existing)
  P@K       -- precision at rank K  = |retrieved[:K] ∩ gold| / K
  Recall@K  -- |retrieved[:K] ∩ gold| / |gold|
  MRR       -- mean reciprocal rank (existing)
  NDCG@K    -- normalised discounted cumulative gain (binary relevance)

Run:
  cd server && .venv/Scripts/python -m bench.bench_retrieval
  cd server && .venv/Scripts/python -m bench.bench_retrieval --k 10 --split all
"""
from __future__ import annotations

import asyncio
import json
import math
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, stdev

# Make sure server/ root is on sys.path when run directly
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import RETRIEVAL_TOP_K  # noqa: E402
from eval_data import by_split  # noqa: E402
from rag import retriever  # noqa: E402

RESULTS_DIR = Path(__file__).parent / "reports"
RESULTS_DIR.mkdir(exist_ok=True)

DEFAULT_K = max(RETRIEVAL_TOP_K, 10)   # evaluate up to 10 even if retriever returns 5

# Metric helpers
def _precision_at_k(retrieved_ids: list[str], gold_set: set[str], k: int) -> float:
    top_k = retrieved_ids[:k]
    hits = sum(1 for r in top_k if r in gold_set)
    return hits / k if k else 0.0

def _recall_at_k(retrieved_ids: list[str], gold_set: set[str], k: int) -> float:
    if not gold_set:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for r in top_k if r in gold_set)
    return hits / len(gold_set)

def _reciprocal_rank(retrieved_ids: list[str], gold_set: set[str]) -> float:
    for i, rid in enumerate(retrieved_ids, start=1):
        if rid in gold_set:
            return 1.0 / i
    return 0.0

def _dcg_at_k(retrieved_ids: list[str], gold_set: set[str], k: int) -> float:
    """DCG with binary relevance."""
    dcg = 0.0
    for i, rid in enumerate(retrieved_ids[:k], start=1):
        if rid in gold_set:
            dcg += 1.0 / math.log2(i + 1)
    return dcg

def _idcg_at_k(gold_size: int, k: int) -> float:
    """Ideal DCG: all relevant docs at the top."""
    n_rel = min(gold_size, k)
    return sum(1.0 / math.log2(i + 1) for i in range(1, n_rel + 1))

def _ndcg_at_k(retrieved_ids: list[str], gold_set: set[str], k: int) -> float:
    idcg = _idcg_at_k(len(gold_set), k)
    if idcg == 0:
        return 0.0
    return _dcg_at_k(retrieved_ids, gold_set, k) / idcg

# Core evaluator
async def run_retrieval_eval(cases: list[dict], k: int = DEFAULT_K) -> dict:
    """
    Run retrieval evaluation on *cases* (must have gold chunk IDs).
    Returns a results dict suitable for report generation.
    """
    results: list[dict] = []
    latencies: list[float] = []
    per_domain: dict[str, list[dict]] = defaultdict(list)

    for case in cases:
        gold_set = set(case["gold"])
        domain = case.get("domain")

        t0 = time.perf_counter()
        hits = await retriever.retrieve(case["q"], domain=domain, k=k)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        retrieved_ids = [h["id"] for h in hits]

        row = {
            "q": case["q"],
            "domain": domain,
            "gold_size": len(gold_set),
            "p1":         int(retrieved_ids[0] in gold_set) if retrieved_ids else 0,
            "p_at_k":     _precision_at_k(retrieved_ids, gold_set, k),
            "recall_5":   _recall_at_k(retrieved_ids, gold_set, 5),
            "recall_k":   _recall_at_k(retrieved_ids, gold_set, k),
            "mrr":        _reciprocal_rank(retrieved_ids, gold_set),
            "ndcg_5":     _ndcg_at_k(retrieved_ids, gold_set, 5),
            "ndcg_k":     _ndcg_at_k(retrieved_ids, gold_set, k),
            "latency_ms": elapsed_ms,
        }
        results.append(row)
        per_domain[domain].append(row)

    def _agg(rows: list[dict]) -> dict:
        n = len(rows)
        def avg(key: str) -> float:
            return mean(r[key] for r in rows) if rows else 0.0
        lat = [r["latency_ms"] for r in rows]
        return {
            "n": n,
            "p1":        avg("p1"),
            "p_at_k":    avg("p_at_k"),
            "recall_5":  avg("recall_5"),
            "recall_k":  avg("recall_k"),
            "mrr":       avg("mrr"),
            "ndcg_5":    avg("ndcg_5"),
            "ndcg_k":    avg("ndcg_k"),
            "latency_ms_p50":  median(lat) if lat else 0,
            "latency_ms_mean": mean(lat) if lat else 0,
            "latency_ms_max":  max(lat) if lat else 0,
            "latency_ms_std":  stdev(lat) if len(lat) > 1 else 0,
        }

    overall = _agg(results)
    domains = {d: _agg(rows) for d, rows in per_domain.items()}
    weakest = min(domains, key=lambda d: domains[d]["recall_5"]) if domains else None

    return {
        "k": k,
        "n_queries": len(results),
        "overall": overall,
        "by_domain": domains,
        "weakest_domain_recall5": weakest,
        "raw_rows": results,
    }

# Report writer
def _fmt(v: float, pct: bool = False, dec: int = 3) -> str:
    if pct:
        return f"{v * 100:.1f}%"
    return f"{v:.{dec}f}"

def write_retrieval_report(data: dict, out_path: Path) -> None:
    k = data["k"]
    o = data["overall"]
    lines: list[str] = []

    lines += [
        "# Retrieval Evaluation Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
        f"**Queries evaluated:** {data['n_queries']}  ",
        f"**K (max retrieved):** {k}",
        "",
        "---",
        "",
        "## Overall Metrics",
        "",
        "| Metric | Score |",
        "|---|---|",
        f"| P@1 | {_fmt(o['p1'], pct=True)} |",
        f"| P@{k} | {_fmt(o['p_at_k'], pct=True)} |",
        f"| Recall@5 | {_fmt(o['recall_5'], pct=True)} |",
        f"| Recall@{k} | {_fmt(o['recall_k'], pct=True)} |",
        f"| MRR | {_fmt(o['mrr'])} |",
        f"| NDCG@5 | {_fmt(o['ndcg_5'])} |",
        f"| NDCG@{k} | {_fmt(o['ndcg_k'])} |",
        "",
        "### Latency",
        "",
        "| Stat | Value |",
        "|---|---|",
        f"| p50 | {o['latency_ms_p50']:.0f} ms |",
        f"| mean | {o['latency_ms_mean']:.0f} ms |",
        f"| max | {o['latency_ms_max']:.0f} ms |",
        f"| std | {o['latency_ms_std']:.0f} ms |",
        "",
        "---",
        "",
        "## Per-Domain Breakdown",
        "",
        f"| Domain | n | P@1 | Recall@5 | Recall@{k} | MRR | NDCG@5 | NDCG@{k} | p50 ms |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for domain, m in sorted(data["by_domain"].items()):
        lines.append(
            f"| {domain} | {m['n']} "
            f"| {_fmt(m['p1'], pct=True)} "
            f"| {_fmt(m['recall_5'], pct=True)} "
            f"| {_fmt(m['recall_k'], pct=True)} "
            f"| {_fmt(m['mrr'])} "
            f"| {_fmt(m['ndcg_5'])} "
            f"| {_fmt(m['ndcg_k'])} "
            f"| {m['latency_ms_p50']:.0f} |"
        )

    weakest = data.get("weakest_domain_recall5")
    if weakest:
        lines += [
            "",
            f"> **Weakest domain (Recall@5):** {weakest}",
        ]

    lines += [
        "",
        "---",
        "",
        "## Metric Definitions",
        "",
        "| Metric | Definition |",
        "|---|---|",
        "| P@1 | Is the top-ranked chunk a gold chunk? (0 or 1) |",
        f"| P@{k} | Fraction of top-{k} results that are gold chunks |",
        "| Recall@K | Fraction of gold chunks found in top-K results |",
        "| MRR | Mean Reciprocal Rank of first gold chunk across queries |",
        "| NDCG@K | Normalised Discounted Cumulative Gain (binary relevance) |",
        "",
        "---",
        "",
        "## Improvement Suggestions",
        "",
    ]

    o_r5 = o["recall_5"]
    o_ndcg5 = o["ndcg_5"]
    o_p1 = o["p1"]

    if o_p1 < 0.75:
        lines.append("- **P@1 < 75%**: The top result is often wrong. Consider increasing `RETRIEVAL_OVERFETCH` "
                     "or improving the cross-encoder reranker threshold.")
    if o_r5 < 0.60:
        lines.append("- **Recall@5 < 60%**: Many gold chunks are outside top-5. Tune BM25 weight in RRF fusion "
                     "or increase `RETRIEVAL_TOP_K`.")
    if o_ndcg5 < 0.65:
        lines.append("- **NDCG@5 < 0.65**: Ranking quality is poor. Review reranker model or consider "
                     "a larger cross-encoder (e.g., `ms-marco-MiniLM-L-12-v2`).")
    if weakest and data["by_domain"][weakest]["recall_5"] < 0.50:
        lines.append(f"- **{weakest} recall is lowest**: Audit knowledge chunks for this domain — "
                     f"coverage gaps are the most likely cause.")

    if not any(line.startswith("-") for line in lines[-6:]):
        lines.append("- All metrics are within acceptable bounds. No immediate action required.")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Retrieval report -> {out_path.relative_to(Path(__file__).parent.parent)}")

# Entry point
async def main() -> None:
    k = DEFAULT_K
    split = "all"
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--k" and i + 1 < len(args):
            k = int(args[i + 1])
        if arg == "--split" and i + 1 < len(args):
            split = args[i + 1]

    cases = by_split(split)
    print(f"\nRetrieval benchmark  |  split={split}  k={k}  n={len(cases)}")
    await retriever.init()
    await retriever.warmup()
    print("  Running...")

    data = await run_retrieval_eval(cases, k=k)
    o = data["overall"]

    print(f"  P@1={o['p1']*100:.1f}%  "
          f"Recall@5={o['recall_5']*100:.1f}%  "
          f"Recall@{k}={o['recall_k']*100:.1f}%  "
          f"MRR={o['mrr']:.3f}  "
          f"NDCG@5={o['ndcg_5']:.3f}  "
          f"NDCG@{k}={o['ndcg_k']:.3f}")
    print(f"  Latency p50={o['latency_ms_p50']:.0f}ms  "
          f"mean={o['latency_ms_mean']:.0f}ms  "
          f"max={o['latency_ms_max']:.0f}ms")

    # Save JSON
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = RESULTS_DIR / f"retrieval_{ts}.json"
    json_path.write_text(json.dumps({k2: v for k2, v in data.items() if k2 != "raw_rows"},
                                    indent=2), encoding="utf-8")

    report_path = RESULTS_DIR / "retrieval_report.md"
    write_retrieval_report(data, report_path)

if __name__ == "__main__":
    asyncio.run(main())
