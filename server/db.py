"""Optional MongoDB persistence (motor async)."""
import asyncio
from datetime import datetime
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from config import MONGODB_URI, MONGODB_DB
from logger import get_logger

log = get_logger("db")

_client: Optional[AsyncIOMotorClient] = None
_db = None


async def connect() -> bool:
    global _client, _db
    if not MONGODB_URI:
        log.warning("MONGODB_URI not set — using in-memory user store (dev only)")
        return False
    try:
        _client = AsyncIOMotorClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=8000,
            connectTimeoutMS=8000,
            retryWrites=True,
        )
        await _client.admin.command("ping")
        _db = _client[MONGODB_DB]
        await _db["messages"].create_index([("userId", 1), ("sessionId", 1)])
        await _db["messages"].create_index("createdAt", expireAfterSeconds=90 * 24 * 3600)
        await _db["users"].create_index("email", unique=True)
        await _db["revoked_tokens"].create_index("jti", unique=True)
        await _db["revoked_tokens"].create_index("expiresAt", expireAfterSeconds=3600)
        await _db["summaries"].create_index(
            [("userId", 1), ("persona", 1), ("sessionId", 1)],
            unique=True,
        )
        await _db["session_memory"].create_index(
            [("userId", 1), ("sessionId", 1)], unique=True
        )
        await _db["session_memory"].create_index("updatedAt", expireAfterSeconds=90 * 24 * 3600)
        await _db["goals"].create_index(
            [("userId", 1), ("sessionId", 1), ("domain", 1)], unique=True
        )
        await _db["goals"].create_index("updatedAt", expireAfterSeconds=90 * 24 * 3600)
        await _db["password_resets"].create_index("createdAt", expireAfterSeconds=3600)
        await _db["password_resets"].create_index("email", unique=True)
        await _db["email_verifications"].create_index("createdAt", expireAfterSeconds=86400)
        await _db["email_verifications"].create_index("email", unique=True)
        await _db["audit_log"].create_index("createdAt", expireAfterSeconds=365 * 24 * 3600)
        await _db["feedback"].create_index(
            [("userId", 1), ("messageId", 1)], unique=True
        )
        await _db["user_memory"].create_index("userId", unique=True)
        await _db["login_attempts"].create_index("email", unique=True)
        await _db["login_attempts"].create_index("updatedAt", expireAfterSeconds=15 * 60)
        host = (_client.address or ("?", 0))[0]
        log.info("MongoDB connected", db=MONGODB_DB, host=host)
        return True
    except Exception as err:
        log.error("MongoDB connection failed — falling back to in-memory store", error=str(err))
        _client = None
        _db = None
        return False


def is_connected() -> bool:
    return _db is not None


def users() -> AsyncIOMotorCollection:
    if _db is None:
        raise RuntimeError("MongoDB not connected")
    return _db["users"]


def messages() -> AsyncIOMotorCollection:
    if _db is None:
        raise RuntimeError("MongoDB not connected")
    return _db["messages"]


async def save_message(*, user_id: str, session_id: str, domain: str, role: str,
                       content: str, emotion: Optional[str] = None,
                       is_emergency: bool = False) -> None:
    if not is_connected() or not session_id or not user_id:
        return
    try:
        await _db["messages"].insert_one({
            "userId": user_id,
            "sessionId": session_id,
            "domain": domain,
            "role": role,
            "content": content,
            "emotion": emotion,
            "isEmergency": is_emergency,
            "createdAt": datetime.utcnow(),
        })
    except Exception as err:
        log.error("failed to save message", error=str(err))


async def fetch_history(*, user_id: str, session_id: str, limit: int = 500) -> list[dict]:
    if not is_connected() or not user_id:
        return []
    cursor = (
        _db["messages"]
        .find({"userId": user_id, "sessionId": session_id})
        .sort("createdAt", 1)
        .limit(limit)
    )
    return [
        {**doc, "_id": str(doc["_id"]), "createdAt": doc["createdAt"].isoformat()}
        async for doc in cursor
    ]


