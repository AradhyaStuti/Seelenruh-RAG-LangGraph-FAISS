"""
bench_latency.py
----------------
Performance profiling for the Seelenruh retrieval pipeline.

Measures per-stage latency at percentiles (p50, p90, p99) for:
  embed_ms     — query -> dense vector (sentence-transformer)
  faiss_ms     — FAISS approximate nearest-neighbour search
  bm25_ms      — BM25 sparse retrieval
  rerank_ms    — cross-encoder reranking
  total_ms     — end-to-end retrieve() wall time

The retrieval pipeline is CPU-only (no API key required). Runs are
repeated N times (default 50) across sample queries from all four domains
to get stable percentile estimates.

LLM and memory latencies require a live Groq API key and are optional.
Pass --skip-llm to benchmark retrieval only.

Run:
  cd server && .venv/Scripts/python -m bench.bench_latency
  cd server && .venv/Scripts/python -m bench.bench_latency --n 100 --skip-llm
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, quantiles, stdev

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

RESULTS_DIR = Path(__file__).parent / "reports"
RESULTS_DIR.mkdir(exist_ok=True)

# Sample queries (2 per domain × 4 domains = 8 seeds, repeated N times)
_SAMPLE_QUERIES: list[tuple[str, str]] = [
    ("Legal",              "How do I file an FIR against someone who assaulted me"),
    ("Legal",              "My employer has not paid my salary for 2 months"),
    ("Government Schemes", "Am I eligible for PM-JAY Ayushman Bharat health scheme"),
    ("Government Schemes", "How do I apply for PM Awas Yojana rural housing"),
    ("Mental Health",      "I feel completely hopeless and cannot get out of bed"),
    ("Mental Health",      "I have been having panic attacks at work"),
    ("Safety",             "Someone transferred money from my UPI account without permission"),
    ("Safety",             "My husband is violent — I need immediate help"),
]

# Retrieval latency profiler
async def _profile_retrieval(n_runs: int) -> dict[str, list[float]]:
    """
    Run retrieve() N times across sample queries and collect per-stage
    latencies from the structured logs — or fall back to wall-time only.

    Returns a dict: stage_name -> list[float] of millisecond timings.
    """
    from rag import retriever
    from rag.retriever import _store, _bm25_index, _BM25_AVAILABLE, embedder, reranker

    stages: dict[str, list[float]] = defaultdict(list)

    # Run one warm-up pass to load caches
    await retriever.retrieve("test warmup", domain="Legal", k=5)

    queries = (_SAMPLE_QUERIES * ((n_runs // len(_SAMPLE_QUERIES)) + 1))[:n_runs]

    for query, domain in queries:
        t_total = time.perf_counter()

        # embed
        t_embed = time.perf_counter()
        import asyncio as _asyncio
        qv = await _asyncio.to_thread(embedder.embed_one, f"query: {query}")
        embed_ms = (time.perf_counter() - t_embed) * 1000
        stages["embed_ms"].append(embed_ms)

        from config import RETRIEVAL_TOP_K, RETRIEVAL_OVERFETCH
        fetch_k = getattr(
            __import__("config"), f"RETRIEVAL_OVERFETCH_{domain.upper().replace(' ', '_')}",
            RETRIEVAL_OVERFETCH,
        ) if False else RETRIEVAL_OVERFETCH  # use default overfetch

        # faiss
        t_faiss = time.perf_counter()
        faiss_hits = _store.search(qv, k=fetch_k, domain=domain)
        faiss_ms = (time.perf_counter() - t_faiss) * 1000
        stages["faiss_ms"].append(faiss_ms)

        # bm25
        if _BM25_AVAILABLE and _bm25_index is not None:
            from rag.retriever import _bm25_search
            t_bm25 = time.perf_counter()
            _bm25_search(query, k=fetch_k, domain=domain)
            bm25_ms = (time.perf_counter() - t_bm25) * 1000
        else:
            bm25_ms = 0.0
        stages["bm25_ms"].append(bm25_ms)

        # rerank
        from rag.retriever import _rrf_fuse
        candidates = _rrf_fuse(faiss_hits, []) if not _BM25_AVAILABLE else faiss_hits
        candidates = candidates[:fetch_k]
        if reranker.is_enabled() and len(candidates) > RETRIEVAL_TOP_K:
            t_rerank = time.perf_counter()
            await reranker.rerank(query, candidates, k=RETRIEVAL_TOP_K)
            rerank_ms = (time.perf_counter() - t_rerank) * 1000
        else:
            rerank_ms = 0.0
        stages["rerank_ms"].append(rerank_ms)

        total_ms = (time.perf_counter() - t_total) * 1000
        stages["total_ms"].append(total_ms)

    return dict(stages)

async def _profile_llm_latency(model_name: str, n_samples: int = 5) -> dict:
    """
    Profile a single LLM call latency (non-streaming).
    Returns mean/p50/p90 in ms. Requires GROQ_API_KEY in environment.
    """
    from ai.provider import chat

    PROMPT = [
        {"role": "system", "content": "You are a helpful assistant. Reply in one sentence."},
        {"role": "user", "content": "What is the capital of India?"},
    ]
    times: list[float] = []
    for _ in range(n_samples):
        t0 = time.perf_counter()
        try:
            await chat(model=model_name, temperature=0.0, max_tokens=30, messages=PROMPT)
        except Exception:
            continue
        times.append((time.perf_counter() - t0) * 1000)

    if not times:
        return {"mean": None, "p50": None, "p90": None, "samples": 0}
    qs = quantiles(times, n=10) if len(times) >= 10 else None
    return {
        "mean": mean(times),
        "p50": median(times),
        "p90": qs[8] if qs else max(times),
        "samples": len(times),
    }

# Stats helper
def _stats(values: list[float]) -> dict:
    if not values:
        return {"p50": 0, "p90": 0, "p99": 0, "mean": 0, "max": 0, "std": 0, "n": 0}
    n = len(values)
    sorted_v = sorted(values)
    def _pct(p: float) -> float:
        idx = int(p / 100 * n)
        return sorted_v[min(idx, n - 1)]
    return {
        "p50": round(_pct(50), 1),
        "p90": round(_pct(90), 1),
        "p99": round(_pct(99), 1),
        "mean": round(mean(values), 1),
        "max": round(max(values), 1),
        "std": round(stdev(values) if n > 1 else 0, 1),
        "n": n,
    }

# Report writer
def write_latency_report(data: dict, out_path: Path) -> None:
    lines: list[str] = []
    lines += [
        "# Latency Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
        f"**Runs per stage:** {data.get('n_runs', '?')}  ",
        "**Platform:** CPU (no GPU)",
        "",
        "---",
        "",
        "## Retrieval Pipeline — Per-Stage Latency",
        "",
        "| Stage | p50 (ms) | p90 (ms) | p99 (ms) | mean (ms) | max (ms) |",
        "|---|---|---|---|---|---|",
    ]

    stage_labels = {
        "embed_ms": "Embedding (query -> vector)",
        "faiss_ms": "FAISS ANN search",
        "bm25_ms":  "BM25 sparse retrieval",
        "rerank_ms": "Cross-encoder reranking",
        "total_ms": "**Total retrieve()**",
    }

    retrieval_stats = data.get("retrieval", {})
    for key, label in stage_labels.items():
        s = retrieval_stats.get(key, {})
        if not s:
            continue
        lines.append(
            f"| {label} | {s['p50']} | {s['p90']} | {s['p99']} "
            f"| {s['mean']} | {s['max']} |"
        )

    bm25_mean = retrieval_stats.get("bm25_ms", {}).get("mean", 0)
    if bm25_mean == 0:
        lines += [
            "",
            "> **BM25:** All zeros — BM25 index not loaded. "
            "Run `python prebuild_rag.py` to enable hybrid retrieval.",
        ]

    rerank_mean = retrieval_stats.get("rerank_ms", {}).get("mean", 0)
    if rerank_mean == 0:
        lines += [
            "",
            "> **Reranker:** All zeros — either disabled (`RERANKER_ENABLED=0`) "
            "or candidate count ≤ TOP_K so reranking was skipped.",
        ]

    lines += [
        "",
        "---",
        "",
        "## LLM Latency (Groq API)",
        "",
    ]

    llm_data = data.get("llm", {})
    if llm_data:
        lines += [
            "| Model | Role | p50 (ms) | p90 (ms) | mean (ms) | Samples |",
            "|---|---|---|---|---|---|",
        ]
        for model_key, meta in llm_data.items():
            if meta.get("p50") is None:
                lines.append(f"| {meta['name']} | {meta['role']} | N/A | N/A | N/A | 0 |")
            else:
                lines.append(
                    f"| {meta['name']} | {meta['role']} "
                    f"| {meta['p50']:.0f} | {meta['p90']:.0f} "
                    f"| {meta['mean']:.0f} | {meta['samples']} |"
                )
    else:
        lines += [
            "> LLM latency not measured (run without `--skip-llm` and set `GROQ_API_KEY`).",
            "",
        ]

    lines += [
        "",
        "---",
        "",
        "## Percentile Distributions",
        "",
        "### Total Retrieval Latency (retrieve())",
        "",
    ]

    total = retrieval_stats.get("total_ms", {})
    if total:
        lines += [
            f"- p50 (median) : **{total['p50']} ms**",
            f"- p90          : **{total['p90']} ms**",
            f"- p99          : **{total['p99']} ms**",
            f"- Std dev      : {total['std']} ms",
            f"- Max observed : {total['max']} ms",
        ]

    lines += [
        "",
        "---",
        "",
        "## Improvement Suggestions",
        "",
    ]

    total_p90 = total.get("p90", 0) if total else 0
    embed_mean = retrieval_stats.get("embed_ms", {}).get("mean", 0)
    faiss_mean = retrieval_stats.get("faiss_ms", {}).get("mean", 0)
    rerank_p90 = retrieval_stats.get("rerank_ms", {}).get("p90", 0)

    if total_p90 > 200:
        lines.append("- **Total p90 > 200ms**: This may be noticeable to users. Profile the "
                     "dominant stage below and address it first.")
    if embed_mean > 50:
        lines.append("- **Embedding > 50ms mean**: Consider switching from CPU inference to "
                     "a smaller model or enabling GPU (`CUDA_VISIBLE_DEVICES=0`).")
    if rerank_p90 > 150:
        lines.append("- **Reranking p90 > 150ms**: The cross-encoder is the bottleneck. "
                     "Try `ms-marco-MiniLM-L-6-v2` (faster) over `L-12` variants, or "
                     "reduce `RETRIEVAL_OVERFETCH` to send fewer candidates.")
    if faiss_mean > 30:
        lines.append("- **FAISS p50 > 30ms**: Index may be large. Consider reducing "
                     "embedding dimensions or using IVF-PQ indexing for faster search.")
    if not any(line.startswith("-") for line in lines[-8:]):
        lines.append("- All stages are within acceptable bounds. No immediate optimisations needed.")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Latency report -> {out_path.relative_to(Path(__file__).parent.parent)}")

# Entry point
async def main() -> None:
    n_runs = 50
    skip_llm = False
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--n" and i + 1 < len(args):
            n_runs = int(args[i + 1])
        if arg == "--skip-llm":
            skip_llm = True

    print(f"\nLatency benchmark  |  n_runs={n_runs}  skip_llm={skip_llm}")

    from rag import retriever as _retriever
    await _retriever.init()
    await _retriever.warmup()

    print("  Profiling retrieval stages...")
    raw_stages = await _profile_retrieval(n_runs)

    retrieval_stats = {stage: _stats(values) for stage, values in raw_stages.items()}
    total = retrieval_stats.get("total_ms", {})
    if total:
        print(f"  Retrieval p50={total['p50']}ms  p90={total['p90']}ms  p99={total['p99']}ms")

    llm_data: dict = {}
    if not skip_llm and os.environ.get("GROQ_API_KEY"):
        from config import GROQ_MODEL_SMART, GROQ_MODEL_FAST
        print("  Profiling LLM latency (5 samples each)...")
        fast_stats = await _profile_llm_latency(GROQ_MODEL_FAST, n_samples=5)
        smart_stats = await _profile_llm_latency(GROQ_MODEL_SMART, n_samples=5)
        llm_data = {
            "fast": {**fast_stats, "name": GROQ_MODEL_FAST, "role": "Classifier (8B)"},
            "smart": {**smart_stats, "name": GROQ_MODEL_SMART, "role": "Composer (70B)"},
        }
        if fast_stats.get("p50"):
            print(f"  LLM 8B  p50={fast_stats['p50']:.0f}ms  mean={fast_stats['mean']:.0f}ms")
        if smart_stats.get("p50"):
            print(f"  LLM 70B p50={smart_stats['p50']:.0f}ms  mean={smart_stats['mean']:.0f}ms")
    elif not skip_llm:
        print("  Skipping LLM latency (GROQ_API_KEY not set)")

    data = {
        "n_runs": n_runs,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "retrieval": retrieval_stats,
        "llm": llm_data,
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = RESULTS_DIR / f"latency_{ts}.json"
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    report_path = RESULTS_DIR / "latency_report.md"
    write_latency_report(data, report_path)

if __name__ == "__main__":
    asyncio.run(main())
