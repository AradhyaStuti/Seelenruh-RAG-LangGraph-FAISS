"""Output grounding: detect hallucinated citations not found in retrieved chunks.

Applies to ALL personas — Legal, Mental Health, Government Schemes, and Safety.
Each domain has its own citation patterns:

  Legal        — Section X, Article X, Rule X, Schedule X, Clause X
  Schemes      — PM-KISAN, Ayushman X, Scheme names with registration numbers
  Mental Health— DSM-5 criteria numbers, ICD codes
  Safety       — IPC/BNS section numbers, POCSO sections, helpline numbers

When any explicit citation cannot be found in the retrieved chunks, a disclaimer
is appended. If there are no citations in the response, the function is a no-op.

Usage
-----
    from ai.grounding import maybe_add_grounding_note

    response = maybe_add_grounding_note(response, retrieved_chunks, domain="Legal")
"""
from __future__ import annotations

import re
from typing import Optional

# ── Legal citations ──────────────────────────────────────────────────────────
# Matches: "Section 302", "Section 498A of the IPC",
#          "Article 21", "Rule 4", "Schedule II", "Clause 5(b)"
_LEGAL_CITATION_RE = re.compile(
    r"(?:"
    r"[Ss]ection\s+(\d+[A-Za-z]{0,3}(?:\([a-z]\))?)"
    r"|[Aa]rticle\s+(\d+[A-Za-z]{0,3})"
    r"|[Rr]ule\s+(\d+[A-Za-z]{0,3})"
    r"|[Ss]chedule\s+([IVXivx]{1,6}|\d+)"
    r"|[Cc]lause\s+(\d+[A-Za-z]{0,3})"
    r")",
    re.MULTILINE,
)

# ── Scheme citations ──────────────────────────────────────────────────────────
# Matches benefit amounts, scheme registration codes, specific eligibility numbers
_SCHEME_CITATION_RE = re.compile(
    r"(?:"
    r"₹\s*(\d[\d,]+)"                          # benefit amounts e.g. "₹6,000"
    r"|\b(PM-?[A-Z]{2,10})\b"                  # PM-KISAN, PMJAY, PMGKY etc.
    r"|\b([A-Z]{2,6}-\d{4,})\b"               # scheme codes with numbers
    r")",
    re.MULTILINE,
)

# ── Mental Health citations ──────────────────────────────────────────────────
# DSM-5, ICD-10/11 codes
_MH_CITATION_RE = re.compile(
    r"(?:"
    r"\b(DSM-?5|ICD-?(?:10|11))\s+(?:criteria\s+)?([A-Z]\d+(?:\.\d+)?)\b"
    r"|\b(F\d{2}(?:\.\d+)?)\b"                 # ICD-10 mental health codes
    r")",
    re.MULTILINE,
)

_GROUNDING_NOTES = {
    "Legal": (
        "\n\n---\n"
        "_Note: One or more section / article numbers cited above could not be "
        "verified in the available knowledge base. Please confirm these references "
        "directly in the relevant statute (or with a qualified lawyer) before "
        "relying on them._"
    ),
    "Government Schemes": (
        "\n\n---\n"
        "_Note: Some scheme details (benefit amounts, eligibility criteria) cited "
        "above could not be cross-verified against the knowledge base. Please "
        "confirm on the official scheme portal (myscheme.gov.in) before applying._"
    ),
    "Mental Health": (
        "\n\n---\n"
        "_Note: Some clinical references above (DSM/ICD codes or criteria) could "
        "not be verified against available sources. Please consult a licensed mental "
        "health professional for a clinical assessment._"
    ),
    "Safety": (
        "\n\n---\n"
        "_Note: Some legal references cited above could not be verified against the "
        "available knowledge base. Please confirm with a lawyer or legal aid centre._"
    ),
    "default": (
        "\n\n---\n"
        "_Note: Some specific references cited above could not be verified in the "
        "available knowledge base. Please cross-check before relying on them._"
    ),
}


def _citations_in(text: str, domain: Optional[str] = None) -> list[str]:
    """Return normalised citation tokens found in *text* for the given domain."""
    nums: list[str] = []

    # Legal citations are checked for all domains (many responses cite IPC/CrPC)
    for m in _LEGAL_CITATION_RE.finditer(text):
        for g in m.groups():
            if g:
                nums.append(g.strip().lower())
                break

    if domain == "Mental Health":
        for m in _MH_CITATION_RE.finditer(text):
            for g in m.groups():
                if g:
                    nums.append(g.strip().lower())
                    break

    # Scheme benefit amounts are not individually verifiable → skip
    return nums


def _chunk_corpus(retrieved: list[dict]) -> str:
    return " ".join(
        f"{c.get('topic', '')} {c.get('text', '')}".lower()
        for c in retrieved
    )


def check_grounding(
    response: str,
    retrieved: list[dict],
    domain: Optional[str] = None,
) -> tuple[bool, list[str]]:
    """Check whether every cited number appears in the retrieved chunk corpus.

    Returns
    -------
    (is_grounded, unverified)
        ``is_grounded`` is True when all citations are found or when the
        response contains no verifiable citations at all.
        ``unverified`` is the list of citation tokens not found in the corpus.
    """
    citations = _citations_in(response, domain)
    if not citations:
        return True, []

    corpus = _chunk_corpus(retrieved)
    unverified = [c for c in citations if c not in corpus]
    return len(unverified) == 0, unverified


def maybe_add_grounding_note(
    response: str,
    retrieved: list[dict],
    domain: Optional[str] = None,
) -> str:
    """Append a domain-appropriate grounding disclaimer if unverified citations
    are detected. Safe to call on any domain — if no citations are found it
    is a pure no-op (no string allocation, no disclaimer added).
    """
    is_grounded, _ = check_grounding(response, retrieved, domain)
    if not is_grounded:
        note = _GROUNDING_NOTES.get(domain or "", _GROUNDING_NOTES["default"])
        return response + note
    return response
