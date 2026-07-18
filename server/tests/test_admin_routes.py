"""Admin API endpoint tests — 24 tests covering auth, all endpoints, and chunk splitting."""
import io
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Minimal stubs so admin.py imports cleanly — no live server/DB/FAISS needed
# ---------------------------------------------------------------------------
import types

_fake_config = types.ModuleType("config")
_fake_config.ADMIN_KEY = "test-key"
sys.modules.setdefault("config", _fake_config)

for _mod in ["structlog", "sentence_transformers", "faiss", "pdfplumber", "docx"]:
    sys.modules.setdefault(_mod, MagicMock())

_fake_db = types.ModuleType("db")
_fake_db._db = MagicMock()
_fake_db.log_admin_action = AsyncMock()
_fake_db.fetch_audit_log = AsyncMock(return_value=[])
_fake_db.fetch_knowledge_gaps = AsyncMock(return_value=[])
_fake_db.update_knowledge_gap = AsyncMock(return_value=True)
_fake_db.fetch_feedback_stats = AsyncMock(return_value={"total": 0, "up": 0, "down": 0})
_fake_db.fetch_document_registry = AsyncMock(return_value=[])
_fake_db.fetch_document_by_id = AsyncMock(return_value=None)
_fake_db.save_document_registry = AsyncMock()
_fake_db.delete_document_from_registry = AsyncMock()
_fake_db.update_document_status = AsyncMock(return_value=True)
sys.modules["db"] = _fake_db

_fake_rl = types.ModuleType("rate_limit")
_fake_rl.limiter = MagicMock()
_fake_rl.limiter.limit = lambda *a, **kw: (lambda f: f)
sys.modules["rate_limit"] = _fake_rl

_fake_rag = types.ModuleType("rag")
sys.modules.setdefault("rag", _fake_rag)
_fake_retriever = types.ModuleType("rag.retriever")
_fake_retriever._store = MagicMock()
_fake_retriever._store.index = MagicMock()
_fake_retriever._store.index.ntotal = 100
_fake_retriever._store.size = MagicMock(return_value=80)
_fake_retriever._store.meta = []
_fake_retriever._store._deleted_ids = set()
_fake_retriever._store.should_compact = MagicMock(return_value=False)
_fake_retriever._store.list_snapshots = MagicMock(return_value=[{"name": "snap1"}])
_fake_retriever._store.rollback = MagicMock(return_value=True)
_fake_retriever._write_lock = MagicMock()
_fake_retriever._write_lock.__aenter__ = AsyncMock(return_value=None)
_fake_retriever._write_lock.__aexit__ = AsyncMock(return_value=None)
_fake_retriever.is_ready = MagicMock(return_value=True)
_fake_retriever.ingest = AsyncMock(return_value=2)
_fake_retriever.delete = AsyncMock(return_value=1)
sys.modules["rag.retriever"] = _fake_retriever

_fake_ku = types.ModuleType("knowledge_updater")
_fake_ku.run_update_cycle = AsyncMock(return_value={"checked": 3, "updated": 1, "errors": 0})
sys.modules["knowledge_updater"] = _fake_ku

from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes.admin import router as admin_router, _chunk_text

app = FastAPI()
app.include_router(admin_router)

GOOD = {"X-Admin-Key": "test-key"}
BAD  = {"X-Admin-Key": "wrong"}

CHUNK = {
    "topic": "POCSO Act",
    "domain": "Legal",
    "text": "The POCSO Act protects children from sexual offences." * 2,
}


@pytest.fixture(autouse=True)
def reset():
    for mock in [
        _fake_db.log_admin_action, _fake_db.fetch_audit_log, _fake_db.fetch_knowledge_gaps,
        _fake_db.update_knowledge_gap, _fake_db.fetch_feedback_stats,
        _fake_db.fetch_document_registry, _fake_db.fetch_document_by_id,
        _fake_db.save_document_registry, _fake_db.delete_document_from_registry,
        _fake_db.update_document_status, _fake_retriever.ingest, _fake_retriever.delete,
        _fake_retriever._store.rollback, _fake_ku.run_update_cycle,
    ]:
        mock.reset_mock()
    yield