async def delete_messages_for_session(*, user_id: str, session_id: str) -> int:
    if not is_connected() or not session_id or not user_id:
        return 0
    try:
        result = await _db["messages"].delete_many(
            {"userId": user_id, "sessionId": session_id}
        )
        return int(result.deleted_count or 0)
    except Exception as err:
        log.error("failed to delete messages for session", session_id=session_id, error=str(err))
        return 0


async def delete_messages_for_user(user_id: str) -> int:
    if not is_connected() or not user_id:
        return 0
    try:
        result = await _db["messages"].delete_many({"userId": user_id})
        return int(result.deleted_count or 0)
    except Exception as err:
        log.error("failed to delete messages for user", user_id=user_id, error=str(err))
        return 0


async def upsert_summary(*, user_id: str, persona: str, session_id: str, summary: str) -> bool:
    if not is_connected():
        return False
    try:
        await _db["summaries"].update_one(
            {"userId": user_id, "persona": persona, "sessionId": session_id},
            {"$set": {
                "userId": user_id,
                "persona": persona,
                "sessionId": session_id,
                "summary": summary,
                "updatedAt": datetime.utcnow(),
            }},
            upsert=True,
        )
        return True
    except Exception as err:
        log.error("failed to upsert summary", error=str(err))
        return False


async def fetch_summary(*, user_id: str, persona: str, session_id: str) -> Optional[dict]:
    if not is_connected():
        return None
    try:
        doc = await _db["summaries"].find_one({
            "userId": user_id, "persona": persona, "sessionId": session_id,
        })
        if not doc:
            return None
        return {
            "summary": doc.get("summary", ""),
            "updatedAt": doc["updatedAt"].isoformat() if doc.get("updatedAt") else None,
        }
    except Exception as err:
        log.error("failed to fetch summary", error=str(err))
        return None


async def fetch_user_summaries(user_id: str) -> list[dict]:
    if not is_connected():
        return []
    try:
        cursor = _db["summaries"].find({"userId": user_id})
        return [
            {
                "persona": d["persona"],
                "sessionId": d["sessionId"],
                "summary": d.get("summary", ""),
                "updatedAt": d["updatedAt"].isoformat() if d.get("updatedAt") else None,
            }
            async for d in cursor
        ]
    except Exception as err:
        log.error("failed to fetch user summaries", error=str(err))
        return []


async def delete_summaries_for_user(user_id: str) -> int:
    if not is_connected():
        return 0
    try:
        result = await _db["summaries"].delete_many({"userId": user_id})
        return int(result.deleted_count or 0)
    except Exception:
        return 0


async def save_session_memory(*, user_id: str, session_id: str,
                               summary: str, emotion_arc: list[str]) -> bool:
    if not is_connected() or not user_id or not session_id:
        return False
    try:
        await _db["session_memory"].update_one(
            {"userId": user_id, "sessionId": session_id},
            {"$set": {
                "userId": user_id,
                "sessionId": session_id,
                "summary": summary,
                "emotionArc": emotion_arc,
                "updatedAt": datetime.utcnow(),
            }},
            upsert=True,
        )
        return True
    except Exception as err:
        log.error("failed to save session memory", error=str(err))
        return False


async def fetch_session_memory(*, user_id: str, session_id: str) -> Optional[dict]:
    if not is_connected() or not user_id or not session_id:
        return None
    try:
        doc = await _db["session_memory"].find_one(
            {"userId": user_id, "sessionId": session_id}
        )
        if not doc:
            return None
        return {
            "summary": doc.get("summary", ""),
            "emotionArc": doc.get("emotionArc", []),
        }
    except Exception:
        return None


async def delete_session_memory_for_user(user_id: str) -> int:
    if not is_connected():
        return 0
    try:
        result = await _db["session_memory"].delete_many({"userId": user_id})
        return int(result.deleted_count or 0)
    except Exception:
        return 0


