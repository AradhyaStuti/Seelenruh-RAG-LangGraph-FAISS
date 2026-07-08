"""Paired significance test for the FULL vs VANILLA_RAG retrieval delta.

Reports:
  - McNemar exact two-sided p on the discordant pairs.
  - Paired bootstrap 95% CI on the P@1 difference (10k resamples, seed 1729).

Run:
  .venv/Scripts/python eval_significance.py
"""
import asyncio
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from rag import embedder, reranker
from rag.knowledge import CHUNKS
from rag.store import VectorStore
from config import RETRIEVAL_OVERFETCH, RETRIEVAL_TOP_K
from eval_data import by_split


BOOTSTRAP_SEED = 1729
BOOTSTRAP_SAMPLES = 10_000

RESULTS_DIR = Path(__file__).parent / "results"

_store = VectorStore()


async def _ensure_index() -> None:
    if _store.size() and _store.size() == len(CHUNKS):
        return
    if _store.load() and _store.size() == len(CHUNKS):
        return
    print(f"[sig] building fresh index for {len(CHUNKS)} chunks...", flush=True)
    texts = [f"passage: {c['topic']}\n{c['text']}" for c in CHUNKS]
    vectors = await asyncio.to_thread(embedder.embed_many, texts)
    _store.build(CHUNKS, vectors)


async def _retrieve(query: str, *, domain: str | None, k: int, use_reranker: bool) -> list[dict]:
    qv = await asyncio.to_thread(embedder.embed_one, f"query: {query}")
    fetch_k = max(k, RETRIEVAL_OVERFETCH) if use_reranker else k
    candidates = _store.search(qv, k=fetch_k, domain=domain)
    if use_reranker and len(candidates) > k:
        return await reranker.rerank(query, candidates, k=k)
    return candidates[:k]


async def _per_query_pass(cases: list[dict], *, use_domain_filter: bool) -> list[int]:
    flags: list[int] = []
    for case in cases:
        dom = case["domain"] if use_domain_filter else None
        hits = await _retrieve(case["q"], domain=dom, k=RETRIEVAL_TOP_K, use_reranker=False)
        top1 = hits[0]["id"] if hits else None
        flags.append(1 if top1 in set(case["gold"]) else 0)
    return flags


def _mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value via the binomial on the discordant
    pairs. Under H0, each discordant pair is equally likely to favour
    either system; the count of (FULL-wins discordants) is Binomial(n=b+c, p=0.5).
    Pure Python — no scipy."""
    n = b + c
    if n == 0:
        return 1.0
    # Build pmf, then two-sided p = sum of pmf for values at least as extreme as min(b, c).
    from math import comb
    k_obs = min(b, c)
    pmf = [comb(n, i) * (0.5 ** n) for i in range(n + 1)]
    p_two_sided = sum(p for i, p in enumerate(pmf) if min(i, n - i) <= k_obs)
    return min(1.0, p_two_sided)


def _paired_bootstrap_ci(full: list[int], vanilla: list[int],
                         alpha: float = 0.05,
                         samples: int = BOOTSTRAP_SAMPLES,
                         seed: int = BOOTSTRAP_SEED) -> tuple[float, float, float]:
    """Resample query indices with replacement; recompute the paired delta
    on each resample. Returns (mean_delta_pp, lo_pp, hi_pp)."""
    assert len(full) == len(vanilla)
    n = len(full)
    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(samples):
        idxs = [rng.randrange(n) for _ in range(n)]
        f = sum(full[i] for i in idxs) / n
        v = sum(vanilla[i] for i in idxs) / n
        deltas.append((f - v) * 100)
    deltas.sort()
    lo_idx = int(samples * (alpha / 2))
    hi_idx = int(samples * (1 - alpha / 2)) - 1
    return (sum(deltas) / samples, deltas[lo_idx], deltas[hi_idx])


async def main():
    split = "test"
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--split" and i + 1 < len(sys.argv) - 1:
            split = sys.argv[i + 2]
    cases = by_split(split)
    print(f"\nSeelenruh significance test — FULL vs VANILLA_RAG, split={split}, n={len(cases)}\n")
    await _ensure_index()
    await asyncio.to_thread(embedder.warmup)
    print()

    t0 = time.time()
    full_flags = await _per_query_pass(cases, use_domain_filter=True)
    vanilla_flags = await _per_query_pass(cases, use_domain_filter=False)
    elapsed = (time.time() - t0) * 1000

    n = len(cases)
    full_correct = sum(full_flags)
    vanilla_correct = sum(vanilla_flags)
    # b = FULL passed, VANILLA failed; c = VANILLA passed, FULL failed.
    b = sum(1 for f, v in zip(full_flags, vanilla_flags) if f == 1 and v == 0)
    c = sum(1 for f, v in zip(full_flags, vanilla_flags) if f == 0 and v == 1)
    concordant = n - b - c

    p_mcnemar = _mcnemar_exact(b, c)
    mean_delta, lo, hi = _paired_bootstrap_ci(full_flags, vanilla_flags)

    print(f"  ran in {elapsed:.0f}ms\n")
    print(f"  FULL    : {full_correct}/{n} = {full_correct/n*100:.1f}% P@1")
    print(f"  VANILLA : {vanilla_correct}/{n} = {vanilla_correct/n*100:.1f}% P@1\n")
    print(f"  Discordant pairs : FULL-only={b}  VANILLA-only={c}  (concordant={concordant})")
    print(f"  Observed delta   : {(full_correct - vanilla_correct) / n * 100:+.1f} pp")
    print(f"  Paired bootstrap : mean={mean_delta:+.2f} pp, 95% CI = [{lo:+.2f}, {hi:+.2f}]")
    print(f"  McNemar exact p  : {p_mcnemar:.4f}  ({'significant at 0.05' if p_mcnemar < 0.05 else 'NOT significant at 0.05'})")
    print()

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"significance_{split}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps({
        "tool": "eval_significance.py",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "split": split,
        "n": n,
        "full_correct": full_correct,
        "vanilla_correct": vanilla_correct,
        "discordant": {"full_only": b, "vanilla_only": c, "concordant": concordant},
        "observed_delta_pp": (full_correct - vanilla_correct) / n * 100,
        "bootstrap": {
            "samples": BOOTSTRAP_SAMPLES, "seed": BOOTSTRAP_SEED,
            "mean_pp": mean_delta, "ci95_pp": [lo, hi],
        },
        "mcnemar_exact_p": p_mcnemar,
    }, indent=2), encoding="utf-8")
    print(f"  Saved to: {out_path.relative_to(Path(__file__).parent)}\n")


if __name__ == "__main__":
    asyncio.run(main())
