"""
Feedback endpoints.

POST  /api/feedback          — save vote (fire-and-forget, no auth required)
GET   /api/feedback/stats    — aggregate stats (admin key required)
GET   /api/feedback/export   — CSV export (admin key required)
"""
import csv
from io import StringIO
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends
from pydantic import BaseModel, Field

from config import ADMIN_KEY
from rate_limit import burst_limit
from auth import decode_token
import db

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

_bearer = HTTPBearer(auto_error=False)


def _extract_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[str]:
    """Extract user_id from a Bearer token if present; return None for unauthenticated requests."""
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        return payload.get("sub")
    except Exception:
        return None


def _check_key(x_admin_key: Optional[str]) -> None:
    if not ADMIN_KEY:
        raise HTTPException(status_code=503, detail="Admin endpoints are disabled (ADMIN_KEY not set).")
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key.")


class FeedbackRequest(BaseModel):
    messageId: str = Field(min_length=1, max_length=200)
    vote: Literal["up", "down"]
    domain: str = Field(default="", max_length=60)
    query: Optional[str] = Field(default=None, max_length=2000)
    response: Optional[str] = Field(default=None, max_length=8000)
    confidence: Optional[str] = Field(default=None, max_length=20)
    persona: Optional[str] = Field(default=None, max_length=60)
    sessionId: Optional[str] = Field(default=None, max_length=200)


@router.post("")
@burst_limit("30/minute")
async def submit_feedback(
    request: Request,
    req: FeedbackRequest,
    user_id: Optional[str] = Depends(_extract_user_id),
) -> dict:
    """Save user feedback. Auth is optional — user_id is captured when token is present."""
    await db.save_feedback_log(
        message_id=req.messageId,
        vote=req.vote,
        domain=req.domain,
        query=req.query,
        response=req.response,
        confidence=req.confidence,
        persona=req.persona,
        session_id=req.sessionId,
        user_id=user_id,
    )
    return {"ok": True}


@router.get("/stats")
async def feedback_stats(
    x_admin_key: Optional[str] = Header(default=None),
) -> dict:
    """Return aggregate feedback statistics. Requires admin key."""
    _check_key(x_admin_key)
    return await db.fetch_feedback_stats()


_EXPORT_FIELDS = [
    "messageId", "vote", "domain", "persona", "confidence",
    "query", "response", "sessionId", "userId", "createdAt",
]


@router.get("/export")
async def export_feedback(
    x_admin_key: Optional[str] = Header(default=None),
):
    """Download all feedback as CSV. Requires admin key."""
    _check_key(x_admin_key)
    rows = await db.fetch_feedback_for_export()

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=_EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in _EXPORT_FIELDS})
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="feedback_export.csv"'},
    )
