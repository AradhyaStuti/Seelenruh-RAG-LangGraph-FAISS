"""
run_all.py
----------
Master runner for the Seelenruh benchmark suite.

Runs all offline benchmarks in order and generates four report files
in bench/reports/:

  benchmark_report.md    — persona quality (keyword coverage, violations)
  retrieval_report.md    — Recall@K, Precision@K, NDCG, MRR
  hallucination_report.md — fake sections, fake schemes, helplines, guarantees
  latency_report.md      — per-stage retrieval latency at p50/p90/p99

Each module can also be run independently:
  python -m bench.bench_retrieval
  python -m bench.bench_hallucination --probe
  python -m bench.bench_latency
  python -m bench.bench_personas

Run:
  cd server && .venv/Scripts/python -m bench.run_all
  cd server && .venv/Scripts/python -m bench.run_all --skip-llm --quick
"""
from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def _header(title: str) -> None:
    w = 60
    print(f"\n{'=' * w}")
    print(f"  {title}")
    print(f"{'=' * w}")


def _elapsed(t0: float) -> str:
    return f"{time.time() - t0:.1f}s"


async def run_retrieval(split: str = "all", k: int = 10) -> bool:
    _header("1/4  Retrieval Evaluation")
    try:
        from rag import retriever
        await retriever.init()
        await retriever.warmup()
        print()

        from bench.bench_retrieval import run_retrieval_eval, write_retrieval_report
        from eval_data import by_split
        cases = by_split(split)
        print(f"  Split={split}  n={len(cases)}  K={k}")
        t0 = time.time()
        data = await run_retrieval_eval(cases, k=k)
        o = data["overall"]
        print(f"  P@1={o['p1']*100:.1f}%  "
              f"Recall@5={o['recall_5']*100:.1f}%  "
              f"NDCG@5={o['ndcg_5']:.3f}  "
              f"MRR={o['mrr']:.3f}  ({_elapsed(t0)})")
        write_retrieval_report(data, REPORTS_DIR / "retrieval_report.md")
        return True
    except Exception as err:
        print(f"  ERROR: {err}")
        return False


def run_hallucination() -> bool:
    _header("2/4  Hallucination Detection")
    try:
        from bench.bench_hallucination import run_static_probes, write_hallucination_report
        t0 = time.time()
        result = run_static_probes()
        print(f"  Scanned={result.total_responses}  "
              f"Passed={len(result.passed)}  "
              f"Flagged={len(set(result.failed))}  "
              f"Rate={result.hallucination_rate*100:.1f}%  ({_elapsed(t0)})")
        write_hallucination_report(result, REPORTS_DIR / "hallucination_report.md")
        return True
    except Exception as err:
        print(f"  ERROR: {err}")
        return False


async def run_latency(n_runs: int = 50, skip_llm: bool = False) -> bool:
    _header("3/4  Latency Profiling")
    try:
        from bench.bench_latency import _profile_retrieval, _stats, write_latency_report
        # retriever already initialised by run_retrieval()
        t0 = time.time()
        print(f"  Profiling {n_runs} retrieval calls...")
        raw = await _profile_retrieval(n_runs)
        retrieval_stats = {stage: _stats(values) for stage, values in raw.items()}
        total = retrieval_stats.get("total_ms", {})
        print(f"  Total p50={total.get('p50', 0)}ms  "
              f"p90={total.get('p90', 0)}ms  ({_elapsed(t0)})")

        llm_data: dict = {}
        if not skip_llm:
            import os
            if os.environ.get("GROQ_API_KEY"):
                from bench.bench_latency import _profile_llm_latency
                from config import GROQ_MODEL_SMART, GROQ_MODEL_FAST
                print("  Profiling LLM latency...")
                fast = await _profile_llm_latency(GROQ_MODEL_FAST, n_samples=5)
                smart = await _profile_llm_latency(GROQ_MODEL_SMART, n_samples=5)
                llm_data = {
                    "fast":  {**fast,  "name": GROQ_MODEL_FAST,  "role": "Classifier (8B)"},
                    "smart": {**smart, "name": GROQ_MODEL_SMART, "role": "Composer (70B)"},
                }
            else:
                print("  Skipping LLM (GROQ_API_KEY not set)")

        data = {
            "n_runs": n_runs,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "retrieval": retrieval_stats,
            "llm": llm_data,
        }
        write_latency_report(data, REPORTS_DIR / "latency_report.md")
        return True
    except Exception as err:
        print(f"  ERROR: {err}")
        import traceback
        traceback.print_exc()
        return False


def run_personas() -> bool:
    _header("4/4  Persona Quality (Dataset Self-Check)")
    try:
        from bench.bench_personas import evaluate_persona, write_benchmark_report
        from bench.bench_data import UMANG_CASES, AAROGYA_CASES, USHA_SCENARIOS, RAKSHA_CASES

        t0 = time.time()
        domain_cases = {
            "Legal":              UMANG_CASES,
            "Government Schemes": AAROGYA_CASES,
            "Mental Health":      USHA_SCENARIOS,
            "Safety":             RAKSHA_CASES,
        }
        results: dict[str, dict] = {}
        for domain, cases in domain_cases.items():
            results[domain] = evaluate_persona(cases, responses=None)
            o = results[domain]["overall"]
            print(f"  {domain:<22} pass={o['pass_rate']*100:.1f}%  "
                  f"violations={o['total_violations']}")

        write_benchmark_report(results, mode="dataset-self-check",
                               out_path=REPORTS_DIR / "benchmark_report.md")
        print(f"  ({_elapsed(t0)})")
        return True
    except Exception as err:
        print(f"  ERROR: {err}")
        return False


async def main() -> None:
    args = sys.argv[1:]
    skip_llm = "--skip-llm" in args
    quick = "--quick" in args

    n_runs = 20 if quick else 50
    split = "all"
    k = 10

    print("\nSeelenruh Benchmark Suite")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  quick={quick}  skip_llm={skip_llm}  n_latency_runs={n_runs}")

    t_suite = time.time()
    statuses: dict[str, bool] = {}

    statuses["retrieval"]      = await run_retrieval(split=split, k=k)
    statuses["hallucination"]  = run_hallucination()
    statuses["latency"]        = await run_latency(n_runs=n_runs, skip_llm=skip_llm)
    statuses["personas"]       = run_personas()

    # Final summary
    w = 60
    print(f"\n{'=' * w}")
    print("  SUMMARY")
    print(f"{'=' * w}")
    all_ok = True
    for name, ok in statuses.items():
        mark = "OK  " if ok else "FAIL"
        print(f"  [{mark}]  {name}")
        if not ok:
            all_ok = False

    print("\n  Reports written to: bench/reports/")
    for md in sorted(REPORTS_DIR.glob("*.md")):
        print(f"    {md.name}")

    total_elapsed = time.time() - t_suite
    print(f"\n  Total time: {total_elapsed:.1f}s")
    print(f"  Status: {'ALL PASSED' if all_ok else 'SOME FAILED'}\n")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
