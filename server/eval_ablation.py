"""Ablation study for the Seelenruh retrieval pipeline.

We claim three design choices matter. This script measures whether they
actually do, against the same 100-query test set used by `eval.py`:

  - Cross-encoder re-rank vs bi-encoder only
  - Persona-domain filter vs corpus-wide search
  - top-k = 1 vs 3 vs 10 (recall-precision curve)

Each variant runs end-to-end on the same query set so the deltas are
directly attributable to the design knob being changed. Output is a
single table with the headline metrics so the result is easy to cite.

Run:
  cd server && .venv/Scripts/python eval_ablation.py
"""
import asyncio
import time
from statistics import mean, median

from rag import embedder, reranker
from rag.knowledge import CHUNKS
from rag.store import VectorStore
from config import RETRIEVAL_OVERFETCH

from eval_data import TEST_CASES, by_split


_store = VectorStore()


async def _ensure_index() -> None:
    if _store.size() and _store.size() == len(CHUNKS):
        return
    if _store.load() and _store.size() == len(CHUNKS):
        return
    print(f"[ablation] building fresh index for {len(CHUNKS)} chunks...", flush=True)
    texts = [f"passage: {c['topic']}\n{c['text']}" for c in CHUNKS]
    vectors = await asyncio.to_thread(embedder.embed_many, texts)
    _store.build(CHUNKS, vectors)


async def _retrieve_variant(
    query: str,
    *,
    domain: str | None,
    k: int,
    use_reranker: bool,
    use_domain_filter: bool,
) -> list[dict]:
    """Single retrieval pass with explicit knobs — no caching tricks, so each
    variant pays its real cost."""
    qv = await asyncio.to_thread(embedder.embed_one, f"query: {query}")
    eff_domain = domain if use_domain_filter else None
    fetch_k = max(k, RETRIEVAL_OVERFETCH) if use_reranker else k
    candidates = _store.search(qv, k=fetch_k, domain=eff_domain)
    if use_reranker and len(candidates) > k:
        return await reranker.rerank(query, candidates, k=k)
    return candidates[:k]


async def run_variant(name: str, *, use_reranker: bool, use_domain_filter: bool, k: int) -> dict:
    p1_hits, rr_total, latencies = 0, 0.0, []
    cross_domain_top1 = 0  # times the top-1 came from a different domain than expected

    for case in TEST_CASES:
        t0 = time.time()
        hits = await _retrieve_variant(
            case["q"],
            domain=case["domain"],
            k=k,
            use_reranker=use_reranker,
            use_domain_filter=use_domain_filter,
        )
        latencies.append((time.time() - t0) * 1000)

        ids = [h["id"] for h in hits]
        domains_seen = [h.get("domain") for h in hits]
        gold_set = set(case["gold"])
        rank = next((i + 1 for i, hid in enumerate(ids) if hid in gold_set), None)
        if rank == 1:
            p1_hits += 1
        if rank:
            rr_total += 1 / rank
        if hits and domains_seen[0] != case["domain"]:
            cross_domain_top1 += 1

    n = len(TEST_CASES)
    return {
        "name": name,
        "p1": p1_hits / n,
        "mrr": rr_total / n,
        "p50_ms": median(latencies),
        "mean_ms": mean(latencies),
        "cross_domain_top1": cross_domain_top1,
    }


def _row(r: dict) -> str:
    return (
        f"  {r['name']:<46}"
        f"  P@1={r['p1']*100:5.1f}%"
        f"  MRR={r['mrr']:.3f}"
        f"  p50={r['p50_ms']:5.0f}ms"
        f"  cross-domain top1={r['cross_domain_top1']:>3}"
    )


async def main():
    import sys
    split = "test"
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--split" and i + 1 < len(sys.argv) - 1:
            split = sys.argv[i + 2]
            break
    global TEST_CASES
    TEST_CASES = by_split(split)
    print(f"\nSeelenruh ablation - {len(TEST_CASES)} queries  (split={split})\n")
    await _ensure_index()
    await asyncio.to_thread(embedder.warmup)
    if reranker.is_enabled():
        await asyncio.to_thread(reranker.warmup)
    print()

    # The full system (production default, k=5) vs successive knockouts and
    # k-sweep. k=5 is what graph.py ships in production after the eval
    # showed k=3 was over-aggressive on rerank.
    variants = [
        # name, use_reranker, use_domain_filter, k
        ("FULL SYSTEM (rerank + domain filter, k=5)  PROD", True, True, 5),
        ("- k=3 (over-aggressive rerank pruning)", True, True, 3),
        ("- k=10 (recovers most precision via larger context)", True, True, 10),
        ("- no cross-encoder re-rank (bi-encoder only, k=5)", False, True, 5),
        ("- no persona-domain filter (whole corpus, k=5)", True, False, 5),
        ("- neither (bi-encoder, whole corpus, k=5)", False, False, 5),
        ("- top-1 only (rerank + filter)", True, True, 1),
    ]

    print("=== Ablation table ===\n")
    results = []
    for name, rer, dom, k in variants:
        r = await run_variant(name, use_reranker=rer, use_domain_filter=dom, k=k)
        results.append(r)
        print(_row(r))
    print()

    by_name = {r["name"]: r for r in results}
    full   = by_name["FULL SYSTEM (rerank + domain filter, k=5)  PROD"]
    no_rer = by_name["- no cross-encoder re-rank (bi-encoder only, k=5)"]
    no_dom = by_name["- no persona-domain filter (whole corpus, k=5)"]
    none   = by_name["- neither (bi-encoder, whole corpus, k=5)"]
    print("=== Headline deltas vs full system ===\n")
    d_rer_p1 = (full["p1"] - no_rer["p1"]) * 100
    d_rer_mrr = full["mrr"] - no_rer["mrr"]
    d_dom_p1 = (full["p1"] - no_dom["p1"]) * 100
    d_dom_mrr = full["mrr"] - no_dom["mrr"]
    d_none_p1 = (full["p1"] - none["p1"]) * 100
    d_none_mrr = full["mrr"] - none["mrr"]
    print(f"  Re-ranker contribution      : {d_rer_p1:+5.1f} pp P@1   {d_rer_mrr:+.3f} MRR")
    print(f"  Persona-filter contribution : {d_dom_p1:+5.1f} pp P@1   {d_dom_mrr:+.3f} MRR  "
          f"({no_dom['cross_domain_top1']} cross-domain top-1 leaks without it)")
    print(f"  Both off vs FULL            : {d_none_p1:+5.1f} pp P@1   {d_none_mrr:+.3f} MRR")
    print()


if __name__ == "__main__":
    asyncio.run(main())
