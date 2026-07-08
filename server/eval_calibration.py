"""Calibration eval for the confidence signal Seelenruh shows in the UI.

The Sources-Used panel surfaces a High / Medium / Low badge derived from
the cross-encoder re-rank score of the top hit. The claim — and the
research-grade angle of the project — is that these labels are
*calibrated*: a "High" badge should correspond to a substantially higher
chance the gold chunk was actually retrieved than a "Low" badge.

This script bins every query in the 100-query test set by the system's
own confidence call, then computes per-bin retrieval P@1. If the labels
are calibrated we should see High >> Medium >> Low. If they're roughly
equal, the badge is decorative — which would be useful to know.

Run:
  cd server && .venv/Scripts/python eval_calibration.py
"""
import asyncio
from collections import defaultdict
from statistics import mean

from rag import retriever
from config import RETRIEVAL_TOP_K
from eval_data import by_split


def _confidence_from_hits(hits: list[dict]) -> str:
    """Mirror of `graph.py::_confidence_from`."""
    if not hits:
        return "None"
    top = hits[0]
    if "rerank_score" in top:
        s = float(top["rerank_score"])
        if s >= 5.0:
            return "High"
        if s >= 2.0:
            return "Medium"
        return "Low"
    s = float(top.get("score", 0.0))
    if s >= 0.88:
        return "High"
    if s >= 0.78:
        return "Medium"
    return "Low"


async def main():
    import sys
    split = "test"
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--split" and i + 1 < len(sys.argv) - 1:
            split = sys.argv[i + 2]
            break
    cases = by_split(split)
    print(f"\nSeelenruh calibration - {len(cases)} queries  (split={split})\n")
    await retriever.init()
    await retriever.warmup()
    print()

    buckets: dict[str, list[int]] = defaultdict(list)  # label -> [1 if P@1 else 0]
    misclassified: dict[str, list[str]] = defaultdict(list)

    for case in cases:
        hits = await retriever.retrieve(case["q"], domain=case["domain"], k=RETRIEVAL_TOP_K)
        label = _confidence_from_hits(hits)
        top1 = hits[0]["id"] if hits else None
        gold_set = set(case["gold"])
        is_p1 = 1 if top1 in gold_set else 0
        buckets[label].append(is_p1)
        if not is_p1 and len(misclassified[label]) < 3:
            misclassified[label].append(
                f"want={sorted(gold_set)[:3]}{'+' if len(gold_set)>3 else ''} got={top1} q='{case['q'][:55]}'"
            )

    print("=== Confidence calibration ===\n")
    print(f"  {'Label':<10}{'N':>6}{'share':>9}{'P@1':>9}")
    n_total = sum(len(v) for v in buckets.values())
    for label in ["High", "Medium", "Low", "None"]:
        v = buckets.get(label, [])
        n = len(v)
        if n == 0:
            print(f"  {label:<10}{0:>6}{'-':>9}{'-':>9}")
            continue
        p1 = sum(v) / n
        share = n / n_total
        print(f"  {label:<10}{n:>6}{share*100:>8.1f}%{p1*100:>8.1f}%")
    print()

    # The key claim — High >> Medium >> Low.
    high_p1 = mean(buckets.get("High", [0])) if buckets.get("High") else 0
    med_p1 = mean(buckets.get("Medium", [0])) if buckets.get("Medium") else 0
    low_p1 = mean(buckets.get("Low", [0])) if buckets.get("Low") else 0
    spread = high_p1 - low_p1
    print(f"  Calibration spread (High P@1 - Low P@1) : {spread*100:.1f} percentage points")
    print(f"  Monotonic ordering (High >= Medium >= Low) : "
          f"{'yes' if high_p1 >= med_p1 >= low_p1 else 'NO'}")
    print()

    if any(misclassified.values()):
        print("=== Sample misclassified queries by bucket ===\n")
        for label in ["High", "Medium", "Low"]:
            misses = misclassified.get(label, [])
            if not misses:
                continue
            print(f"  {label}-confidence misses (these are the dangerous ones if the bucket is large):")
            for m in misses:
                print(f"    - {m}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
