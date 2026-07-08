"""Load all env vars once at import time."""
import os
from dotenv import load_dotenv

load_dotenv()

# Suppress the harmless HF symlink warning on Windows and prefer offline cache
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
PORT = int(os.getenv("PORT", "5000"))
CLIENT_ORIGIN = os.getenv("CLIENT_ORIGIN", "")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB = os.getenv("MONGODB_DB", "seelenruh")

GROQ_MODEL_SMART = "llama-3.3-70b-versatile"
GROQ_MODEL_FAST = "llama-3.1-8b-instant"
GROQ_MODEL_WHISPER = "whisper-large-v3-turbo"

EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
RETRIEVAL_TOP_K = 5
RETRIEVAL_OVERFETCH = 15  # reduced from 25 — fewer candidates = faster reranker on CPU

RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "1") == "1"

# Admin key for the /api/admin/* endpoints (ingest new RAG knowledge).
# Set a strong random value in .env for production. If unset, admin endpoints are disabled.
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

# Optional: Brave Search API for richer web results (https://api.search.brave.com)
BRAVE_SEARCH_KEY = os.getenv("BRAVE_SEARCH_KEY", "")

# Optional: ElevenLabs neural TTS (https://elevenlabs.io)
# Find your voice ID in the ElevenLabs dashboard — set ELEVENLABS_VOICE_ID in .env.
ELEVENLABS_KEY = os.getenv("ELEVENLABS_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

# Optional: Anthropic as third LLM fallback (after Groq + Ollama)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

# Optional: SMTP for sending password-reset and verification emails.
# If unset, tokens are logged to server console (dev mode).
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5173")

_DEV_JWT_SECRET = "change-me-in-production-please"
JWT_SECRET = os.getenv("JWT_SECRET", _DEV_JWT_SECRET)
JWT_ALG = "HS256"
JWT_ACCESS_TTL_MINUTES = int(os.getenv("JWT_ACCESS_TTL_MINUTES", "15"))
JWT_REFRESH_TTL_DAYS = int(os.getenv("JWT_REFRESH_TTL_DAYS", "30"))

# Account lockout: lock after N consecutive failures, heals after 15 min TTL.
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "10"))

# Redis URL for persistent rate-limit counters. Falls back to in-memory if unset.
REDIS_URL = os.getenv("REDIS_URL", "")

# Observability
SEELENRUH_ENV = os.getenv("SEELENRUH_ENV", "dev").lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SENTRY_DSN = os.getenv("SENTRY_DSN", "")

# CORS: in dev, only allow these ports (comma-separated). Ignored when CLIENT_ORIGIN is set.
DEV_ALLOWED_PORTS = os.getenv("DEV_ALLOWED_PORTS", "5173,5000,3000")

# Refuse to boot with the dev placeholder when SEELENRUH_ENV=prod.
if SEELENRUH_ENV == "prod" and JWT_SECRET == _DEV_JWT_SECRET:
    raise RuntimeError(
        "Refusing to start in prod mode with the placeholder JWT_SECRET. "
        "Set JWT_SECRET to a 32+ byte random string in the environment."
    )