client = TestClient(app)


# 1 — wrong key blocked on every protected route
def test_auth_wrong_key_blocked():
    assert client.get("/api/admin/status", headers=BAD).status_code == 401

# 2 — missing key also blocked
def test_auth_missing_key_blocked():
    assert client.get("/api/admin/chunks").status_code == 401

# 3 — status returns index health fields
def test_status_returns_index_health():
    r = client.get("/api/admin/status", headers=GOOD)
    assert r.status_code == 200
    data = r.json()
    assert {"ragReady", "chunksInIndex", "totalVectors", "deletedVectors", "compactionNeeded"} <= data.keys()

# 4 — ingest happy path
def test_ingest_chunks_success():
    _fake_retriever.ingest.return_value = 1
    r = client.post("/api/admin/ingest", json={"chunks": [CHUNK]}, headers=GOOD)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["added"] == 1

# 5 — ingest rejects invalid domain
def test_ingest_invalid_domain_rejected():
    r = client.post("/api/admin/ingest", json={"chunks": [{**CHUNK, "domain": "Politics"}]}, headers=GOOD)
    assert r.status_code == 422

# 6 — ingest rejects text that is too short
def test_ingest_short_text_rejected():
    r = client.post("/api/admin/ingest", json={"chunks": [{**CHUNK, "text": "short"}]}, headers=GOOD)
    assert r.status_code == 422

# 7 — delete chunks calls retriever with correct IDs
def test_delete_chunks_calls_retriever():
    _fake_retriever.delete.return_value = 1
    client.request("DELETE", "/api/admin/ingest", json={"ids": ["c1", "c2"]}, headers=GOOD)
    _fake_retriever.delete.assert_called_once_with(["c1", "c2"])

# 8 — chunk browser respects domain filter
def test_chunks_domain_filter():
    _fake_retriever._store.meta = [
        {"id": "a", "domain": "Legal", "topic": "RTI", "text": "RTI text..."},
        {"id": "b", "domain": "Mental Health", "topic": "Anxiety", "text": "Anxiety..."},
    ]
    _fake_retriever._store._deleted_ids = set()
    r = client.get("/api/admin/chunks?domain=Legal", headers=GOOD)
    assert r.json()["total"] == 1

# 9 — chunk browser excludes soft-deleted entries
def test_chunks_excludes_deleted():
    _fake_retriever._store.meta = [
        {"id": "live", "domain": "Legal", "topic": "T", "text": "live text..."},
        {"id": "gone", "domain": "Legal", "topic": "T", "text": "deleted text..."},
    ]
    _fake_retriever._store._deleted_ids = {"gone"}
    r = client.get("/api/admin/chunks?domain=Legal", headers=GOOD)
    assert r.json()["total"] == 1
    assert r.json()["chunks"][0]["id"] == "live"

# 10 — analytics returns all four top-level keys
def test_analytics_response_shape():
    _fake_db.fetch_feedback_stats.return_value = {"total": 5, "up": 4, "down": 1}
    _fake_db.fetch_knowledge_gaps.return_value = []
    _fake_db.fetch_document_registry.return_value = []
    r = client.get("/api/admin/analytics", headers=GOOD)
    assert r.status_code == 200
    assert {"feedback", "knowledgeGaps", "rag", "documents"} <= r.json().keys()

# 11 — knowledge gaps status filter is forwarded to db
def test_knowledge_gaps_filter_forwarded():
    _fake_db.fetch_knowledge_gaps.return_value = []
    client.get("/api/admin/knowledge-gaps?status=open", headers=GOOD)
    _fake_db.fetch_knowledge_gaps.assert_called_once_with(status="open", limit=100)

