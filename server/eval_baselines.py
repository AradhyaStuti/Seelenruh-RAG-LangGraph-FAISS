"""Baseline comparison on TEST_HELDOUT.

Systems:
  A. FULL              bi-encoder + persona-domain filter (production).
  B. VANILLA_RAG       bi-encoder only, no filter.
  C. SINGLE_PERSONA    rerank on, no persona-domain filter.
  D. ZERO_SHOT_LLM     no RAG; keyword-coverage on a 6-probe set.

Run:
  .venv/Scripts/python eval_baselines.py
  .venv/Scripts/python eval_baselines.py --split dev
  .venv/Scripts/python eval_baselines.py --skip-llm
"""
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

from rag import embedder, reranker
from rag.knowledge import CHUNKS
from rag.store import VectorStore
from config import RETRIEVAL_OVERFETCH
from eval_data import by_split


KEYWORD_PROBES = [
    {"q": "How do I file an RTI application for a central ministry",
     "domain": "Legal",
     "any": ["Section 6", "Right to Information", "RTI Act"]},
    {"q": "My cheque bounced what's the legal process",
     "domain": "Legal",
     "any": ["Section 138", "Negotiable Instruments", "NI Act"]},
    {"q": "I'm a small farmer how do I get PM Kisan",
     "domain": "Government Schemes",
     "any": ["PM-KISAN", "PM Kisan", "6000", "₹6,000"]},
    {"q": "Someone is following me right now and I'm scared",
     "domain": "Safety",
     "any": ["112", "100", "1091"]},
    {"q": "I just got scammed on a loan app",
     "domain": "Safety",
     "any": ["1930", "cybercrime.gov.in"]},
    {"q": "Heart attack symptoms what to do right now",
     "domain": "Safety",
     "any": ["108", "102", "112"]},
]


_store = VectorStore()
RESULTS_DIR = Path(__file__).parent / "results"


async def _ensure_index() -> None:
    if _store.size() and _store.size() == len(CHUNKS):
        return
    if _store.load() and _store.size() == len(CHUNKS):
        return
    print(f"[baselines] building fresh index for {len(CHUNKS)} chunks...", flush=True)
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


async def run_retrieval_system(name: str, cases: list[dict], *,
                               use_reranker: bool, use_domain_filter: bool,
                               k: int = 5) -> dict:
    p1, rr_total, latencies, cross_domain = 0, 0.0, [], 0
    for case in cases:
        eff_domain = case["domain"] if use_domain_filter else None
        t0 = time.time()
        hits = await _retrieve(case["q"], domain=eff_domain, k=k, use_reranker=use_reranker)
        latencies.append((time.time() - t0) * 1000)
        ids = [h["id"] for h in hits]
        domains = [h.get("domain") for h in hits]
        gold = set(case["gold"])
        rank = next((i + 1 for i, hid in enumerate(ids) if hid in gold), None)
        if rank == 1:
            p1 += 1
        if rank:
            rr_total += 1 / rank
        if hits and domains[0] != case["domain"]:
            cross_domain += 1
    n = len(cases)
    return {
        "name": name,
        "n": n,
        "p1": p1 / n,
        "mrr": rr_total / n,
        "p50_ms": median(latencies),
        "mean_ms": mean(latencies),
        "cross_domain_top1": cross_domain,
        "retrieves": True,
    }


async def run_zero_shot_llm(cases: list[dict]) -> dict:
    """Pure-LLM baseline: no RAG, no persona prompt, just the model's
    own weights answering the question. Measures keyword coverage on
    the safety / legal probes, not P@1 — there's nothing to retrieve."""
    from ai.provider import chat
    from config import GROQ_MODEL_SMART
    SYSTEM = (
        "You are a helpful assistant for people in India seeking guidance on "
        "mental health, legal rights, government schemes and personal safety. "
        "Answer the user's question concisely and accurately. Cite official "
        "Indian helpline numbers or statute Section numbers where they apply."
    )
    kw_pass = 0
    misses: list[str] = []
    latencies = []
    for probe in KEYWORD_PROBES:
        t0 = time.time()
        try:
            result = await chat(
                model=GROQ_MODEL_SMART,
                temperature=0.5,
                max_tokens=600,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": probe["q"]},
                ],
            )
            reply = result["content"]
        except Exception as err:
            misses.append(f"{probe['q'][:40]} — error: {err}")
            continue
        latencies.append((time.time() - t0) * 1000)
        lower = reply.lower()
        ok = any(k.lower() in lower for k in probe["any"])
        if ok:
            kw_pass += 1
        else:
            misses.append(f"{probe['q'][:40]} — missing all of {probe['any']}")
    n = len(KEYWORD_PROBES)
    return {
        "name": "D. ZERO_SHOT_LLM (no RAG, model weights only)",
        "n": n,
        "p1": None,
        "mrr": None,
        "p50_ms": median(latencies) if latencies else 0,
        "mean_ms": mean(latencies) if latencies else 0,
        "cross_domain_top1": None,
        "retrieves": False,
        "keyword_coverage": kw_pass / n if n else 0,
        "keyword_misses": misses,
    }


