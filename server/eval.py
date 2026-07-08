"""Offline evaluation for the Seelenruh RAG pipeline. Windows-console safe (ASCII only).

Measures three things against a hand-labelled test set of 100 queries
(25 per domain, including a deliberate share of code-mixed / German /
adversarial near-neighbour queries):

  1. Retrieval precision@1   - did the top-ranked chunk match the gold chunk?
  2. Retrieval MRR (Mean Reciprocal Rank) - how high up was the gold chunk?
  3. Routing accuracy         - did the intent classifier pick the right domain?

Each is reported overall AND per-domain so weak categories don't hide
behind a strong average. Latency reported in ms (p50, mean, max).
Routing eval calls Groq; retrieval eval is fully local. Set
RERANKER_ENABLED=0 to compare bi-encoder vs bi+cross-encoder.

Run:
  cd server && .venv/Scripts/python eval.py
"""
import asyncio
import hashlib
import json
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

from ai import intent as intent_flow
from rag import retriever
from config import RETRIEVAL_TOP_K
from eval_data import TEST_CASES, by_split

EVAL_TOP_K = RETRIEVAL_TOP_K

# Fixed seed for the bootstrap resampler so the reported confidence
# intervals are reproducible across runs (the eval itself is otherwise
# deterministic apart from the LLM routing call).
BOOTSTRAP_SEED = 1729
BOOTSTRAP_SAMPLES = 1000
RESULTS_DIR = Path(__file__).parent / "results"


