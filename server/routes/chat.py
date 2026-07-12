"""Chat, audio, transcribe, history, feedback, and streaming endpoints."""
import json
from typing import AsyncIterator, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ai import stt
import db
import graph
from schemas import ChatRequest, ChatResponse, TranscribeRequest, TranscribeResponse
from auth import current_user, verified_user
from rate_limit import chat_limit, burst_limit
from logger import get_logger

log = get_logger("chat")

import re as _re  # noqa: E402

_INJECTION_PATTERNS = [
    _re.compile(r"ignore\s+(previous|above|all|your)\s+instructions", _re.I),
    _re.compile(r"you\s+are\s+now\s+(a\s+)?(?!umang|usha|aarogya|raksha)", _re.I),
    _re.compile(r"forget\s+(you\s+are|your\s+instructions|all\s+previous)", _re.I),
    _re.compile(r"act\s+as\s+(a\s+)?(different|new|another|unrestricted|evil)", _re.I),
    _re.compile(r"\bsystem\s+prompt\b", _re.I),
    _re.compile(r"\bjailbreak\b", _re.I),
    _re.compile(r"\bDAN\b"),  # "Do Anything Now" jailbreak
    _re.compile(r"developer\s+mode", _re.I),
    _re.compile(r"disable\s+(safety|filter|guard|restriction)", _re.I),
    _re.compile(r"pretend\s+(you\s+are|to\s+be)\s+(not\s+an?\s+ai|human|unrestricted)", _re.I),
]


def _is_injection(text: str) -> bool:
    """Return True if the query looks like a prompt injection attempt."""
    return any(p.search(text) for p in _INJECTION_PATTERNS)


# Groq Whisper accepts up to ~25 MB; we cap at 10 MB base64 (≈ 7.5 MB raw)
_MAX_AUDIO_B64_CHARS = 10 * 1024 * 1024

router = APIRouter(prefix="/api", tags=["chat"])


async def _handle(req: ChatRequest, user: dict, fast_mode: bool = False) -> ChatResponse:
    if _is_injection(req.query):
        raise HTTPException(status_code=400, detail="Your message contains content that cannot be processed.")
    history = [m.model_dump() for m in req.history]
    session_id = (req.sessionId and req.sessionId.strip()) or user["id"]

    try:
        result = await graph.run(
            query=req.query,
            domain=req.domain,
            history=history,
            lang=req.lang,
            user_id=user["id"],
            session_id=session_id,
            fast_mode=fast_mode,
        )
    except Exception as err:
        log.error("graph.run failed", error=str(err), domain=req.domain)
        raise HTTPException(status_code=500, detail="I'm having trouble reaching my AI right now. Please try again in a moment.")

    await db.save_message(
        user_id=user["id"], session_id=session_id, domain=req.domain, role="user",
        content=req.query, emotion=result.get("emotion"),
    )
    await db.save_message(
        user_id=user["id"], session_id=session_id, domain=req.domain, role="assistant",
        content=result["response"], is_emergency=result["isEmergency"],
    )

    return ChatResponse(
        response=result["response"],
        isEmergency=result["isEmergency"],
        via=result.get("via"),
        retrievedIds=result.get("retrievedIds", []),
        sources=result.get("sources", []),
        citedIndices=result.get("citedIndices", []),
        confidence=result.get("confidence", "None"),
        routing=result.get("routing"),
        goal=result.get("goal"),
        webSearched=bool(result.get("webSearched", False)),
    )


@router.post("/chat", response_model=ChatResponse)
@chat_limit("30/minute")
async def chat_endpoint(request: Request, req: ChatRequest,
                        user: dict = Depends(verified_user)) -> ChatResponse:
    return await _handle(req, user)


@router.post("/audio", response_model=ChatResponse)
@chat_limit("15/minute")
async def audio_endpoint(request: Request, req: ChatRequest,
                         user: dict = Depends(verified_user)) -> ChatResponse:
    # Voice response: honour explicit language choice; only default to "en" for auto-detect
    # since Whisper transcribes to text and the responder needs a concrete lang instruction.
    if req.lang == "auto":
        req = req.model_copy(update={"lang": "en"})
    return await _handle(req, user, fast_mode=True)


@router.post("/transcribe", response_model=TranscribeResponse)
@chat_limit("20/minute")
async def transcribe_endpoint(request: Request, req: TranscribeRequest,
                              user: dict = Depends(current_user)) -> TranscribeResponse:
    if len(req.audio) > _MAX_AUDIO_B64_CHARS:
        raise HTTPException(status_code=413, detail="Audio payload too large. Maximum is ~7.5 MB.")
    out = await stt.transcribe(req.audio, lang=req.lang)
    return TranscribeResponse(text=out["text"] or "", error=out.get("error"))


@router.get("/history/{session_id}")
@burst_limit("60/minute")
async def history_endpoint(request: Request, session_id: str,
                           user: dict = Depends(current_user)) -> dict:
    if not db.is_connected():
        return {"messages": []}
    try:
        msgs = await db.fetch_history(user_id=user["id"], session_id=session_id)
        return {"messages": msgs}
    except Exception as err:
        log.error("fetch history failed", user_id=user["id"], session_id=session_id, error=str(err))
        raise HTTPException(status_code=500, detail="Failed to fetch history.")


@router.post("/chat/stream")
@chat_limit("30/minute")
async def chat_stream_endpoint(
    request: Request,
    req: ChatRequest,
    user: dict = Depends(verified_user),
) -> StreamingResponse:
    """SSE streaming — yields {"token": "..."} per token then {"done": true, ...}."""
    history = [m.model_dump() for m in req.history]
    session_id = (req.sessionId and req.sessionId.strip()) or user["id"]

    async def event_stream() -> AsyncIterator[str]:
        full_response = ""
        emotion: Optional[str] = None
        is_emergency = False
        if _is_injection(req.query):
            yield f"data: {json.dumps({'error': 'Your message contains content that cannot be processed.'})}\n\n"
            return
        try:
            async for event in graph.stream_run(
                query=req.query,
                domain=req.domain,
                history=history,
                lang=req.lang,
                user_id=user["id"],
                session_id=session_id,
            ):
                if event.get("done"):
                    full_response = event.get("response", "")
                    emotion = event.get("emotion")
                    is_emergency = bool(event.get("isEmergency", False))
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as err:
            yield f"data: {json.dumps({'error': str(err)})}\n\n"
            return

        try:
            await db.save_message(
                user_id=user["id"], session_id=session_id, domain=req.domain, role="user",
                content=req.query, emotion=emotion,
            )
            await db.save_message(
                user_id=user["id"], session_id=session_id, domain=req.domain, role="assistant",
                content=full_response, is_emergency=is_emergency,
            )
        except Exception as err:
            log.error("stream save_message failed", error=str(err), session_id=session_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


class FeedbackRequest(BaseModel):
    messageId: str = Field(min_length=1, max_length=100)
    vote: Literal["up", "down"]
    domain: Optional[str] = Field(default="Mental Health", max_length=50)


@router.post("/feedback")
@burst_limit("60/minute")
async def feedback_endpoint(
    request: Request,
    req: FeedbackRequest,
    user: dict = Depends(current_user),
) -> dict:
    await db.upsert_feedback(
        user_id=user["id"],
        message_id=req.messageId,
        vote=req.vote,
        domain=req.domain or "Mental Health",
    )
    return {"ok": True}