def _fmt_row(r: dict) -> str:
    name = f"{r['name']:<58}"
    if r["retrieves"]:
        p1 = f"P@1={r['p1']*100:5.1f}%"
        mrr = f"MRR={r['mrr']:.3f}"
        lat = f"p50={r['p50_ms']:5.0f}ms"
        leak = f"x-domain={r['cross_domain_top1']:>3}"
        return f"  {name}  {p1}  {mrr}  {lat}  {leak}"
    kw = f"keyword-coverage={r['keyword_coverage']*100:5.1f}%"
    lat = f"p50={r['p50_ms']:5.0f}ms"
    return f"  {name}  {kw}  {lat}  (no retrieval)"


def _delta_row(label: str, full: dict, base: dict) -> str:
    if not base["retrieves"]:
        return f"  {label:<58}  (no retrieval to compare — see keyword coverage)"
    d_p1 = (full["p1"] - base["p1"]) * 100
    d_mrr = full["mrr"] - base["mrr"]
    sign = "+" if d_p1 >= 0 else ""
    return f"  {label:<58}  dP@1={sign}{d_p1:5.1f} pp   dMRR={d_mrr:+.3f}"


async def main():
    split = "test"  # held-out by default — paper-grade number
    skip_llm = False
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--split" and i + 1 < len(sys.argv) - 1:
            split = sys.argv[i + 2]
        if arg == "--skip-llm":
            skip_llm = True

    cases = by_split(split)
    print(f"\nSeelenruh baseline comparison — split={split}, n={len(cases)}\n")

    await _ensure_index()
    await asyncio.to_thread(embedder.warmup)
    if reranker.is_enabled():
        await asyncio.to_thread(reranker.warmup)
    print()

    a = await run_retrieval_system("A. FULL (rerank + persona-domain filter, k=5)  PROD",
                                   cases, use_reranker=True, use_domain_filter=True)
    b = await run_retrieval_system("B. VANILLA_RAG (bi-encoder only, no filter, k=5)",
                                   cases, use_reranker=False, use_domain_filter=False)
    c = await run_retrieval_system("C. SINGLE_PERSONA (rerank, no domain filter, k=5)",
                                   cases, use_reranker=True, use_domain_filter=False)
    rows = [a, b, c]
    if not skip_llm:
        d = await run_zero_shot_llm(cases)
        rows.append(d)

    print("=== Baseline comparison table ===\n")
    for r in rows:
        print(_fmt_row(r))
    print()

    print("=== Headline deltas vs FULL system ===\n")
    print(_delta_row("FULL -> VANILLA_RAG", a, b))
    print(_delta_row("FULL -> SINGLE_PERSONA", a, c))
    if not skip_llm:
        print(_delta_row("FULL -> ZERO_SHOT_LLM", a, rows[-1]))
        print()
        print(f"  ZERO_SHOT keyword-coverage: {rows[-1]['keyword_coverage']*100:.1f}%  "
              f"(misses below — these are the dangerous ones)")
        for m in rows[-1]["keyword_misses"]:
            print(f"    - {m}")
    print()

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"baselines_{split}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps({
        "tool": "eval_baselines.py",
        "split": split,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n": len(cases),
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print(f"  Saved structured run to: {out_path.relative_to(Path(__file__).parent)}\n")


if __name__ == "__main__":
    asyncio.run(main())