async def save_goal(*, user_id: str, session_id: str, domain: str, goal: str) -> bool:
    if not is_connected() or not user_id or not session_id:
        return False
    try:
        await _db["goals"].update_one(
            {"userId": user_id, "sessionId": session_id, "domain": domain},
            {"$set": {
                "userId": user_id,
                "sessionId": session_id,
                "domain": domain,
                "goal": goal,
                "updatedAt": datetime.utcnow(),
            }},
            upsert=True,
        )
        return True
    except Exception as err:
        log.error("failed to save goal", error=str(err))
        return False


async def fetch_goal(*, user_id: str, session_id: str, domain: str) -> Optional[str]:
    if not is_connected() or not user_id or not session_id:
        return None
    try:
        doc = await _db["goals"].find_one(
            {"userId": user_id, "sessionId": session_id, "domain": domain}
        )
        return doc.get("goal") if doc else None
    except Exception:
        return None


async def delete_goals_for_user(user_id: str) -> int:
    if not is_connected():
        return 0
    try:
        result = await _db["goals"].delete_many({"userId": user_id})
        return int(result.deleted_count or 0)
    except Exception:
        return 0


async def upsert_feedback(*, user_id: str, message_id: str, vote: str, domain: str) -> bool:
    if not is_connected() or not user_id:
        return False
    try:
        await _db["feedback"].update_one(
            {"userId": user_id, "messageId": message_id},
            {"$set": {
                "userId": user_id,
                "messageId": message_id,
                "vote": vote,
                "domain": domain,
                "updatedAt": datetime.utcnow(),
            }},
            upsert=True,
        )
        return True
    except Exception as err:
        log.error("failed to upsert feedback", error=str(err))
        return False


async def delete_feedback_for_user(user_id: str) -> int:
    if not is_connected():
        return 0
    try:
        result = await _db["feedback"].delete_many({"userId": user_id})
        return int(result.deleted_count or 0)
    except Exception as err:
        log.error("failed to delete feedback for user", user_id=user_id, error=str(err))
        return 0


async def upsert_user_memory(user_id: str) -> Optional[str]:
    """Aggregate the 8 most recent session summaries into a single user memory string."""
    if not is_connected() or not user_id:
        return None
    try:
        cursor = (
            _db["session_memory"]
            .find({"userId": user_id}, {"summary": 1, "updatedAt": 1})
            .sort("updatedAt", -1)
            .limit(8)
        )
        parts = [d["summary"] async for d in cursor if d.get("summary")]
        if not parts:
            return None
        user_memory = " | ".join(parts)
        await _db["user_memory"].update_one(
            {"userId": user_id},
            {"$set": {
                "userId": user_id,
                "memory": user_memory,
                "updatedAt": datetime.utcnow(),
            }},
            upsert=True,
        )
        return user_memory
    except Exception as err:
        log.error("failed to upsert user memory", error=str(err))
        return None


async def fetch_user_memory(user_id: str) -> Optional[str]:
    if not is_connected() or not user_id:
        return None
    try:
        doc = await _db["user_memory"].find_one({"userId": user_id})
        return doc.get("memory") if doc else None
    except Exception:
        return None


async def save_reset_token(*, email: str, token: str) -> bool:
    if not is_connected():
        return False
    try:
        await _db["password_resets"].update_one(
            {"email": email},
            {"$set": {"email": email, "token": token, "createdAt": datetime.utcnow()}},
            upsert=True,
        )
        return True
    except Exception as err:
        log.error("failed to save reset token", error=str(err))
        return False


async def consume_reset_token(*, token: str) -> Optional[str]:
    """Returns email on success, None if invalid or expired."""
    if not is_connected():
        return None
    try:
        doc = await _db["password_resets"].find_one({"token": token})
        if not doc:
            return None
        await _db["password_resets"].delete_one({"token": token})
        return doc["email"]
    except Exception:
        return None


async def save_verification_token(*, email: str, token: str) -> bool:
    if not is_connected():
        return False
    try:
        await _db["email_verifications"].update_one(
            {"email": email},
            {"$set": {"email": email, "token": token, "createdAt": datetime.utcnow()}},
            upsert=True,
        )
        return True
    except Exception as err:
        log.error("failed to save verification token", error=str(err))
        return False


