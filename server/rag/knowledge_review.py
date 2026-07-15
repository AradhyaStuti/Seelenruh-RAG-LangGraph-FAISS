"""CLI tool to check which knowledge chunks need re-verification."""
import argparse
import sys
from collections import defaultdict
from datetime import date

from rag.knowledge import CHUNKS
from rag.knowledge_meta import enrich_chunk, ReviewStatus


def _header(status: str) -> str:
    return {
        ReviewStatus.DEPRECATED.value:  "🔴  DEPRECATED — Remove or replace immediately",
        ReviewStatus.SUPERSEDED.value:  "🟠  SUPERSEDED — Update to newer version",
        ReviewStatus.NEEDS_REVIEW.value: "🟡  NEEDS REVIEW — Human verification required",
        ReviewStatus.UNKNOWN.value:     "⚪  UNKNOWN — No verification date on record",
        ReviewStatus.VERIFIED.value:    "🟢  VERIFIED — Within review window",
    }.get(status, status)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Knowledge freshness report — identify chunks requiring human attention."
    )
    parser.add_argument("--domain",  help="Filter by domain  (e.g. Legal, Safety, Government Schemes)")
    parser.add_argument("--status",  help="Filter by status  (Verified | NeedsReview | Unknown | Superseded | Deprecated)")
    parser.add_argument("--type",    dest="doc_type", help="Filter by document type  (e.g. Helpline, Scheme, Act)")
    parser.add_argument("--verbose", action="store_true", help="Show review note for every chunk (not just problem chunks)")
    args = parser.parse_args()

    today = date.today()
    enriched = [enrich_chunk(c, today=today) for c in CHUNKS]

    filtered = enriched
    if args.domain:
        filtered = [c for c in filtered if (c.get("domain") or "").lower() == args.domain.lower()]
    if args.status:
        filtered = [c for c in filtered if c.get("reviewStatus", "") == args.status]
    if args.doc_type:
        filtered = [c for c in filtered if c.get("documentType", "") == args.doc_type]

    by_status: dict[str, list[dict]] = defaultdict(list)
    for c in filtered:
        by_status[c.get("reviewStatus", ReviewStatus.UNKNOWN.value)].append(c)

    print(f"\n{'='*65}")
    print(f"  Knowledge Freshness Report   {today}")
    print(f"{'='*65}")
    print(f"  Total chunks in knowledge base : {len(enriched)}")
    if len(filtered) != len(enriched):
        print(f"  After filters                  : {len(filtered)}")
    print()

    priority_order = [
        ReviewStatus.DEPRECATED.value,
        ReviewStatus.SUPERSEDED.value,
        ReviewStatus.NEEDS_REVIEW.value,
        ReviewStatus.UNKNOWN.value,
        ReviewStatus.VERIFIED.value,
    ]
    show_note_for = {ReviewStatus.DEPRECATED.value, ReviewStatus.SUPERSEDED.value,
                     ReviewStatus.NEEDS_REVIEW.value, ReviewStatus.UNKNOWN.value}

    for status in priority_order:
        chunks = by_status.get(status, [])
        if not chunks:
            continue

        print(f"{_header(status)} ({len(chunks)})")
        print(f"{'-'*65}")

        for c in chunks:
            lv     = c.get("lastVerifiedOn") or "—"
            dt     = c.get("documentType", "General")
            domain = c.get("domain", "—")
            freq   = c.get("reviewFrequency", "Periodic")
            topic  = c.get("topic") or c.get("id", "?")
            note   = c.get("reviewNote", "")

            print(f"  [{domain}] {topic}")
            print(f"    Type: {dt:<15} Review: {freq:<10} Last verified: {lv}")

            show_note = status in show_note_for or args.verbose
            if show_note and note:
                print(f"    ↳ {note}")
            print()

    print(f"{'='*65}")
    needs_action = (
        len(by_status.get(ReviewStatus.DEPRECATED.value, [])) +
        len(by_status.get(ReviewStatus.SUPERSEDED.value, [])) +
        len(by_status.get(ReviewStatus.NEEDS_REVIEW.value, []))
    )
    if needs_action:
        print(f"  ⚠  {needs_action} chunk(s) require human attention.")
        print("     Run with --status NeedsReview to focus on overdue items.")
    else:
        print("  ✓  All chunks are within their review window.")
    print()

    return 1 if needs_action else 0


if __name__ == "__main__":
    sys.exit(main())
