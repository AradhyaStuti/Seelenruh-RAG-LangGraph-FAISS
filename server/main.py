"""FastAPI entry point. uvicorn main:app --reload --port 5000"""
import asyncio
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from fastapi import Header as _Header
from config import PORT, CLIENT_ORIGIN, DEV_ALLOWED_PORTS, ADMIN_KEY
from logger import get_logger
from schemas import HealthResponse
from rate_limit import limiter
from routes.chat import router as chat_router
from routes.auth import router as auth_router
from routes.schemes import router as schemes_router
from routes.templates import router as templates_router
from routes.summary import router as summary_router
from routes.tts import router as tts_router
from routes.admin import router as admin_router
from routes.upload import router as upload_router
from routes.feedback import router as feedback_router
import db
from rag import retriever

log = get_logger("main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from config import REDIS_URL, SEELENRUH_ENV
    if not REDIS_URL:
        log.warning(
            "REDIS_URL not set — rate-limit counters are in-memory and will reset on restart. "
            "Set REDIS_URL in .env for persistent rate limiting across restarts."
        )
    if SEELENRUH_ENV == "prod":
        log.warning(
            "Running in production mode. Ensure MongoDB Atlas encryption-at-rest is enabled "
            "in your Atlas cluster settings to protect sensitive user data."
        )

    # Run DB connect + RAG warmup as background tasks so the lifespan
    # completes immediately and uvicorn starts accepting requests right away.
    # HF Spaces health-check fires within seconds of port open — if we block
    # here (db.connect takes ~6s) the check times out and HF marks us "down".
    async def _bootstrap():
        await db.connect()
        log.info("database connected")
        await retriever.init()
        await retriever.warmup()
        log.info("RAG index ready", chunks=retriever._store.size())

    asyncio.create_task(_bootstrap())
    yield
    log.info("server shutting down")


app = FastAPI(title="Seelenruh API", version="4.0.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def _global_500_handler(request: Request, exc: Exception):
    log.error("unhandled exception", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end. Please try again in a moment."},
    )

if CLIENT_ORIGIN:
    origins = [CLIENT_ORIGIN]
    allow_origin_regex = None
else:
    origins = []
    # Allow only the explicitly listed dev ports — never a wildcard \d+
    _ports = "|".join(re.escape(p.strip()) for p in DEV_ALLOWED_PORTS.split(",") if p.strip())
    allow_origin_regex = rf"^http://(localhost|127\.0\.0\.1):({_ports})$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    from ai.circuit_breaker import groq_breaker, ollama_breaker, anthropic_breaker
    return HealthResponse(
        ok=True,
        ts=int(time.time() * 1000),
        ragReady=retriever.is_ready(),
        dbConnected=db.is_connected(),
        providers={b.name: b.status() for b in [groq_breaker, ollama_breaker, anthropic_breaker]},
    )


@app.get("/api/metrics")
async def metrics(x_admin_key: str = _Header(default="")) -> dict:
    if not ADMIN_KEY or x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key.")
    from ai.circuit_breaker import groq_breaker, ollama_breaker, anthropic_breaker
    return {
        "uptime_s": int(time.time() - _start_time),
        "rag": {
            "ready": retriever.is_ready(),
            "chunks": retriever._store.size() if retriever.is_ready() else 0,
            "deleted": len(retriever._store._deleted_ids) if retriever.is_ready() else 0,
        },
        "db": {"connected": db.is_connected()},
        "providers": {
            b.name: b.status()
            for b in [groq_breaker, ollama_breaker, anthropic_breaker]
        },
    }


_start_time = time.time()


app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(schemes_router)
app.include_router(templates_router)
app.include_router(summary_router)
app.include_router(tts_router)
app.include_router(admin_router)
app.include_router(upload_router)
app.include_router(feedback_router)


_CLIENT_DIST = (Path(__file__).parent.parent / "client" / "dist").resolve()
if _CLIENT_DIST.is_dir():
    _ASSETS = _CLIENT_DIST / "assets"
    if _ASSETS.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_ASSETS)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # serve the file if it exists, otherwise fall back to index.html for SPA routing
        if full_path:
            try:
                candidate = (_CLIENT_DIST / full_path).resolve()
            except (OSError, ValueError):
                candidate = _CLIENT_DIST / "index.html"
            if (
                candidate.is_file()
                and _CLIENT_DIST in candidate.parents
            ):
                return FileResponse(candidate)
        # no-cache so the browser always fetches fresh hashed JS/CSS bundle references
        return FileResponse(
            _CLIENT_DIST / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
