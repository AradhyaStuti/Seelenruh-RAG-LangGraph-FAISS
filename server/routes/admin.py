"""Admin endpoints — guarded by ADMIN_KEY env var.

POST   /api/admin/ingest          — add new knowledge chunks to the live RAG index
DELETE /api/admin/ingest          — soft-delete chunks by ID
GET    /api/admin/status          — index size + readiness check
GET    /api/admin/chunks          — list all live chunks (paginated)
GET    /api/admin/audit           — last 100 admin actions

All mutating operations are written to the audit_log collection in MongoDB.
Set ADMIN_KEY to a strong random string in .env to enable these endpoints.
"""
import asyncio
import io
import re
import uuid
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile
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


# ---------------------------------------------------------------------------
# Knowledge gap endpoints
# ---------------------------------------------------------------------------

GapStatus = Literal["open", "solved", "ignored"]


@router.get("/knowledge-gaps")
async def list_knowledge_gaps(
    x_admin_key: Optional[str] = Header(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    """List low-confidence queries that the RAG system couldn't answer well."""
    _check_key(x_admin_key)
    gaps = await db.fetch_knowledge_gaps(status=status, limit=limit)
    return {"gaps": gaps, "count": len(gaps)}


class GapUpdateRequest(BaseModel):
    status: GapStatus


@router.patch("/knowledge-gaps/{gap_id}")
async def update_gap(
    gap_id: str,
    req: GapUpdateRequest,
    x_admin_key: Optional[str] = Header(default=None),
) -> dict:
    """Mark a knowledge gap as solved or ignored."""
    _check_key(x_admin_key)
    ok = await db.update_knowledge_gap(gap_id, req.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Gap not found or already updated.")
    return {"ok": True, "status": req.status}


# ---------------------------------------------------------------------------
# Analytics dashboard
# ---------------------------------------------------------------------------

@router.get("/analytics")
async def analytics_dashboard(
    x_admin_key: Optional[str] = Header(default=None),
) -> dict:
    """Return aggregate stats for the admin analytics dashboard."""
    _check_key(x_admin_key)
    feedback_stats, knowledge_gaps, documents = await asyncio.gather(
        db.fetch_feedback_stats(),
        db.fetch_knowledge_gaps(status="open", limit=500),
        db.fetch_document_registry(limit=500),
    )
    rag_status = {
        "ragReady": retriever.is_ready(),
        "chunksInIndex": retriever._store.size() if retriever.is_ready() else 0,
    }
    return {
        "feedback": feedback_stats,
        "knowledgeGaps": {"open": len(knowledge_gaps)},
        "rag": rag_status,
        "documents": {
            "total": len(documents),
            "active": sum(1 for d in documents if d.get("status") == "active"),
        },
    }


# ---------------------------------------------------------------------------
# Document management helpers
# ---------------------------------------------------------------------------

_CHUNK_SIZE = 480
_CHUNK_OVERLAP = 60
_ADMIN_UPLOAD_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_ADMIN_ACCEPTED = {".pdf", ".docx", ".md", ".txt", ".json"}


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks at paragraph boundaries."""
    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if not current:
            current = para
        elif len(current) + len(para) + 2 <= _CHUNK_SIZE:
            current = current + "\n\n" + para
        else:
            if len(current) >= 30:
                chunks.append(current)
            # Carry overlap from end of current into next chunk
            tail = current[-_CHUNK_OVERLAP:].strip() if len(current) > _CHUNK_OVERLAP else current
            current = (tail + "\n\n" + para).strip() if tail else para

    if current and len(current) >= 30:
        chunks.append(current)

    # Fall back to sentence splitting for paragraphs that are still too long
    final: list[str] = []
    for chunk in chunks:
        if len(chunk) <= _CHUNK_SIZE * 1.5:
            final.append(chunk)
        else:
            sentences = re.split(r"(?<=[.!?])\s+", chunk)
            buf = ""
            for sent in sentences:
                if len(buf) + len(sent) <= _CHUNK_SIZE:
                    buf = (buf + " " + sent).strip()
                else:
                    if buf:
                        final.append(buf)
                    buf = sent
            if buf:
                final.append(buf)

    return [c for c in final if len(c) >= 20]


def _extract_text_from_bytes(data: bytes, suffix: str) -> str:
    if suffix == ".pdf":
        try:
            import pdfplumber
            parts: list[str] = []
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    parts.append(page.extract_text() or "")
            return "\n\n".join(parts)
        except ImportError:
            raise HTTPException(status_code=415, detail="pdfplumber not installed.")
    if suffix == ".docx":
        try:
            from docx import Document
            doc = Document(io.BytesIO(data))
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            raise HTTPException(status_code=415, detail="python-docx not installed.")
    return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Document management endpoints
# ---------------------------------------------------------------------------

@router.post("/ingest-document")
async def ingest_document(
    file: UploadFile = File(...),
    domain: str = Query(...),
    topic: str = Query(default=""),
    source: Optional[str] = Query(default=None),
    language: str = Query(default="en"),
    x_admin_key: Optional[str] = Header(default=None),
) -> dict:
    """Upload a document, auto-chunk, embed, and add to the live RAG index.

    Returns the document ID, chunk count, and a list of chunk IDs on success.
    Does NOT restart the server — index update is live immediately.
    """
    _check_key(x_admin_key)

    filename = file.filename or "upload"
    suffix = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""
    if suffix not in _ADMIN_ACCEPTED:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported type '{suffix}'. Accepted: {', '.join(sorted(_ADMIN_ACCEPTED))}",
        )

    data = await file.read()
    if len(data) > _ADMIN_UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(data)//1024} KB). Max is {_ADMIN_UPLOAD_MAX_BYTES//1024} KB.",
        )

    # Extract text
    try:
        raw_text = await asyncio.to_thread(_extract_text_from_bytes, data, suffix)
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {err}")

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from the file.")

    # Chunk
    text_chunks = _chunk_text(raw_text)
    if not text_chunks:
        raise HTTPException(status_code=422, detail="File produced no usable chunks after splitting.")

    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    today = date.today().isoformat()
    chunk_topic = topic.strip() or filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")

    raw_chunks = [
        {
            "id": f"{doc_id}_c{i:03d}",
            "domain": domain,
            "topic": chunk_topic,
            "text": chunk,
            "source": source,
            "lastVerifiedOn": today,
            "verifiedBy": "admin-upload",
        }
        for i, chunk in enumerate(text_chunks)
    ]

    added = await retriever.ingest(raw_chunks)
    chunk_ids = [c["id"] for c in raw_chunks]

    # Persist to document registry
    await db.save_document_registry(
        doc_id=doc_id,
        filename=filename,
        domain=domain,
        file_type=suffix,
        chunk_ids=chunk_ids,
        size_bytes=len(data),
        source=source,
        language=language,
        topic=chunk_topic,
    )

    await db.log_admin_action(
        action="ingest_document",
        detail={
            "docId": doc_id,
            "filename": filename,
            "domain": domain,
            "chunks": added,
            "sizeBytes": len(data),
        },
    )

    return {
        "ok": True,
        "docId": doc_id,
        "filename": filename,
        "chunksAdded": added,
        "chunkIds": chunk_ids,
        "totalInIndex": retriever._store.size(),
    }


@router.get("/documents")
async def list_documents(
    x_admin_key: Optional[str] = Header(default=None),
    domain: Optional[str] = Query(default=None),
    file_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    """List all admin-uploaded documents with metadata."""
    _check_key(x_admin_key)
    docs = await db.fetch_document_registry(
        domain=domain, file_type=file_type, status=status, limit=limit
    )
    return {"documents": docs, "total": len(docs)}


@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    x_admin_key: Optional[str] = Header(default=None),
) -> dict:
    """Get full document details including all chunk IDs."""
    _check_key(x_admin_key)
    doc = await db.fetch_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Enrich with live chunk data from the FAISS index
    store = retriever._store
    live_chunks = []
    if store.index is not None:
        chunk_id_set = set(doc.get("chunkIds", []))
        live_chunks = [m for m in store.meta if m["id"] in chunk_id_set and m["id"] not in store._deleted_ids]

    return {**doc, "liveChunks": live_chunks}


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    hard: bool = Query(default=False, description="If true, permanently remove chunks from FAISS"),
    x_admin_key: Optional[str] = Header(default=None),
) -> dict:
    """Soft-delete (default) or hard-delete a document and all its chunks."""
    _check_key(x_admin_key)
    doc = await db.fetch_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    chunk_ids = doc.get("chunkIds", [])

    if hard:
        removed = await retriever.delete(chunk_ids) if chunk_ids else 0
        await db.delete_document_from_registry(doc_id)
        action = "hard_delete_document"
    else:
        removed = await retriever.delete(chunk_ids) if chunk_ids else 0
        await db.update_document_status(doc_id, "deleted")
        action = "soft_delete_document"

    await db.log_admin_action(
        action=action,
        detail={"docId": doc_id, "filename": doc.get("filename"), "chunksRemoved": removed},
    )
    return {"ok": True, "docId": doc_id, "chunksRemoved": removed}


@router.post("/documents/{doc_id}/restore")
async def restore_document(
    doc_id: str,
    x_admin_key: Optional[str] = Header(default=None),
) -> dict:
    """Restore a soft-deleted document (marks as active; chunks must be re-ingested separately)."""
    _check_key(x_admin_key)
    ok = await db.update_document_status(doc_id, "active")
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found.")
    await db.log_admin_action(action="restore_document", detail={"docId": doc_id})
    return {"ok": True, "docId": doc_id, "status": "active"}
