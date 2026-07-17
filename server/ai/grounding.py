"""Output grounding: detect hallucinated legal citations not in retrieved chunks.

Only meaningful for the Legal domain where structured section/article references
can be verified against the knowledge-base chunks that were actually retrieved.
Mental Health, Government Schemes, and Safety responses don't have the same
citation patterns and are not checked.

Usage
-----
    from ai.grounding import maybe_add_grounding_note

    response = maybe_add_grounding_note(response, retrieved_chunks)
"""
from __future__ import annotations

import re

# Matches: "Section 302", "Section 498A of the IPC",
#          "Article 21 of the Constitution", "Rule 4 of …", "Schedule II of …"
_CITATION_RE = re.compile(
    r"(?:"
    r"[Ss]ection\s+(\d+[A-Za-z]{0,3})"
    r"|[Aa]rticle\s+(\d+[A-Za-z]{0,3})"
    r"|[Rr]ule\s+(\d+[A-Za-z]{0,3})"
    r"|[Ss]chedule\s+([IVXivx]{1,6}|\d+)"
    r"|[Cc]lause\s+(\d+[A-Za-z]{0,3})"
    r")",
    re.MULTILINE,
)

_GROUNDING_NOTE = (
    "\n\n---\n"
    "_Note: One or more specific section / article numbers cited above could not "
    "be verified in the available knowledge base. Please confirm these references "
    "directly in the relevant statute before relying on them._"
)


def _citations_in(text: str) -> list[str]:
    """Return normalised citation numbers found in *text*."""
    nums: list[str] = []
    for m in _CITATION_RE.finditer(text):
        for g in m.groups():
            if g:
                nums.append(g.strip().lower())
                break
    return nums


def _chunk_corpus(retrieved: list[dict]) -> str:
    return " ".join(
        f"{c.get('topic', '')} {c.get('text', '')}".lower()
        for c in retrieved
    )


def check_grounding(
    response: str,
    retrieved: list[dict],
) -> tuple[bool, list[str]]:
    """Check whether every cited section/article appears in the retrieved chunks.

    Returns
    -------
    (is_grounded, unverified)
        ``is_grounded`` is True when all citations can be found in the corpus
        or when the response contains no citations at all.
        ``unverified`` is the list of citation numbers not found.
    """
    citations = _citations_in(response)
    if not citations:
        return True, []

    corpus = _chunk_corpus(retrieved)
    unverified = [c for c in citations if c not in corpus]
    return len(unverified) == 0, unverified


def maybe_add_grounding_note(
    response: str,
    retrieved: list[dict],
) -> str:
    """Append a grounding disclaimer if unverified citations are detected.

    Safe to call on any domain — if no citations are found it's a no-op.
    """
    is_grounded, _ = check_grounding(response, retrieved)
    if not is_grounded:
        return response + _GROUNDING_NOTE
    return response
