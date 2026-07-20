"""Conversation export endpoints.

GET /api/export/{session_id}?format=json   — full history as JSON
GET /api/export/{session_id}?format=md     — human-readable Markdown
GET /api/export/{session_id}?format=txt    — plain text transcript

All formats include: timestamps, persona/domain, message content.
Requires authentication (token must belong to the session owner).
"""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from auth import current_user
from rate_limit import burst_limit
import db

router = APIRouter(prefix="/api/export", tags=["export"])


def _fmt_ts(ts) -> str:
    """Format a MongoDB timestamp or ISO string to readable datetime."""
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d %H:%M UTC")
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return ts
    return str(ts) if ts else ""


def _to_json(messages: list[dict], session_id: str, user: dict) -> str:
    export = {
        "export": {
            "sessionId": session_id,
            "exportedAt": datetime.now(timezone.utc).isoformat(),
            "user": {"name": user.get("name", ""), "email": user.get("email", "")},
            "messageCount": len(messages),
        },
        "messages": [
            {
                "role": m.get("role"),
                "content": m.get("content"),
                "domain": m.get("domain"),
                "timestamp": _fmt_ts(m.get("createdAt")),
                "isEmergency": m.get("isEmergency", False),
            }
            for m in messages
        ],
    }
    return json.dumps(export, ensure_ascii=False, indent=2)


def _to_markdown(messages: list[dict], session_id: str, user: dict) -> str:
    lines = [
        "# Seelenruh — Conversation Export",
        "",
        f"**Session:** `{session_id}`  ",
        f"**Exported:** {_fmt_ts(datetime.now(timezone.utc))}  ",
        f"**User:** {user.get('name') or user.get('email', 'Unknown')}",
        f"**Messages:** {len(messages)}",
        "",
        "---",
        "",
    ]
    for m in messages:
        role = m.get("role", "unknown")
        domain = m.get("domain", "")
        ts = _fmt_ts(m.get("createdAt"))
        label = "**You**" if role == "user" else f"**Seelenruh** _{domain}_"
        emergency = " 🚨 *Emergency flagged*" if m.get("isEmergency") else ""
        lines.append(f"### {label}{emergency}")
        lines.append(f"*{ts}*")
        lines.append("")
        lines.append(m.get("content", ""))
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def _to_txt(messages: list[dict], session_id: str, user: dict) -> str:
    lines = [
        "SEELENRUH CONVERSATION EXPORT",
        f"Session: {session_id}",
        f"Exported: {_fmt_ts(datetime.now(timezone.utc))}",
        f"User: {user.get('name') or user.get('email', 'Unknown')}",
        f"{'=' * 60}",
        "",
    ]
    for m in messages:
        role = "You" if m.get("role") == "user" else f"Seelenruh [{m.get('domain', '')}]"
        ts = _fmt_ts(m.get("createdAt"))
        lines.append(f"[{ts}] {role}")
        lines.append(m.get("content", ""))
        lines.append("-" * 40)
        lines.append("")
    return "\n".join(lines)


@router.get("/{session_id}")
@burst_limit("10/minute")
async def export_conversation(
    request: Request,
    session_id: str,
    format: Optional[str] = Query(default="json", pattern="^(json|md|txt)$"),
    user: dict = Depends(current_user),
) -> Response:
    """Export a conversation session in the requested format.

    Formats: `json` (default), `md` (Markdown), `txt` (plain text).
    """
    if not db.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable — cannot export history.")

    messages = await db.fetch_history(user_id=user["id"], session_id=session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="No messages found for this session.")

    safe_id = session_id.replace("/", "_").replace("..", "")[:64]

    if format == "json":
        content = _to_json(messages, session_id, user)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="seelenruh_{safe_id}.json"'},
        )
    if format == "md":
        content = _to_markdown(messages, session_id, user)
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="seelenruh_{safe_id}.md"'},
        )
    # txt
    content = _to_txt(messages, session_id, user)
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="seelenruh_{safe_id}.txt"'},
    )
