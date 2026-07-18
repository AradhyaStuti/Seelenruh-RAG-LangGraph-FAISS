"""Tests for all admin API endpoints.

Strategy: spin up a minimal FastAPI app with only the admin router,
mock out all external I/O (db, retriever, knowledge_updater), and verify
auth, success, and error paths for every endpoint.

No live MongoDB, no FAISS index, no network needed.
"""
import io
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Bootstrap: provide a minimal config so admin.py can be imported cleanly.
# ---------------------------------------------------------------------------
import types

# Stub out 'config' before importing admin
_fake_config = types.ModuleType("config")
_fake_config.ADMIN_KEY = "test-secret-key"
_fake_config.MONGODB_DB = "test"
_fake_config.MONGODB_URI = "mongodb://localhost"
_fake_config.JWT_SECRET = "jwt-secret"
_fake_config.GEMINI_API_KEY = ""
_fake_config.OPENAI_API_KEY = ""
_fake_config.ANTHROPIC_API_KEY = ""
_fake_config.GROQ_API_KEY = ""
_fake_config.ELEVENLABS_API_KEY = ""
_fake_config.ADMIN_KEY = "test-secret-key"
sys.modules.setdefault("config", _fake_config)

# Stub out slowslow-loading modules we don't need in tests
for _mod in ["structlog", "sentence_transformers", "faiss", "pdfplumber", "docx"]:
    sys.modules.setdefault(_mod, MagicMock())

# Stub 'db' module
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

# Stub 'rate_limit' module
_fake_rl = types.ModuleType("rate_limit")
_fake_rl.limiter = MagicMock()
_fake_rl.limiter.limit = lambda *a, **kw: (lambda f: f)  # no-op decorator
_fake_rl.burst_limit = lambda *a, **kw: (lambda f: f)
sys.modules["rate_limit"] = _fake_rl

# Stub 'rag.retriever'
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

# Stub 'knowledge_updater'
_fake_ku = types.ModuleType("knowledge_updater")
_fake_ku.run_update_cycle = AsyncMock(return_value={"checked": 3, "updated": 1, "errors": 0})
sys.modules["knowledge_updater"] = _fake_ku

# Now import FastAPI + the admin router
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Patch ADMIN_KEY inside the admin module namespace before import
with patch.dict(sys.modules, {}):
    from routes.admin import router as admin_router

app = FastAPI()
app.include_router(admin_router)