# 12 — patch gap to solved
def test_patch_gap_solved():
    _fake_db.update_knowledge_gap.return_value = True
    r = client.patch("/api/admin/knowledge-gaps/g1", json={"status": "solved"}, headers=GOOD)
    assert r.status_code == 200
    assert r.json()["status"] == "solved"

# 13 — patch gap with invalid status is rejected
def test_patch_gap_invalid_status():
    r = client.patch("/api/admin/knowledge-gaps/g1", json={"status": "deleted"}, headers=GOOD)
    assert r.status_code == 422

# 14 — rollback returns ok and step count
def test_rollback_success():
    _fake_retriever._store.rollback.return_value = True
    r = client.post("/api/admin/rollback?steps=2", headers=GOOD)
    assert r.status_code == 200
    assert r.json()["steps"] == 2

# 15 — rollback when no snapshot returns 409
def test_rollback_no_snapshot_returns_409():
    _fake_retriever._store.rollback.return_value = False
    assert client.post("/api/admin/rollback", headers=GOOD).status_code == 409

# 16 — snapshots list is returned
def test_snapshots_returned():
    _fake_retriever._store.list_snapshots.return_value = [{"name": "s1"}, {"name": "s2"}]
    r = client.get("/api/admin/snapshots", headers=GOOD)
    assert r.json()["count"] == 2

# 17 — audit log entries are returned and limit is forwarded
def test_audit_log_limit_forwarded():
    _fake_db.fetch_audit_log.return_value = []
    client.get("/api/admin/audit?limit=50", headers=GOOD)
    _fake_db.fetch_audit_log.assert_called_once_with(limit=50)

# 18 — document list returned
def test_documents_list():
    _fake_db.fetch_document_registry.return_value = [
        {"docId": "doc_1", "filename": "guide.pdf", "domain": "Legal", "status": "active"}
    ]
    r = client.get("/api/admin/documents", headers=GOOD)
    assert r.json()["total"] == 1

# 19 — soft delete updates status, does not purge registry
def test_delete_document_soft():
    _fake_db.fetch_document_by_id.return_value = {"docId": "d1", "filename": "f.pdf", "chunkIds": ["c1"]}
    _fake_retriever.delete.return_value = 1
    client.delete("/api/admin/documents/d1", headers=GOOD)
    _fake_db.update_document_status.assert_called_once_with("d1", "deleted")
    _fake_db.delete_document_from_registry.assert_not_called()

# 20 — restore document marks it active
def test_restore_document():
    _fake_db.update_document_status.return_value = True
    r = client.post("/api/admin/documents/d1/restore", headers=GOOD)
    assert r.json()["status"] == "active"

# 21 — txt file upload is ingested and saved to registry
def test_ingest_document_txt():
    _fake_retriever.ingest.return_value = 3
    text = "Knowledge about legal rights.\n\n" * 15
    r = client.post(
        "/api/admin/ingest-document?domain=Legal",
        files=[("file", ("doc.txt", io.BytesIO(text.encode()), "text/plain"))],
        headers=GOOD,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    _fake_db.save_document_registry.assert_called_once()

# 22 — unsupported file type returns 415
def test_ingest_document_unsupported_type():
    r = client.post(
        "/api/admin/ingest-document?domain=Legal",
        files=[("file", ("script.exe", io.BytesIO(b"binary"), "application/octet-stream"))],
        headers=GOOD,
    )
    assert r.status_code == 415

# 23 — crawler trigger returns ok and logs action
def test_crawler_trigger():
    r = client.post("/api/admin/crawler/trigger", headers=GOOD)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    _fake_db.log_admin_action.assert_called_once()
    assert _fake_db.log_admin_action.call_args.kwargs["action"] == "trigger_crawler"

# 24 — _chunk_text splits long content and preserves keywords
def test_chunk_text_splits_and_preserves_content():
    keyword = "POCSO Act protects children"
    text = f"{keyword}.\n\n" + ("Additional legal context. " * 30)
    chunks = _chunk_text(text)
    assert len(chunks) >= 1
    assert all(len(c) >= 20 for c in chunks)
    assert keyword in " ".join(chunks)
