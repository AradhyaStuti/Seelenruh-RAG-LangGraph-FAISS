"""JWT + bcrypt auth. Falls back to in-memory user store when MongoDB isn't configured."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import bcrypt
import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import JWT_SECRET, JWT_ALG, JWT_ACCESS_TTL_MINUTES, JWT_REFRESH_TTL_DAYS
import db
from logger import get_logger

log = get_logger("auth")

_bearer = HTTPBearer(auto_error=False)

# Fallback when MongoDB isn't configured (handy for local dev).
_memory_users: dict[str, dict] = {}
_memory_blacklist: dict[str, datetime] = {}  # jti -> expiry


def _to_bytes(plain: str) -> bytes:
    return plain.encode("utf-8")[:72]  # bcrypt only looks at first 72 bytes


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_to_bytes(plain), bcrypt.gensalt(rounds=12)).decode("utf-8")


# dummy hash so authenticate() takes the same time whether the email exists or not
_DUMMY_HASH = bcrypt.hashpw(b"", bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(plain), hashed.encode("utf-8"))
    except Exception:
        return False


def make_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "jti": uuid4().hex,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=JWT_ACCESS_TTL_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def make_refresh_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "jti": uuid4().hex,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=JWT_REFRESH_TTL_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)



def decode_token(token: str, expected_type: Optional[str] = None) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        if expected_type and payload.get("type") != expected_type:
            raise HTTPException(status_code=401, detail="Wrong token type.")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def revoke_token(jti: str, expires_at: datetime) -> None:
    if not jti:
        return
    if db.is_connected():
        try:
            await db._db["revoked_tokens"].update_one(
                {"jti": jti},
                {"$set": {"jti": jti, "expiresAt": expires_at}},
                upsert=True,
            )
            return
        except Exception as err:
            log.warning("failed to persist revoked token, using memory fallback", error=str(err))
    _memory_blacklist[jti] = expires_at


def _as_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    # Mongo returns naive UTC; normalise both sides before comparing
    # (previously caused revoked tokens to appear valid — took a while to find)
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _is_revoked(jti: Optional[str]) -> bool:
    if not jti:
        return False  # legacy tokens without jti — can't revoke individually
    now = datetime.now(timezone.utc)
    if db.is_connected():
        try:
            doc = await db._db["revoked_tokens"].find_one({"jti": jti})
        except Exception as err:
            # Fail-closed on a real DB error — better to inconvenience a
            # legitimate user than to honour a revoked token because Mongo
            # was briefly unreachable.
            log.error("revoked-token lookup failed, failing closed", jti=jti, error=str(err))
            return True
        if doc is None:
            return False
        exp = _as_aware_utc(doc.get("expiresAt"))
        if exp and exp < now:
            await db._db["revoked_tokens"].delete_one({"jti": jti})
            return False
        return True
    exp = _as_aware_utc(_memory_blacklist.get(jti))
    if exp is None:
        return False
    if exp < now:
        _memory_blacklist.pop(jti, None)
        return False
    return True


class EmailAlreadyRegistered(Exception):
    """Internal only — routes catch this and return a generic message."""


async def create_user(*, email: str, name: str, password: str) -> dict:
    email = email.lower().strip()
    # hash before existence check so signup timing doesn't leak whether the email is taken
    hashed = hash_password(password)
    existing = await find_user_by_email(email)
    if existing:
        raise EmailAlreadyRegistered(email)
    user = {
        "email": email,
        "name": name.strip() or email.split("@")[0],
        "password": hashed,
        "createdAt": datetime.now(timezone.utc),
        "emailVerified": True,
    }
    if db.is_connected():
        result = await db.users().insert_one(user)
        user["_id"] = str(result.inserted_id)
    else:
        user["_id"] = email
        _memory_users[email] = user
    return user


async def find_user_by_email(email: str) -> Optional[dict]:
    email = email.lower().strip()
    if db.is_connected():
        u = await db.users().find_one({"email": email})
        if u:
            u["_id"] = str(u["_id"])
        return u
    return _memory_users.get(email)


async def authenticate(*, email: str, password: str) -> Optional[dict]:
    user = await find_user_by_email(email)
    # always run bcrypt even on user-miss to prevent timing-based email enumeration
    if not user:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user["password"]):
        return None
    return user


async def delete_user(user_id: str, email: str) -> bool:
    if db.is_connected():
        try:
            oid = ObjectId(user_id)
        except (InvalidId, TypeError):
            return False
        result = await db.users().delete_one({"_id": oid})
        return bool(result.deleted_count)
    return _memory_users.pop(email.lower().strip(), None) is not None


async def _resolve_user(credentials: HTTPAuthorizationCredentials, *, require_verified: bool) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials, expected_type="access")
    if await _is_revoked(payload.get("jti")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if require_verified:
        user_record = await find_user_by_email(payload["email"])
        if user_record and not user_record.get("emailVerified", True):
            raise HTTPException(
                status_code=403,
                detail="Email not verified. Please check your inbox or resend from settings.",
            )
    return {"id": payload["sub"], "email": payload["email"], "jti": payload.get("jti")}


async def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    return await _resolve_user(credentials, require_verified=False)


async def verified_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Requires email verified — use for chat/data routes."""
    return await _resolve_user(credentials, require_verified=True)


async def current_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Returns full JWT payload — used by /logout to get the jti for blacklisting."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(credentials.credentials)
