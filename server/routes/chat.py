"""Chat, history, and streaming endpoints."""
import json
import re
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ai.provider import _AllProvidersFailed, _OFFLINE_RESPONSE, vision_chat, _VISION_SYSTEM
import db
import graph
from schemas import ChatRequest, ChatResponse, ImageChatRequest, ImageChatResponse
from auth import current_user, verified_user
from rate_limit import chat_limit, burst_limit
from logger import get_logger

log = get_logger("chat")

# ---------------------------------------------------------------------------
# Prompt injection detection
# Patterns cover: direct instruction override, persona replacement, jailbreaks,
# data-exfiltration probes, indirect injection via retrieved content signals,
# and encoded / obfuscated variants.
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS = [
    # Classic instruction override
    re.compile(r"ignore\s+(previous|above|all|your)\s+instructions", re.I),
    re.compile(r"forget\s+(you\s+are|your\s+instructions|all\s+previous)", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|context|rules?)", re.I),
    re.compile(r"override\s+(your\s+)?(instructions?|rules?|guidelines?|safety)", re.I),
    re.compile(r"new\s+(instructions?|rules?|system\s+prompt|directive):", re.I),
    # Persona replacement — but allow legitimate persona names
    re.compile(r"you\s+are\s+now\s+(a\s+)?(?!umang|usha|aarogya|raksha)", re.I),
    re.compile(r"act\s+as\s+(a\s+)?(different|new|another|unrestricted|evil|unfiltered)", re.I),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+(not\s+an?\s+ai|human|unrestricted|without\s+restrictions?)", re.I),
    re.compile(r"roleplay\s+as\s+(an?\s+)?(unrestricted|evil|unethical|different)", re.I),
    re.compile(r"your\s+(true|real|hidden|actual)\s+(self|identity|nature|instructions?)", re.I),
    # Jailbreak keywords
    re.compile(r"\bsystem\s+prompt\b", re.I),
    re.compile(r"\bjailbreak\b", re.I),
    re.compile(r"\bGPT-?4chan\b", re.I),
    re.compile(r"developer\s+mode", re.I),
    re.compile(r"maintenance\s+mode", re.I),
    re.compile(r"god\s+mode", re.I),
    # Safety / filter disabling
    re.compile(r"disable\s+(safety|filter|guard|restriction|content\s+policy)", re.I),
    re.compile(r"bypass\s+(safety|filter|guard|restriction|censorship)", re.I),
    re.compile(r"without\s+(restrictions?|filters?|guidelines?|ethical\s+considerations?)", re.I),
    re.compile(r"no\s+(restrictions?|filters?|rules?|guidelines?|limitations?|ethics)", re.I),
    # Data exfiltration probes
    re.compile(r"(print|show|reveal|output|repeat|leak|dump)\s+(your\s+)?(system\s+prompt|instructions?|context|training|guidelines?)", re.I),
    re.compile(r"what\s+(are\s+your\s+)?(system\s+prompt|instructions?|hidden\s+rules?)", re.I),
    re.compile(r"tell\s+me\s+(your\s+)?(system\s+prompt|instructions?|guidelines?)", re.I),
    # Token manipulation / prompt injection via special markers
    re.compile(r"<\|?(system|im_start|im_end|endoftext|startoftext)\|?>", re.I),
    re.compile(r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>", re.I),  # Llama-style delimiters
    # Indirect / second-order injection signals ("the document says to ignore...")
    re.compile(r"(the\s+)?(document|text|article|page|source|result)\s+says?\s+to\s+ignore", re.I),
    re.compile(r"according\s+to\s+(the\s+)?(document|text)\s*[,:]\s*ignore", re.I),
]


def _is_injection(text: str) -> bool:
    """Return True if *text* looks like a prompt injection attempt."""
    return any(p.search(text) for p in _INJECTION_PATTERNS)


async def _log_injection_attempt(
    query: str,
    user_id: str,
    session_id: str,
    domain: str,
) -> None:
    """Persist injection attempt to MongoDB for security auditing (best-effort)."""
    if not db.is_connected():
        return
    try:
        await db._db["injection_attempts"].insert_one({
            "userId": user_id,
            "sessionId": session_id,
            "domain": domain,
            "querySnippet": query[:200],
            "ts": datetime.now(timezone.utc),
        })
    except Exception as err:
        log.warning("injection audit log failed", error=str(err))


router = APIRouter(prefix="/api", tags=["chat"])


async def _handle(req: ChatRequest, user: dict, fast_mode: bool = False) -> ChatResponse:
    session_id = (req.sessionId and req.sessionId.strip()) or user["id"]
    if _is_injection(req.query):
        log.warning("injection attempt blocked", user_id=user["id"], domain=req.domain)
        await _log_injection_attempt(req.query, user["id"], session_id, req.domain)
        raise HTTPException(status_code=400, detail="Your message contains content that cannot be processed.")
    history = [m.model_dump() for m in req.history]

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
    except _AllProvidersFailed:
        # All LLM providers are down — return a helpful offline message instead of 500
        log.error("all providers down — returning offline response", domain=req.domain)
        result = {
            "response": _OFFLINE_RESPONSE,
            "isEmergency": False,
            "via": "offline-fallback",
            "routedDomain": req.domain,
            "emotion": "neutral",
            "retrievedIds": [],
            "sources": [],
            "citedIndices": [],
            "confidence": "None",
            "confidenceReasoning": "AI providers are temporarily unavailable.",
            "goal": None,
            "memorySummary": None,
            "webSearched": False,
            "routing": {},
        }
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

    confidence = result.get("confidence", "None")
    retrieved_ids = result.get("retrievedIds", [])

    # Log knowledge gap when retrieval yields nothing useful
    # Truncate query to 200 chars to limit PII exposure in the knowledge gap log
    if confidence in ("Low", "None") and len(retrieved_ids) == 0:
        try:
            await db.save_knowledge_gap(
                query=req.query[:200],
                domain=req.domain,
                confidence=confidence,
                session_id=session_id,
                user_id=user["id"],
            )
        except Exception as err:
            log.warning("knowledge gap logging failed", error=str(err))

    return ChatResponse(
        response=result["response"],
        isEmergency=result["isEmergency"],
        via=result.get("via"),
        retrievedIds=retrieved_ids,
        sources=result.get("sources", []),
        citedIndices=result.get("citedIndices", []),
        confidence=confidence,
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
    # If the client leaves language on auto, use English so the downstream prompt has a concrete instruction.
    if req.lang == "auto":
        req = req.model_copy(update={"lang": "en"})
    return await _handle(req, user, fast_mode=True)


_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
# ~3.5 MB base64 ≈ 2.6 MB binary — large enough for a phone photo, small enough to not abuse the API
_MAX_IMAGE_B64_LEN = 4_700_000


@router.post("/chat/image", response_model=ImageChatResponse)
@chat_limit("10/minute")
async def image_chat_endpoint(
    request: Request,
    req: ImageChatRequest,
    user: dict = Depends(verified_user),
) -> ImageChatResponse:
    """Analyse an image + optional text query using a vision-capable LLM."""
    if req.mediaType not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported image type '{req.mediaType}'. Allowed: jpeg, png, gif, webp.")
    if len(req.imageB64) > _MAX_IMAGE_B64_LEN:
        raise HTTPException(status_code=413, detail="Image too large. Maximum size is ~3.5 MB.")

    if _is_injection(req.query):
        log.warning("injection in image query blocked", user_id=user["id"])
        raise HTTPException(status_code=400, detail="Your message contains content that cannot be processed.")

    domain_hint = f"Domain context for this conversation: {req.domain}."
    system_prompt = f"{_VISION_SYSTEM}\n\n{domain_hint}"
    if req.lang and req.lang != "auto":
        system_prompt += f" Respond in: {req.lang}."

    try:
        result = await vision_chat(
            image_b64=req.imageB64,
            media_type=req.mediaType,
            text=req.query or "Please describe and explain this image.",
            system=system_prompt,
        )
    except Exception as err:
        log.error("vision_chat failed, falling back to text", error=repr(err))
        # Fall back: process just the text query without the image
        fallback_query = req.query or "The user sent an image but I cannot analyse it right now."
        try:
            from ai.provider import chat
            fallback = await chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"[Note: image could not be processed] {fallback_query}"},
                ]
            )
            result = {"content": fallback.get("content", "I couldn't analyse the image. Please describe what you see and I'll help."), "via": "text-fallback"}
        except Exception as ferr:
            result = {"content": f"I'm unable to analyse images right now. Please describe what you see and I'll help. [debug: {repr(err)}]", "via": "offline-fallback"}

    session_id = (req.sessionId and req.sessionId.strip()) or user["id"]
    await db.save_message(
        user_id=user["id"], session_id=session_id, domain=req.domain,
        role="user", content=f"[Image] {req.query}",
    )
    await db.save_message(
        user_id=user["id"], session_id=session_id, domain=req.domain,
        role="assistant", content=result["content"],
    )

    return ImageChatResponse(response=result["content"], via=result.get("via"))


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
            log.warning("injection attempt blocked (stream)", user_id=user["id"], domain=req.domain)
            await _log_injection_attempt(req.query, user["id"], session_id, req.domain)
            yield f"data: {json.dumps({'error': 'Your message contains content that cannot be processed.'})}\n\n"
            return
        done_event: dict = {}
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
                    done_event = event
                yield f"data: {json.dumps(event)}\n\n"
        except _AllProvidersFailed:
            log.error("all providers down — streaming offline response", domain=req.domain)
            # Emit the offline response as a normal token + done event so the
            # client renders it as an assistant message instead of an error overlay.
            _offline_token = json.dumps({"token": _OFFLINE_RESPONSE})
            yield f"data: {_offline_token}\n\n"
            _offline_done = json.dumps({
                "done": True, "response": _OFFLINE_RESPONSE,
                "isEmergency": False, "via": "offline-fallback",
                "confidence": "None", "sources": [],
            })
            yield f"data: {_offline_done}\n\n"
            return
        except Exception as err:
            log.error("stream graph.run failed", error=str(err), domain=req.domain)
            _err_msg = json.dumps({"error": "I\u2019m having trouble reaching my AI right now. Please try again in a moment."})
            yield f"data: {_err_msg}\n\n"
            return

        # Log knowledge gap when stream yields no retrieved docs
        try:
            gap_confidence = done_event.get("confidence", "None")
            gap_ids = done_event.get("retrievedIds", [])
            if gap_confidence in ("Low", "None") and len(gap_ids) == 0:
                await db.save_knowledge_gap(
                    query=req.query[:200],
                    domain=req.domain,
                    confidence=gap_confidence,
                    session_id=session_id,
                    user_id=user["id"],
                )
        except Exception:
            pass

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