async def consume_verification_token(*, token: str) -> Optional[str]:
    """Returns email on success, None if invalid."""
    if not is_connected():
        return None
    try:
        doc = await _db["email_verifications"].find_one({"token": token})
        if not doc:
            return None
        await _db["email_verifications"].delete_one({"token": token})
        return doc["email"]
    except Exception:
        return None


async def mark_email_verified(email: str) -> bool:
    if not is_connected():
        return False
    try:
        result = await _db["users"].update_one(
            {"email": email.lower().strip()},
            {"$set": {"emailVerified": True, "verifiedAt": datetime.utcnow()}},
        )
        return bool(result.modified_count)
    except Exception:
        return False


async def log_admin_action(*, action: str, detail: dict) -> None:
    if not is_connected():
        return
    try:
        await _db["audit_log"].insert_one({
            "action": action,
            "detail": detail,
            "createdAt": datetime.utcnow(),
        })
    except Exception:
        pass  # audit failure must never break the primary action


async def fetch_audit_log(limit: int = 100) -> list[dict]:
    if not is_connected():
        return []
    try:
        cursor = _db["audit_log"].find().sort("createdAt", -1).limit(limit)
        return [
            {**d, "_id": str(d["_id"]), "createdAt": d["createdAt"].isoformat()}
            async for d in cursor
        ]
    except Exception:
        return []


async def delete_user_memory(user_id: str) -> int:
    if not is_connected():
        return 0
    try:
        result = await _db["user_memory"].delete_many({"userId": user_id})
        return int(result.deleted_count or 0)
    except Exception:
        return 0


async def record_failed_login(email: str) -> int:
    """Increment failed-login counter. TTL on updatedAt auto-clears after 15 min."""
    if not is_connected():
        return 0
    try:
        doc = await _db["login_attempts"].find_one_and_update(
            {"email": email.lower().strip()},
            {
                "$inc": {"attempts": 1},
                "$set": {"updatedAt": datetime.utcnow()},
                "$setOnInsert": {"createdAt": datetime.utcnow()},
            },
            upsert=True,
            return_document=True,
        )
        return int(doc.get("attempts", 1)) if doc else 1
    except Exception as err:
        log.error("record_failed_login error", error=str(err))
        return 0


async def get_failed_login_count(email: str) -> int:
    if not is_connected():
        return 0
    try:
        doc = await _db["login_attempts"].find_one({"email": email.lower().strip()})
        return int(doc.get("attempts", 0)) if doc else 0
    except Exception:
        return 0


async def clear_failed_logins(email: str) -> None:
    if not is_connected():
        return
    try:
        await _db["login_attempts"].delete_one({"email": email.lower().strip()})
    except Exception:
        pass


async def export_user_data(user_id: str) -> dict:
    """Collect everything stored about a user — for data portability requests."""
    if not is_connected():
        return {"note": "No database connected — no server-side data stored."}

    async def _collect(collection: str, query: dict, project: dict | None = None) -> list[dict]:
        try:
            cursor = _db[collection].find(query, project or {}).sort("createdAt", 1).limit(5000)
            rows = []
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                for k, v in doc.items():
                    if isinstance(v, datetime):
                        doc[k] = v.isoformat()
                rows.append(doc)
            return rows
        except Exception:
            return []

    messages, summaries, session_mem, goals, feedback = await asyncio.gather(
        _collect("messages",      {"userId": user_id}, {"userId": 0}),
        _collect("summaries",     {"userId": user_id}, {"userId": 0}),
        _collect("session_memory",{"userId": user_id}, {"userId": 0}),
        _collect("goals",         {"userId": user_id}, {"userId": 0}),
        _collect("feedback",      {"userId": user_id}, {"userId": 0}),
    )

    return {
        "messages":      messages,
        "summaries":     summaries,
        "sessionMemory": session_mem,
        "goals":         goals,
        "feedback":      feedback,
    }
