"""Shared helpers for AI agent modules."""


def _kw_score(chunk: dict, keywords: list[str]) -> float:
    """Score a retrieved chunk by how many keywords appear in its text."""
    text = (chunk.get("topic", "") + " " + chunk.get("text", "")).lower()
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return hits / max(len(keywords), 1)
