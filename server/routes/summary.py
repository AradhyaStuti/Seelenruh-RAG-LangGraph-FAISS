"""Conversation summary endpoints.

POST /api/summary           — generate + upsert a fresh summary
GET  /api/summary/{persona}/{sessionId} — fetch the pinned summary, if any
GET  /api/summary/all       — every summary the user has (cross-device hydrate)
"""
from fastapi import APIRouter, Depends, HTTPException, Request

from schemas import SummaryRequest, SummaryResponse, PinnedSummary, AllSummariesResponse
from auth import current_user
from rate_limit import chat_limit, burst_limit
from ai import summarizer
import db

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.post("", response_model=SummaryResponse)
@chat_limit("12/minute")
async def summary_endpoint(
    request: Request, req: SummaryRequest, user: dict = Depends(current_user),
) -> SummaryResponse:
    """Generate a summary from posted messages and persist it server-side so
    the same user sees it on a different device next time they load this
    persona+session."""
    messages = [m.model_dump() for m in req.messages]
    summary = await summarizer.summarize(messages)
    if summary and req.sessionId:
        await db.upsert_summary(
            user_id=user["id"],
            persona=req.persona or "Mental Health",
            session_id=req.sessionId,
            summary=summary,
        )
    return SummaryResponse(summary=summary)


@router.get("/all", response_model=AllSummariesResponse)
@burst_limit("60/minute")
async def all_summaries_endpoint(
    request: Request, user: dict = Depends(current_user),
) -> AllSummariesResponse:
    """Used at app load to hydrate any session summaries the user wrote on
    other devices — pinned card appears immediately, no extra round-trip per
    session."""
    rows = await db.fetch_user_summaries(user["id"])
    return AllSummariesResponse(summaries=[PinnedSummary(**r) for r in rows])


@router.get("/{persona}/{session_id}", response_model=PinnedSummary)
@burst_limit("60/minute")
async def get_summary_endpoint(
    request: Request, persona: str, session_id: str,
    user: dict = Depends(current_user),
) -> PinnedSummary:
    doc = await db.fetch_summary(user_id=user["id"], persona=persona, session_id=session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No summary pinned for this session.")
    return PinnedSummary(
        persona=persona,
        sessionId=session_id,
        summary=doc["summary"],
        updatedAt=doc["updatedAt"],
    )
