"""Admin endpoints — guarded by ADMIN_KEY env var.

POST   /api/admin/ingest          — add new knowledge chunks to the live RAG index
DELETE /api/admin/ingest          — soft-delete chunks by ID
GET    /api/admin/status          — index size + readiness check
GET    /api/admin/chunks          — list all live chunks (paginated)
GET    /api/admin/audit           — last 100 admin actions

All mutating operations are written to the audit_log collection in MongoDB.
Set ADMIN_KEY to a strong random string in .env to enable these endpoints.
"""
import uuid
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from config import ADMIN_KEY
from rag import retriever
import db

router = APIRouter(prefix="/api/admin", tags=["admin"])

Domain = Literal["Mental Health", "Legal", "Government Schemes", "Safety"]


def _check_key(x_admin_key: Optional[str]) -> None:
    if not ADMIN_KEY:
        raise HTTPException(status_code=503, detail="Admin endpoints are disabled (ADMIN_KEY not set).")
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key.")


class IngestChunk(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    domain: Domain
    text: str = Field(min_length=10, max_length=4000)
    source: Optional[str] = Field(default=None, max_length=500)
    lastVerifiedOn: Optional[str] = Field(default=None)
    verifiedBy: Optional[str] = Field(default="admin", max_length=100)


class IngestRequest(BaseModel):
    chunks: list[IngestChunk] = Field(min_length=1, max_length=50)


class IngestResponse(BaseModel):
    ok: bool
    added: int
    totalInIndex: int


@router.post("/ingest", response_model=IngestResponse)
async def ingest_chunks(
    req: IngestRequest,
    x_admin_key: Optional[str] = Header(default=None),
) -> IngestResponse:
    """Add new knowledge chunks to the live FAISS index.

    Example request body:
    {
      "chunks": [
        {
          "domain": "Legal",
          "topic": "Digital Personal Data Protection Act 2023",
          "text": "The DPDP Act 2023 gives citizens the right to...",
          "source": "https://meity.gov.in/dpdp",
          "lastVerifiedOn": "2025-01-15"
        }
      ]
    }
    """
    _check_key(x_admin_key)

    today = date.today().isoformat()
    raw_chunks = [
        {
            "id": f"admin_{uuid.uuid4().hex[:8]}",
            "domain": c.domain,
            "topic": c.topic,
            "text": c.text,
            "source": c.source,
            "lastVerifiedOn": c.lastVerifiedOn or today,
            "verifiedBy": c.verifiedBy or "admin",
        }
        for c in req.chunks
    ]

    added = await retriever.ingest(raw_chunks)

    await db.log_admin_action(
        action="ingest",
        detail={
            "added": added,
            "chunks": [{"id": c["id"], "topic": c["topic"], "domain": c["domain"]} for c in raw_chunks],
        },
    )

    return IngestResponse(ok=True, added=added, totalInIndex=retriever._store.size())


class DeleteRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=200)


@router.delete("/ingest", response_model=dict)
async def delete_chunks(
    req: DeleteRequest,
    x_admin_key: Optional[str] = Header(default=None),
) -> dict:
    """Soft-delete knowledge chunks by their ID.

    Deleted chunks are hidden from search immediately. Background compaction
    rebuilds the index when deleted waste exceeds 30%.
    """
    _check_key(x_admin_key)
    removed = await retriever.delete(req.ids)

    await db.log_admin_action(
        action="delete",
        detail={"requested": len(req.ids), "removed": removed, "ids": req.ids},
    )

    return {"ok": True, "removed": removed, "totalInIndex": retriever._store.size()}


@router.get("/status")
async def admin_status(
    x_admin_key: Optional[str] = Header(default=None),
) -> dict:
    """Return current index size, readiness, and compaction stats."""
    _check_key(x_admin_key)
    store = retriever._store
    return {
        "ragReady": retriever.is_ready(),
        "chunksInIndex": store.size(),
        "totalVectors": store.index.ntotal if store.index else 0,
        "deletedVectors": len(store._deleted_ids),
        "compactionNeeded": store.should_compact(),
    }


@router.get("/chunks")
async def list_chunks(
    x_admin_key: Optional[str] = Header(default=None),
    domain: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> dict:
    """Browse all live (non-deleted) knowledge chunks with optional domain filter."""
    _check_key(x_admin_key)
    store = retriever._store
    if store.index is None:
        return {"chunks": [], "total": 0, "page": page, "pageSize": page_size}

    live = [
        m for m in store.meta
        if m["id"] not in store._deleted_ids
        and (domain is None or m["domain"] == domain)
    ]
    total = len(live)
    start = (page - 1) * page_size
    return {"chunks": live[start : start + page_size], "total": total, "page": page, "pageSize": page_size}


@router.get("/audit")
async def audit_log(
    x_admin_key: Optional[str] = Header(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    """Return the most recent admin actions in reverse chronological order."""
    _check_key(x_admin_key)
    entries = await db.fetch_audit_log(limit=limit)
    return {"entries": entries, "count": len(entries)}


@router.get("/snapshots")
async def list_snapshots(
    x_admin_key: Optional[str] = Header(default=None),
) -> dict:
    """List available FAISS index snapshots (up to 5 most recent saves)."""
    _check_key(x_admin_key)
    snapshots = retriever._store.list_snapshots()
    return {"snapshots": snapshots, "count": len(snapshots)}


@router.post("/rollback")
async def rollback_index(
    steps: int = Query(default=1, ge=1, le=5),
    x_admin_key: Optional[str] = Header(default=None),
) -> dict:
    """Roll back the FAISS index to a previous snapshot.

    `steps=1` (default) restores the most recent snapshot (the state just
    before the last save). `steps=2` goes one further back, and so on.
    Returns 409 if the requested snapshot does not exist.
    """
    _check_key(x_admin_key)
    async with retriever._write_lock:
        ok = retriever._store.rollback(steps=steps)
    if not ok:
        raise HTTPException(status_code=409, detail=f"Snapshot {steps} not found.")

    await db.log_admin_action(
        action="rollback",
        detail={"steps": steps, "chunksAfter": retriever._store.size()},
    )
    return {"ok": True, "steps": steps, "totalInIndex": retriever._store.size()}