def _bootstrap_ci(values: list[float], samples: int = BOOTSTRAP_SAMPLES,
                  alpha: float = 0.05) -> tuple[float, float]:
    """Return (lower, upper) percentile-bootstrap CI for the mean.
    Pure-Python so no numpy/scipy dependency."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(values)
    means: list[float] = []
    for _ in range(samples):
        resample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(resample) / n)
    means.sort()
    lo_idx = int(samples * (alpha / 2))
    hi_idx = int(samples * (1 - alpha / 2)) - 1
    return (means[lo_idx], means[hi_idx])


def _testset_hash() -> str:
    """Stable identifier for the eval set — bump if test cases change.
    Useful for comparing eval runs across git revisions."""
    payload = json.dumps(
        [{"q": c["q"], "gold": sorted(c["gold"]), "domain": c["domain"]} for c in TEST_CASES],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


# TEST_CASES is imported from eval_data.py (above) — single source of truth.


async def evaluate_retrieval():
    print("=== Retrieval ===")
    p1_flags: list[int] = []
    rr_values: list[float] = []
    latencies: list[float] = []
    p1_by_domain: dict[str, list[int]] = defaultdict(list)
    rr_by_domain: dict[str, list[float]] = defaultdict(list)
    miss_examples: dict[str, list[str]] = defaultdict(list)

    for case in TEST_CASES:
        t0 = time.time()
        hits = await retriever.retrieve(case["q"], domain=case["domain"], k=EVAL_TOP_K)
        latencies.append((time.time() - t0) * 1000)

        ids = [h["id"] for h in hits]
        gold_set = set(case["gold"])
        # rank = position of the FIRST hit that matches ANY gold id
        rank = next((i + 1 for i, hid in enumerate(ids) if hid in gold_set), None)
        is_p1 = 1 if rank == 1 else 0
        rr = (1.0 / rank) if rank else 0.0

        p1_flags.append(is_p1)
        rr_values.append(rr)
        p1_by_domain[case["domain"]].append(is_p1)
        rr_by_domain[case["domain"]].append(rr)

        if not is_p1 and len(miss_examples[case["domain"]]) < 3:
            top1 = ids[0] if ids else "-"
            miss_examples[case["domain"]].append(
                f"want={sorted(gold_set)[:3]}{'+' if len(gold_set)>3 else ''} got={top1} q='{case['q'][:55]}'"
            )

    n = len(TEST_CASES)
    p1_mean = sum(p1_flags) / n
    rr_mean = sum(rr_values) / n
    p1_lo, p1_hi = _bootstrap_ci(p1_flags)
    rr_lo, rr_hi = _bootstrap_ci(rr_values)
    print(f"  Overall  P@1 = {p1_mean*100:5.1f}% [{p1_lo*100:.1f}, {p1_hi*100:.1f}] 95% CI")
    print(f"           MRR = {rr_mean:.3f} [{rr_lo:.3f}, {rr_hi:.3f}] 95% CI")
    print(f"  Latency  p50={median(latencies):.0f}ms  mean={mean(latencies):.0f}ms  max={max(latencies):.0f}ms")
    print()
    print("  Per-domain:")
    domains = sorted(p1_by_domain.keys())
    domain_breakdown: dict[str, dict] = {}
    for d in domains:
        nd = len(p1_by_domain[d])
        p1d_sum = sum(p1_by_domain[d])
        mrrd = sum(rr_by_domain[d]) / nd if nd else 0.0
        print(f"    {d:<22} P@1={p1d_sum}/{nd} = {p1d_sum/nd*100:5.1f}%   MRR={mrrd:.3f}")
        domain_breakdown[d] = {"n": nd, "p1": p1d_sum / nd, "mrr": mrrd}
    print()

    worst = min(
        domains,
        key=lambda d: sum(p1_by_domain[d]) / len(p1_by_domain[d]) if p1_by_domain[d] else 1.0,
    )
    print(f"  Weakest domain: {worst}")
    for ex in miss_examples[worst]:
        print(f"    - {ex}")
    print()

    return {
        "n": n,
        "p1_mean": p1_mean,
        "p1_ci95": [p1_lo, p1_hi],
        "mrr_mean": rr_mean,
        "mrr_ci95": [rr_lo, rr_hi],
        "latency_ms": {"p50": median(latencies), "mean": mean(latencies), "max": max(latencies)},
        "domain": domain_breakdown,
        "weakest_domain": worst,
    }


async def evaluate_routing():
    print("=== Routing (intent classifier) ===")
    # Fallback predictions (LLM call failed -> default "Mental Health") are
    # excluded from the headline metric and reported separately.
    ok_flags: list[int] = []          # 1/0 for non-fallback predictions only
    latencies: list[float] = []
    ok_by_domain: dict[str, list[int]] = defaultdict(list)
    confusions: list[tuple[str, str, str]] = []
    fallback_count = 0
    fallback_by_domain: dict[str, int] = defaultdict(int)

    for case in TEST_CASES:
        t0 = time.time()
        try:
            result = await intent_flow.detect(case["q"])
        except Exception as err:
            print(f"  ERR  {case['domain']:<20} '{case['q'][:55]}'  -> {err}")
            # Hard exceptions (not provider-fallback) — count as wrong.
            ok_by_domain[case["domain"]].append(0)
            ok_flags.append(0)
            continue
        latencies.append((time.time() - t0) * 1000)
        if result.get("fallback_used"):
            fallback_count += 1
            fallback_by_domain[case["domain"]] += 1
            continue  # excluded from accuracy denominator
        predicted = result["intent"]
        # "Panic" intent routes to Safety; treat as correct if expected was Safety
        normalised = "Safety" if predicted == "Panic" else predicted
        ok = 1 if normalised == case["domain"] else 0
        ok_flags.append(ok)
        ok_by_domain[case["domain"]].append(ok)
        if not ok and len(confusions) < 8:
            confusions.append((case["domain"], predicted, case["q"][:55]))

    n_total = len(TEST_CASES)
    n_scored = len(ok_flags)
    acc_mean = sum(ok_flags) / n_scored if n_scored else 0.0
    acc_lo, acc_hi = _bootstrap_ci(ok_flags) if n_scored else (0.0, 0.0)
    print(f"  Scored   {n_scored}/{n_total} queries  ({fallback_count} excluded — provider fallback)")
    print(f"  Overall  {acc_mean*100:5.1f}% [{acc_lo*100:.1f}, {acc_hi*100:.1f}] 95% CI")
    if latencies:
        print(f"  Latency  p50={median(latencies):.0f}ms  mean={mean(latencies):.0f}ms")
    print()
    print("  Per-domain:")
    domain_breakdown: dict[str, dict] = {}
    for d in sorted(ok_by_domain.keys()):
        ok_sum = sum(ok_by_domain[d])
        nd = len(ok_by_domain[d])
        fb = fallback_by_domain.get(d, 0)
        fb_note = f"   ({fb} fallback)" if fb else ""
        if nd:
            print(f"    {d:<22} {ok_sum}/{nd} = {ok_sum/nd*100:5.1f}%{fb_note}")
        else:
            print(f"    {d:<22} no scored queries{fb_note}")
        domain_breakdown[d] = {"n_scored": nd, "n_fallback": fb,
                               "accuracy": (ok_sum / nd) if nd else None}
    if confusions:
        print()
        print("  Sample confusions:")
        for exp, pred, q in confusions:
            print(f"    expected={exp:<20} predicted={pred:<20} '{q}'")
    if fallback_count:
        print()
        print(f"  NOTE  {fallback_count} fallback predictions excluded from accuracy."
              f" Worst-case (all fallbacks wrong): {sum(ok_flags) / n_total * 100:.1f}%."
              f" Best-case (all fallbacks right): "
              f"{(sum(ok_flags) + fallback_count) / n_total * 100:.1f}%.")
    print()

    return {
        "n_total": n_total,
        "n_scored": n_scored,
        "n_fallback": fallback_count,
        "fallback_by_domain": dict(fallback_by_domain),
        "accuracy_mean": acc_mean,
        "accuracy_ci95": [acc_lo, acc_hi],
        "latency_ms": {"p50": median(latencies) if latencies else 0, "mean": mean(latencies) if latencies else 0},
        "domain": domain_breakdown,
    }


def _save_run(retrieval_out: dict, routing_out: dict, split: str = "all") -> Path:
    """Snapshot this run's headline numbers to results/ so future runs
    can be diff'd against a known-good revision."""
    RESULTS_DIR.mkdir(exist_ok=True)
    record = {
        "tool": "eval.py",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "split": split,
        "testset_hash": _testset_hash(),
        "n_queries": len(TEST_CASES),
        "bootstrap": {"samples": BOOTSTRAP_SAMPLES, "seed": BOOTSTRAP_SEED},
        "python": sys.version.split()[0],
        "retrieval": retrieval_out,
        "routing": routing_out,
    }
    suffix = f"_{split}" if split != "all" else ""
    out_path = RESULTS_DIR / f"eval{suffix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return out_path


async def main():
    # `--split test` (default) = held-out 50; `dev` = tuning 50; `all` = 100.
    split = "test"
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--split" and i + 1 < len(sys.argv) - 1:
            split = sys.argv[i + 2]
            break
    global TEST_CASES
    TEST_CASES = by_split(split)
    print(f"\nSeelenruh evaluation - {len(TEST_CASES)} test queries  (split={split})")
    by_dom: dict[str, int] = defaultdict(int)
    for c in TEST_CASES:
        by_dom[c["domain"]] += 1
    print("  Per-domain split:", ", ".join(f"{d}={by_dom[d]}" for d in sorted(by_dom)))
    print()
    print(f"  Testset hash: {_testset_hash()}  (bump if test cases change)")
    print(f"  Bootstrap: {BOOTSTRAP_SAMPLES} resamples, seed={BOOTSTRAP_SEED}")
    print()
    await retriever.init()
    await retriever.warmup()
    print()
    retrieval_out = await evaluate_retrieval()
    routing_out = await evaluate_routing()
    out_path = _save_run(retrieval_out, routing_out, split=split)
    print(f"  Saved structured run to: {out_path.relative_to(Path(__file__).parent)}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
