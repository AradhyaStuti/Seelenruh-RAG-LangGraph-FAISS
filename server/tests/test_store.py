"""Tests for vector-store build / search / cache invalidation."""
import json

import numpy as np

from rag.store import VectorStore


def _fake_chunks():
    return [
        {"id": "c1", "domain": "X", "topic": "alpha", "text": "first chunk", "source": "Test", "lastVerifiedOn": "2025-10-15"},
        {"id": "c2", "domain": "X", "topic": "beta",  "text": "second chunk", "source": "Test", "lastVerifiedOn": "2025-10-15"},
    ]


def _fake_vectors(dim=4):
    arr = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype="float32")
    # L2-normalise so cosine == dot product
    arr /= np.linalg.norm(arr, axis=1, keepdims=True)
    return arr


def test_build_and_search_roundtrip():
    store = VectorStore()
    store.build(_fake_chunks(), _fake_vectors())
    qv = np.array([1, 0, 0, 0], dtype="float32")
    hits = store.search(qv, k=2)
    assert len(hits) == 2
    assert hits[0]["id"] == "c1"  # closest by construction


def test_meta_carries_source_and_lastVerifiedOn():
    store = VectorStore()
    store.build(_fake_chunks(), _fake_vectors())
    qv = np.array([1, 0, 0, 0], dtype="float32")
    hits = store.search(qv, k=1)
    assert hits[0]["source"] == "Test"
    assert hits[0]["lastVerifiedOn"] == "2025-10-15"


def test_cache_invalidates_on_version_mismatch(tmp_path, monkeypatch):
    """A cache written under META_VERSION=1 must be rejected today."""
    cache = tmp_path / ".cache"
    cache.mkdir()
    monkeypatch.setattr("rag.store.CACHE_DIR", cache)
    monkeypatch.setattr("rag.store.INDEX_PATH", cache / "faiss.index")
    monkeypatch.setattr("rag.store.META_PATH", cache / "meta.json")

    # Hand-write a stale cache shaped like META_VERSION=1 (flat list, no version key).
    (cache / "meta.json").write_text(json.dumps([{"id": "old"}]), encoding="utf-8")

    store = VectorStore()
    # The faiss index file doesn't exist either — load should refuse cleanly.
    assert store.load() is False


def test_cache_roundtrip_with_correct_version(tmp_path, monkeypatch):
    cache = tmp_path / ".cache"
    cache.mkdir()
    monkeypatch.setattr("rag.store.CACHE_DIR", cache)
    monkeypatch.setattr("rag.store.INDEX_PATH", cache / "faiss.index")
    monkeypatch.setattr("rag.store.META_PATH", cache / "meta.json")

    store1 = VectorStore()
    store1.build(_fake_chunks(), _fake_vectors())
    store1.save()

    store2 = VectorStore()
    assert store2.load() is True
    assert store2.size() == 2
    assert store2.meta[0]["id"] == "c1"
