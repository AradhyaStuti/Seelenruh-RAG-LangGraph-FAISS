"""slowapi rate limiting. Keys on JWT subject when authenticated, falls back to IP."""
import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from config import JWT_SECRET, JWT_ALG, REDIS_URL


def _user_or_ip(request: Request) -> str:
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass
    return f"ip:{get_remote_address(request)}"


# Use Redis for persistent rate-limit counters across restarts/replicas when
# REDIS_URL is configured; fall back to in-process memory otherwise.
_storage_uri = REDIS_URL if REDIS_URL else "memory://"
limiter = Limiter(key_func=_user_or_ip, default_limits=[], storage_uri=_storage_uri)


def auth_limit(spec: str = "10/minute"):
    """Stricter limit for auth routes (defends against credential stuffing)."""
    return limiter.limit(spec)


def chat_limit(spec: str = "30/minute"):
    """Limit chat endpoints — protects the Groq quota."""
    return limiter.limit(spec)


def burst_limit(spec: str = "60/minute"):
    """Looser limit for the lower-cost endpoints (history fetch, summary, etc.)."""
    return limiter.limit(spec)


__all__ = ["limiter", "auth_limit", "chat_limit", "burst_limit"]
