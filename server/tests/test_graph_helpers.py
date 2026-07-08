"""Tests for the small helpers in `graph.py` that shape retrieval hits for
the UI. These are pure functions, easy to break by typo, and the visible
behaviour (confidence pill, sources panel) depends on them being right."""
from graph import _build_sources, _confidence_from, _cited_indices


def test_build_sources_strips_full_text_keeps_metadata():
    hits = [{
        "id": "lg-2",
        "topic": "RTI filing process",
        "domain": "Legal",
        "text": "very long chunk text we don't want to ship to the client",
        "score": 0.91,
        "rerank_score": 5.7,
        "source": "RTI Act 2005",
        "lastVerifiedOn": "2025-10-15",
    }]
    out = _build_sources(hits)
    assert out[0]["id"] == "lg-2"
    assert out[0]["topic"] == "RTI filing process"
    assert out[0]["domain"] == "Legal"
    assert out[0]["score"] == 0.91
    assert out[0]["rerankScore"] == 5.7
    assert out[0]["source"] == "RTI Act 2005"
    assert out[0]["lastVerifiedOn"] == "2025-10-15"
    assert "text" not in out[0]  # the heavy field must not leak


def test_build_sources_handles_missing_rerank_score():
    hits = [{"id": "x", "topic": "t", "domain": "d", "text": "", "score": 0.5}]
    out = _build_sources(hits)
    assert out[0]["rerankScore"] is None
    assert out[0]["source"] is None
    assert out[0]["lastVerifiedOn"] is None


def test_confidence_high_when_rerank_strong():
    hits = [{"rerank_score": 7.2, "score": 0.9}]
    assert _confidence_from(hits) == "High"


def test_confidence_medium_when_rerank_middling():
    hits = [{"rerank_score": 2.5, "score": 0.9}]
    assert _confidence_from(hits) == "Medium"


def test_confidence_low_when_rerank_weak():
    hits = [{"rerank_score": 0.3, "score": 0.9}]
    assert _confidence_from(hits) == "Low"


def test_confidence_falls_back_to_faiss_score_when_no_rerank():
    hits = [{"score": 0.92}]
    assert _confidence_from(hits) == "High"
    assert _confidence_from([{"score": 0.78}]) == "Medium"
    assert _confidence_from([{"score": 0.50}]) == "Low"


def test_confidence_none_on_empty_hits():
    assert _confidence_from([]) == "None"


def test_cited_indices_picks_inline_marks_in_first_appearance_order():
    text = "RTI deadline is 30 days [2]. First Appeal to the FAA [3][2]. See also [1]."
    assert _cited_indices(text, n_sources=3) == [2, 3, 1]


def test_cited_indices_ignores_out_of_range_marks():
    """Model occasionally hallucinates [4] when only 3 sources supplied."""
    text = "Per Section 6 [1] and amendment notice [4]."
    assert _cited_indices(text, n_sources=3) == [1]


def test_cited_indices_empty_when_no_citations():
    assert _cited_indices("plain prose with no marks", n_sources=3) == []


def test_cited_indices_handles_no_sources():
    assert _cited_indices("anything [1] here", n_sources=0) == []