GOOD_KEY = "test-secret-key"
BAD_KEY  = "wrong-key"
HEADERS  = {"X-Admin-Key": GOOD_KEY}


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset call counts and return values before each test."""
    _fake_db.log_admin_action.reset_mock()
    _fake_db.fetch_audit_log.reset_mock()
    _fake_db.fetch_knowledge_gaps.reset_mock()
    _fake_db.update_knowledge_gap.reset_mock()
    _fake_db.fetch_feedback_stats.reset_mock()
    _fake_db.fetch_document_registry.reset_mock()
    _fake_db.fetch_document_by_id.reset_mock()
    _fake_db.save_document_registry.reset_mock()
    _fake_db.delete_document_from_registry.reset_mock()
    _fake_db.update_document_status.reset_mock()
    _fake_retriever.ingest.reset_mock()
    _fake_retriever.delete.reset_mock()
    _fake_retriever._store.rollback.reset_mock()
    _fake_ku.run_update_cycle.reset_mock()
    yield


# ===========================================================================
# Auth guard — all endpoints must reject missing / wrong keys
# ===========================================================================

class TestAuthGuard:
    client = TestClient(app)

    def test_status_rejects_missing_key(self):
        r = self.client.get("/api/admin/status")
        assert r.status_code == 401

    def test_status_rejects_wrong_key(self):
        r = self.client.get("/api/admin/status", headers={"X-Admin-Key": BAD_KEY})
        assert r.status_code == 401

    def test_ingest_rejects_wrong_key(self):
        r = self.client.post(
            "/api/admin/ingest",
            json={"chunks": [{"topic": "t", "domain": "Mental Health", "text": "x" * 10}]},
            headers={"X-Admin-Key": BAD_KEY},
        )
        assert r.status_code == 401

    def test_delete_rejects_wrong_key(self):
        r = self.client.request(
            "DELETE",
            "/api/admin/ingest",
            json={"ids": ["abc"]},
            headers={"X-Admin-Key": BAD_KEY},
        )
        assert r.status_code == 401

    def test_chunks_rejects_missing_key(self):
        r = self.client.get("/api/admin/chunks")
        assert r.status_code == 401

    def test_audit_rejects_missing_key(self):
        r = self.client.get("/api/admin/audit")
        assert r.status_code == 401

    def test_snapshots_rejects_missing_key(self):
        r = self.client.get("/api/admin/snapshots")
        assert r.status_code == 401

    def test_rollback_rejects_wrong_key(self):
        r = self.client.post("/api/admin/rollback", headers={"X-Admin-Key": BAD_KEY})
        assert r.status_code == 401

    def test_knowledge_gaps_rejects_missing_key(self):
        r = self.client.get("/api/admin/knowledge-gaps")
        assert r.status_code == 401

    def test_analytics_rejects_missing_key(self):
        r = self.client.get("/api/admin/analytics")
        assert r.status_code == 401

    def test_documents_rejects_missing_key(self):
        r = self.client.get("/api/admin/documents")
        assert r.status_code == 401

    def test_crawler_sources_rejects_missing_key(self):
        r = self.client.get("/api/admin/crawler/sources")
        assert r.status_code == 401

    def test_crawler_trigger_rejects_wrong_key(self):
        r = self.client.post("/api/admin/crawler/trigger", headers={"X-Admin-Key": BAD_KEY})
        assert r.status_code == 401


# ===========================================================================
# GET /api/admin/status
# ===========================================================================

class TestAdminStatus:
    client = TestClient(app)

    def test_returns_200_with_valid_key(self):
        r = self.client.get("/api/admin/status", headers=HEADERS)
        assert r.status_code == 200

    def test_response_contains_required_fields(self):
        r = self.client.get("/api/admin/status", headers=HEADERS)
        data = r.json()
        assert "ragReady" in data
        assert "chunksInIndex" in data
        assert "totalVectors" in data
        assert "deletedVectors" in data
        assert "compactionNeeded" in data

    def test_rag_ready_reflects_mock(self):
        r = self.client.get("/api/admin/status", headers=HEADERS)
        assert r.json()["ragReady"] is True

    def test_chunks_in_index_matches_store_size(self):
        r = self.client.get("/api/admin/status", headers=HEADERS)
        assert r.json()["chunksInIndex"] == 80


# ===========================================================================
# POST /api/admin/ingest
# ===========================================================================

class TestIngestChunks:
    client = TestClient(app)

    VALID_CHUNK = {
        "topic": "POCSO Act overview",
        "domain": "Legal",
        "text": "The POCSO Act protects children from sexual offences." * 2,
        "source": "https://indiacode.nic.in",
    }

    def test_ingest_success_returns_200(self):
        _fake_retriever.ingest.return_value = 1
        r = self.client.post("/api/admin/ingest", json={"chunks": [self.VALID_CHUNK]}, headers=HEADERS)
        assert r.status_code == 200

    def test_ingest_response_structure(self):
        _fake_retriever.ingest.return_value = 1
        r = self.client.post("/api/admin/ingest", json={"chunks": [self.VALID_CHUNK]}, headers=HEADERS)
        data = r.json()
        assert data["ok"] is True
        assert "added" in data
        assert "totalInIndex" in data

    def test_ingest_calls_retriever(self):
        _fake_retriever.ingest.return_value = 1
        self.client.post("/api/admin/ingest", json={"chunks": [self.VALID_CHUNK]}, headers=HEADERS)
        _fake_retriever.ingest.assert_called_once()

    def test_ingest_logs_admin_action(self):
        _fake_retriever.ingest.return_value = 1
        self.client.post("/api/admin/ingest", json={"chunks": [self.VALID_CHUNK]}, headers=HEADERS)
        _fake_db.log_admin_action.assert_called_once()
        call_kwargs = _fake_db.log_admin_action.call_args.kwargs
        assert call_kwargs.get("action") == "ingest"

    def test_ingest_rejects_empty_chunks(self):
        r = self.client.post("/api/admin/ingest", json={"chunks": []}, headers=HEADERS)
        assert r.status_code == 422

    def test_ingest_rejects_too_short_text(self):
        chunk = {**self.VALID_CHUNK, "text": "short"}
        r = self.client.post("/api/admin/ingest", json={"chunks": [chunk]}, headers=HEADERS)
        assert r.status_code == 422

    def test_ingest_rejects_invalid_domain(self):
        chunk = {**self.VALID_CHUNK, "domain": "Politics"}
        r = self.client.post("/api/admin/ingest", json={"chunks": [chunk]}, headers=HEADERS)
        assert r.status_code == 422

    def test_ingest_multiple_chunks(self):
        _fake_retriever.ingest.return_value = 3
        chunks = [self.VALID_CHUNK] * 3
        r = self.client.post("/api/admin/ingest", json={"chunks": chunks}, headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["added"] == 3

    def test_ingest_generates_unique_chunk_ids(self):
        _fake_retriever.ingest.return_value = 1
        # Call twice and verify the IDs passed to ingest differ
        self.client.post("/api/admin/ingest", json={"chunks": [self.VALID_CHUNK]}, headers=HEADERS)
        call1_chunk = _fake_retriever.ingest.call_args[0][0][0]
        _fake_retriever.ingest.reset_mock()
        self.client.post("/api/admin/ingest", json={"chunks": [self.VALID_CHUNK]}, headers=HEADERS)
        call2_chunk = _fake_retriever.ingest.call_args[0][0][0]
        assert call1_chunk["id"] != call2_chunk["id"]


# ===========================================================================
# DELETE /api/admin/ingest
# ===========================================================================

class TestDeleteChunks:
    client = TestClient(app)

    def test_delete_success_returns_200(self):
        _fake_retriever.delete.return_value = 1
        r = self.client.request("DELETE", "/api/admin/ingest", json={"ids": ["chunk_abc"]}, headers=HEADERS)
        assert r.status_code == 200

    def test_delete_response_structure(self):
        _fake_retriever.delete.return_value = 1
        r = self.client.request("DELETE", "/api/admin/ingest", json={"ids": ["chunk_abc"]}, headers=HEADERS)
        data = r.json()
        assert data["ok"] is True
        assert "removed" in data
        assert "totalInIndex" in data

    def test_delete_calls_retriever(self):
        _fake_retriever.delete.return_value = 1
        self.client.request("DELETE", "/api/admin/ingest", json={"ids": ["chunk_abc"]}, headers=HEADERS)
        _fake_retriever.delete.assert_called_once_with(["chunk_abc"])

    def test_delete_logs_admin_action(self):
        _fake_retriever.delete.return_value = 1
        self.client.request("DELETE", "/api/admin/ingest", json={"ids": ["chunk_abc"]}, headers=HEADERS)
        _fake_db.log_admin_action.assert_called_once()
        assert _fake_db.log_admin_action.call_args.kwargs["action"] == "delete"

    def test_delete_rejects_empty_ids(self):
        r = self.client.request("DELETE", "/api/admin/ingest", json={"ids": []}, headers=HEADERS)
        assert r.status_code == 422


# ===========================================================================
# GET /api/admin/chunks
# ===========================================================================

class TestListChunks:
    client = TestClient(app)

    def test_returns_empty_list_when_no_chunks(self):
        _fake_retriever._store.meta = []
        r = self.client.get("/api/admin/chunks", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["chunks"] == []
        assert data["total"] == 0

    def test_returns_live_chunks(self):
        _fake_retriever._store.meta = [
            {"id": "c1", "domain": "Legal", "topic": "RTI", "text": "Right to Information..."},
            {"id": "c2", "domain": "Mental Health", "topic": "Anxiety", "text": "Anxiety coping..."},
        ]
        _fake_retriever._store._deleted_ids = set()
        r = self.client.get("/api/admin/chunks", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["total"] == 2

    def test_domain_filter_works(self):
        _fake_retriever._store.meta = [
            {"id": "c1", "domain": "Legal", "topic": "RTI", "text": "RTI text here..."},
            {"id": "c2", "domain": "Mental Health", "topic": "Anxiety", "text": "Anxiety text..."},
        ]
        _fake_retriever._store._deleted_ids = set()
        r = self.client.get("/api/admin/chunks?domain=Legal", headers=HEADERS)
        data = r.json()
        assert data["total"] == 1
        assert data["chunks"][0]["domain"] == "Legal"

    def test_deleted_chunks_excluded(self):
        _fake_retriever._store.meta = [
            {"id": "c1", "domain": "Legal", "topic": "RTI", "text": "live chunk text..."},
            {"id": "c2", "domain": "Legal", "topic": "Old", "text": "deleted chunk..."},
        ]
        _fake_retriever._store._deleted_ids = {"c2"}
        r = self.client.get("/api/admin/chunks?domain=Legal", headers=HEADERS)
        assert r.json()["total"] == 1
        assert r.json()["chunks"][0]["id"] == "c1"

    def test_pagination_page_2(self):
        _fake_retriever._store.meta = [
            {"id": f"c{i}", "domain": "Legal", "topic": f"T{i}", "text": f"text {i}" * 5}
            for i in range(10)
        ]
        _fake_retriever._store._deleted_ids = set()
        r = self.client.get("/api/admin/chunks?page=2&page_size=3", headers=HEADERS)
        data = r.json()
        assert data["page"] == 2
        assert len(data["chunks"]) == 3

    def test_null_index_returns_empty(self):
        _fake_retriever._store.index = None
        r = self.client.get("/api/admin/chunks", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["chunks"] == []
        # Restore
        _fake_retriever._store.index = MagicMock()
        _fake_retriever._store.index.ntotal = 100


# ===========================================================================
# GET /api/admin/audit
# ===========================================================================

class TestAuditLog:
    client = TestClient(app)

    def test_returns_empty_entries(self):
        _fake_db.fetch_audit_log.return_value = []
        r = self.client.get("/api/admin/audit", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["entries"] == []
        assert r.json()["count"] == 0

    def test_returns_audit_entries(self):
        _fake_db.fetch_audit_log.return_value = [
            {"action": "ingest", "detail": {"added": 5}, "ts": "2026-01-01T10:00:00"},
        ]
        r = self.client.get("/api/admin/audit", headers=HEADERS)
        data = r.json()
        assert data["count"] == 1
        assert data["entries"][0]["action"] == "ingest"

    def test_limit_param_is_forwarded(self):
        _fake_db.fetch_audit_log.return_value = []
        self.client.get("/api/admin/audit?limit=200", headers=HEADERS)
        _fake_db.fetch_audit_log.assert_called_once_with(limit=200)

    def test_limit_out_of_range_rejected(self):
        r = self.client.get("/api/admin/audit?limit=999", headers=HEADERS)
        assert r.status_code == 422


# ===========================================================================
# GET /api/admin/snapshots
# ===========================================================================

class TestSnapshots:
    client = TestClient(app)

    def test_returns_snapshot_list(self):
        _fake_retriever._store.list_snapshots.return_value = [{"name": "snap1"}, {"name": "snap2"}]
        r = self.client.get("/api/admin/snapshots", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        assert len(data["snapshots"]) == 2

    def test_empty_snapshots(self):
        _fake_retriever._store.list_snapshots.return_value = []
        r = self.client.get("/api/admin/snapshots", headers=HEADERS)
        assert r.json()["count"] == 0


# ===========================================================================
# POST /api/admin/rollback
# ===========================================================================

class TestRollback:
    client = TestClient(app)

    def test_rollback_success(self):
        _fake_retriever._store.rollback.return_value = True
        r = self.client.post("/api/admin/rollback", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["steps"] == 1

    def test_rollback_custom_steps(self):
        _fake_retriever._store.rollback.return_value = True
        r = self.client.post("/api/admin/rollback?steps=3", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["steps"] == 3

    def test_rollback_no_snapshot_returns_409(self):
        _fake_retriever._store.rollback.return_value = False
        r = self.client.post("/api/admin/rollback", headers=HEADERS)
        assert r.status_code == 409

    def test_rollback_logs_action(self):
        _fake_retriever._store.rollback.return_value = True
        self.client.post("/api/admin/rollback", headers=HEADERS)
        _fake_db.log_admin_action.assert_called_once()
        assert _fake_db.log_admin_action.call_args.kwargs["action"] == "rollback"

    def test_rollback_steps_out_of_range_rejected(self):
        r = self.client.post("/api/admin/rollback?steps=10", headers=HEADERS)
        assert r.status_code == 422


# ===========================================================================
# GET /api/admin/knowledge-gaps
# ===========================================================================

class TestKnowledgeGaps:
    client = TestClient(app)

    def test_returns_gap_list(self):
        _fake_db.fetch_knowledge_gaps.return_value = [
            {"_id": "g1", "query": "How to apply for PMJAY?", "status": "open"},
        ]
        r = self.client.get("/api/admin/knowledge-gaps", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["gaps"][0]["query"] == "How to apply for PMJAY?"

    def test_status_filter_forwarded(self):
        _fake_db.fetch_knowledge_gaps.return_value = []
        self.client.get("/api/admin/knowledge-gaps?status=open", headers=HEADERS)
        _fake_db.fetch_knowledge_gaps.assert_called_once_with(status="open", limit=100)

    def test_empty_gaps(self):
        _fake_db.fetch_knowledge_gaps.return_value = []
        r = self.client.get("/api/admin/knowledge-gaps", headers=HEADERS)
        assert r.json()["count"] == 0


# ===========================================================================
# PATCH /api/admin/knowledge-gaps/{gap_id}
# ===========================================================================

class TestUpdateGap:
    client = TestClient(app)

    def test_mark_gap_solved(self):
        _fake_db.update_knowledge_gap.return_value = True
        r = self.client.patch(
            "/api/admin/knowledge-gaps/g1",
            json={"status": "solved"},
            headers=HEADERS,
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["status"] == "solved"

    def test_mark_gap_ignored(self):
        _fake_db.update_knowledge_gap.return_value = True
        r = self.client.patch(
            "/api/admin/knowledge-gaps/g1",
            json={"status": "ignored"},
            headers=HEADERS,
        )
        assert r.status_code == 200

    def test_invalid_status_rejected(self):
        r = self.client.patch(
            "/api/admin/knowledge-gaps/g1",
            json={"status": "deleted"},
            headers=HEADERS,
        )
        assert r.status_code == 422

    def test_gap_not_found_returns_404(self):
        _fake_db.update_knowledge_gap.return_value = False
        r = self.client.patch(
            "/api/admin/knowledge-gaps/nonexistent",
            json={"status": "solved"},
            headers=HEADERS,
        )
        assert r.status_code == 404


# ===========================================================================
# GET /api/admin/analytics
# ===========================================================================

class TestAnalytics:
    client = TestClient(app)

    def test_returns_analytics_dict(self):
        _fake_db.fetch_feedback_stats.return_value = {"total": 10, "up": 8, "down": 2}
        _fake_db.fetch_knowledge_gaps.return_value = []
        _fake_db.fetch_document_registry.return_value = []
        r = self.client.get("/api/admin/analytics", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "feedback" in data
        assert "knowledgeGaps" in data
        assert "rag" in data
        assert "documents" in data

    def test_rag_section_reflects_readiness(self):
        _fake_db.fetch_feedback_stats.return_value = {}
        _fake_db.fetch_knowledge_gaps.return_value = []
        _fake_db.fetch_document_registry.return_value = []
        r = self.client.get("/api/admin/analytics", headers=HEADERS)
        assert r.json()["rag"]["ragReady"] is True

    def test_knowledge_gaps_open_count(self):
        _fake_db.fetch_feedback_stats.return_value = {}
        _fake_db.fetch_knowledge_gaps.return_value = [
            {"_id": "g1", "status": "open"},
            {"_id": "g2", "status": "open"},
        ]
        _fake_db.fetch_document_registry.return_value = []
        r = self.client.get("/api/admin/analytics", headers=HEADERS)
        assert r.json()["knowledgeGaps"]["open"] == 2


# ===========================================================================
# GET /api/admin/documents
# ===========================================================================

class TestListDocuments:
    client = TestClient(app)

    def test_returns_document_list(self):
        _fake_db.fetch_document_registry.return_value = [
            {"docId": "doc_abc", "filename": "guide.pdf", "domain": "Legal", "status": "active"},
        ]
        r = self.client.get("/api/admin/documents", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["documents"][0]["filename"] == "guide.pdf"

    def test_empty_documents(self):
        _fake_db.fetch_document_registry.return_value = []
        r = self.client.get("/api/admin/documents", headers=HEADERS)
        assert r.json()["total"] == 0

    def test_domain_filter_forwarded(self):
        _fake_db.fetch_document_registry.return_value = []
        self.client.get("/api/admin/documents?domain=Legal", headers=HEADERS)
        call_kwargs = _fake_db.fetch_document_registry.call_args.kwargs
        assert call_kwargs.get("domain") == "Legal"


# ===========================================================================
# GET /api/admin/documents/{doc_id}
# ===========================================================================

class TestGetDocument:
    client = TestClient(app)

    def test_returns_404_for_missing_doc(self):
        _fake_db.fetch_document_by_id.return_value = None
        r = self.client.get("/api/admin/documents/doc_missing", headers=HEADERS)
        assert r.status_code == 404

    def test_returns_document_with_live_chunks(self):
        _fake_db.fetch_document_by_id.return_value = {
            "docId": "doc_abc",
            "filename": "guide.pdf",
            "domain": "Legal",
            "chunkIds": ["doc_abc_c000"],
        }
        _fake_retriever._store.meta = [
            {"id": "doc_abc_c000", "domain": "Legal", "topic": "Guide", "text": "Guide text..."}
        ]
        _fake_retriever._store._deleted_ids = set()
        r = self.client.get("/api/admin/documents/doc_abc", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["docId"] == "doc_abc"
        assert len(data["liveChunks"]) == 1


# ===========================================================================
# DELETE /api/admin/documents/{doc_id}
# ===========================================================================

class TestDeleteDocument:
    client = TestClient(app)

    DOC = {
        "docId": "doc_abc",
        "filename": "guide.pdf",
        "domain": "Legal",
        "chunkIds": ["doc_abc_c000"],
        "status": "active",
    }

    def test_soft_delete_returns_ok(self):
        _fake_db.fetch_document_by_id.return_value = self.DOC
        _fake_retriever.delete.return_value = 1
        r = self.client.delete("/api/admin/documents/doc_abc", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_soft_delete_calls_update_status(self):
        _fake_db.fetch_document_by_id.return_value = self.DOC
        _fake_retriever.delete.return_value = 1
        self.client.delete("/api/admin/documents/doc_abc", headers=HEADERS)
        _fake_db.update_document_status.assert_called_once_with("doc_abc", "deleted")

    def test_hard_delete_calls_delete_from_registry(self):
        _fake_db.fetch_document_by_id.return_value = self.DOC
        _fake_retriever.delete.return_value = 1
        self.client.delete("/api/admin/documents/doc_abc?hard=true", headers=HEADERS)
        _fake_db.delete_document_from_registry.assert_called_once_with("doc_abc")

    def test_delete_missing_doc_returns_404(self):
        _fake_db.fetch_document_by_id.return_value = None
        r = self.client.delete("/api/admin/documents/doc_missing", headers=HEADERS)
        assert r.status_code == 404

    def test_delete_logs_admin_action(self):
        _fake_db.fetch_document_by_id.return_value = self.DOC
        _fake_retriever.delete.return_value = 1
        self.client.delete("/api/admin/documents/doc_abc", headers=HEADERS)
        _fake_db.log_admin_action.assert_called_once()
        assert "delete" in _fake_db.log_admin_action.call_args.kwargs["action"]


# ===========================================================================
# POST /api/admin/documents/{doc_id}/restore
# ===========================================================================

class TestRestoreDocument:
    client = TestClient(app)

    def test_restore_success(self):
        _fake_db.update_document_status.return_value = True
        r = self.client.post("/api/admin/documents/doc_abc/restore", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["status"] == "active"

    def test_restore_logs_action(self):
        _fake_db.update_document_status.return_value = True
        self.client.post("/api/admin/documents/doc_abc/restore", headers=HEADERS)
        _fake_db.log_admin_action.assert_called_once()
        assert _fake_db.log_admin_action.call_args.kwargs["action"] == "restore_document"

    def test_restore_not_found_returns_404(self):
        _fake_db.update_document_status.return_value = False
        r = self.client.post("/api/admin/documents/doc_missing/restore", headers=HEADERS)
        assert r.status_code == 404


# ===========================================================================
# POST /api/admin/ingest-document (file upload)
# ===========================================================================

class TestIngestDocument:
    client = TestClient(app)

    def _txt_file(self, content: str, name: str = "test.txt"):
        return ("file", (name, io.BytesIO(content.encode()), "text/plain"))

    def test_txt_upload_success(self):
        _fake_retriever.ingest.return_value = 2
        text = ("This is a test paragraph about mental health.\n\n" * 20)
        r = self.client.post(
            "/api/admin/ingest-document?domain=Mental+Health",
            files=[self._txt_file(text)],
            headers=HEADERS,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "docId" in data
        assert data["chunksAdded"] >= 1

    def test_unsupported_file_type_returns_415(self):
        r = self.client.post(
            "/api/admin/ingest-document?domain=Legal",
            files=[("file", ("test.exe", io.BytesIO(b"binary"), "application/octet-stream"))],
            headers=HEADERS,
        )
        assert r.status_code == 415

    def test_empty_file_returns_422(self):
        r = self.client.post(
            "/api/admin/ingest-document?domain=Legal",
            files=[self._txt_file("   ", "empty.txt")],
            headers=HEADERS,
        )
        assert r.status_code == 422

    def test_ingest_document_saves_to_registry(self):
        _fake_retriever.ingest.return_value = 1
        text = "Knowledge about legal rights.\n\n" * 10
        self.client.post(
            "/api/admin/ingest-document?domain=Legal",
            files=[self._txt_file(text)],
            headers=HEADERS,
        )
        _fake_db.save_document_registry.assert_called_once()

    def test_ingest_document_logs_action(self):
        _fake_retriever.ingest.return_value = 1
        text = "Knowledge about government schemes.\n\n" * 10
        self.client.post(
            "/api/admin/ingest-document?domain=Government+Schemes",
            files=[self._txt_file(text)],
            headers=HEADERS,
        )
        _fake_db.log_admin_action.assert_called_once()
        assert _fake_db.log_admin_action.call_args.kwargs["action"] == "ingest_document"

    def test_json_file_accepted(self):
        _fake_retriever.ingest.return_value = 1
        content = '{"info": "' + ("legal information about contracts. " * 20) + '"}'
        r = self.client.post(
            "/api/admin/ingest-document?domain=Legal",
            files=[("file", ("data.json", io.BytesIO(content.encode()), "application/json"))],
            headers=HEADERS,
        )
        assert r.status_code == 200

    def test_md_file_accepted(self):
        _fake_retriever.ingest.return_value = 1
        content = "# Safety Guide\n\n" + ("This section covers safety procedures. " * 20)
        r = self.client.post(
            "/api/admin/ingest-document?domain=Safety",
            files=[("file", ("guide.md", io.BytesIO(content.encode()), "text/markdown"))],
            headers=HEADERS,
        )
        assert r.status_code == 200


# ===========================================================================
# GET /api/admin/crawler/sources
# ===========================================================================

class TestCrawlerSources:
    client = TestClient(app)

    def test_returns_empty_when_no_sources(self):
        cursor_mock = MagicMock()
        cursor_mock.to_list = AsyncMock(return_value=[])
        _fake_db._db.__getitem__.return_value.find.return_value = cursor_mock
        r = self.client.get("/api/admin/crawler/sources", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "sources" in data
        assert "count" in data

    def test_returns_source_records(self):
        cursor_mock = MagicMock()
        cursor_mock.to_list = AsyncMock(return_value=[
            {"sourceId": "indiacode", "url": "https://indiacode.nic.in", "status": "ok"},
            {"sourceId": "nalsa",     "url": "https://nalsa.gov.in",     "status": "pending"},
        ])
        _fake_db._db.__getitem__.return_value.find.return_value = cursor_mock
        r = self.client.get("/api/admin/crawler/sources", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["count"] == 2
        ids = [s["sourceId"] for s in r.json()["sources"]]
        assert "indiacode" in ids
        assert "nalsa" in ids

    def test_db_error_returns_503(self):
        _fake_db._db.__getitem__.side_effect = Exception("DB down")
        r = self.client.get("/api/admin/crawler/sources", headers=HEADERS)
        assert r.status_code == 503
        # Restore
        _fake_db._db.__getitem__.side_effect = None


# ===========================================================================
# POST /api/admin/crawler/trigger
# ===========================================================================

class TestCrawlerTrigger:
    client = TestClient(app)

    def test_trigger_returns_ok(self):
        r = self.client.post("/api/admin/crawler/trigger", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "message" in data

    def test_trigger_logs_admin_action(self):
        self.client.post("/api/admin/crawler/trigger", headers=HEADERS)
        _fake_db.log_admin_action.assert_called_once()
        assert _fake_db.log_admin_action.call_args.kwargs["action"] == "trigger_crawler"

    def test_trigger_response_includes_message(self):
        r = self.client.post("/api/admin/crawler/trigger", headers=HEADERS)
        assert len(r.json()["message"]) > 10


# ===========================================================================
# Chunk text helper — tested directly (no HTTP)
# ===========================================================================

from routes.admin import _chunk_text


class TestChunkText:
    def test_short_text_produces_one_chunk(self):
        text = "This is a short paragraph about mental health coping strategies."
        chunks = _chunk_text(text)
        assert len(chunks) >= 1

    def test_long_text_splits_into_multiple_chunks(self):
        para = "This is an important paragraph about the Right to Information Act. " * 10
        text = "\n\n".join([para] * 5)
        chunks = _chunk_text(text)
        assert len(chunks) > 1

    def test_chunks_have_minimum_length(self):
        text = "\n\n".join(["Valid paragraph text about legal rights." * 3] * 8)
        chunks = _chunk_text(text)
        assert all(len(c) >= 20 for c in chunks)

    def test_empty_string_returns_empty(self):
        assert _chunk_text("") == []

    def test_whitespace_only_returns_empty(self):
        assert _chunk_text("   \n\n   ") == []

    def test_chunks_preserve_content(self):
        keyword = "POCSO Act protects children"
        text = f"{keyword} from sexual offences.\n\n" + ("Additional legal context. " * 20)
        chunks = _chunk_text(text)
        combined = " ".join(chunks)
        assert keyword in combined

    def test_excess_newlines_normalised(self):
        text = "Paragraph one.\n\n\n\n\nParagraph two about safety.\n\n\n\nParagraph three on health."
        chunks = _chunk_text(text)
        assert len(chunks) >= 1
