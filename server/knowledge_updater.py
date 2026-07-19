"""Dynamic Knowledge Base Updater.

Runs a background scheduler that periodically crawls authoritative Indian
government and health sources, detects changed content via checksum, and
re-ingests only changed documents into the live FAISS index.

Sources checked:
  - India Code (legislation)           https://www.indiacode.nic.in
  - eGazette India                     https://egazette.gov.in
  - PIB (Press Information Bureau)     https://pib.gov.in
  - MyGov                              https://www.mygov.in
  - National Health Portal             https://www.nhp.gov.in
  - NALSA                              https://nalsa.gov.in
  - MyScheme Portal                    https://www.myscheme.gov.in

Architecture:
  - Source registry stored in MongoDB `knowledge_sources` collection.
  - Each source has: url, last_checked, last_updated, checksum, version, status.
  - On change: download → extract text → chunk → re-embed → upsert into FAISS.
  - On failure: log error, keep previous knowledge, notify admin via log.
  - Scheduler runs every 24 hours by default (configurable via UPDATE_INTERVAL_HOURS).
  - Never duplicates chunks: upserts by source URL as the dedup key.

Startup:
  Call start_scheduler() from main.py lifespan. It's non-blocking.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from config import ADMIN_KEY
from logger import get_logger
import db

log = get_logger("knowledge_updater")

# How often to check each source (in seconds). Default: every 24 hours.
_UPDATE_INTERVAL_S = int(__import__("os").getenv("KNOWLEDGE_UPDATE_INTERVAL_HOURS", "24")) * 3600

# Max text to extract per page (keep it lean for embedding quality)
_MAX_PAGE_CHARS = 4_000

# Minimum content length to bother ingesting (skip empty/error pages)
_MIN_CONTENT_CHARS = 100

# HTTP timeout for source fetching
_FETCH_TIMEOUT = 15.0

# ── Source Registry ───────────────────────────────────────────────────────────
# Each entry: (source_id, url, domain, topic_hint)
# topic_hint is used as the chunk topic when no better title is found.
_SOURCES: list[dict] = [
    # Legislation / Judiciary
    {
        "id": "indiacode_home",
        "url": "https://www.indiacode.nic.in/",
        "domain": "Legal",
        "topic": "India Code — Central Acts Portal",
        "section": "legislation",
    },
    {
        "id": "nalsa_home",
        "url": "https://nalsa.gov.in/",
        "domain": "Legal",
        "topic": "NALSA — National Legal Services Authority",
        "section": "legal_aid",
    },
    {
        "id": "egazette",
        "url": "https://egazette.gov.in/",
        "domain": "Legal",
        "topic": "eGazette India — Official Gazette Notifications",
        "section": "gazette",
    },
    # Government schemes / welfare
    {
        "id": "myscheme_portal",
        "url": "https://www.myscheme.gov.in/",
        "domain": "Government Schemes",
        "topic": "MyScheme Portal — Central & State Government Schemes",
        "section": "schemes",
    },
    {
        "id": "pib_home",
        "url": "https://pib.gov.in/",
        "domain": "Government Schemes",
        "topic": "PIB — Press Information Bureau India",
        "section": "news",
    },
    {
        "id": "mygov_home",
        "url": "https://www.mygov.in/",
        "domain": "Government Schemes",
        "topic": "MyGov — Government of India Citizen Platform",
        "section": "schemes",
    },
    {
        "id": "pmkisan",
        "url": "https://pmkisan.gov.in/",
        "domain": "Government Schemes",
        "topic": "PM-KISAN — Pradhan Mantri Kisan Samman Nidhi",
        "section": "schemes",
    },
    {
        "id": "pmjay",
        "url": "https://pmjay.gov.in/",
        "domain": "Government Schemes",
        "topic": "Ayushman Bharat PM-JAY — Health Insurance Scheme",
        "section": "schemes",
    },
    # Mental health
    {
        "id": "nhp_mental",
        "url": "https://www.nhp.gov.in/disease/mental-health",
        "domain": "Mental Health",
        "topic": "National Health Portal — Mental Health Resources",
        "section": "mental_health",
    },
    {
        "id": "nimhans",
        "url": "https://nimhans.ac.in/",
        "domain": "Mental Health",
        "topic": "NIMHANS — National Institute of Mental Health and Neurosciences",
        "section": "mental_health",
    },
    {
        "id": "telemanas",
        "url": "https://telemanas.mohfw.gov.in/",
        "domain": "Mental Health",
        "topic": "Tele-MANAS — Mental Health Helpline 14416",
        "section": "mental_health",
    },
    # Women's safety
    {
        "id": "wcd_ministry",
        "url": "https://wcd.nic.in/",
        "domain": "Safety",
        "topic": "Ministry of Women and Child Development",
        "section": "safety",
    },
    {
        "id": "shebox",
        "url": "https://shebox.wcd.gov.in/",
        "domain": "Safety",
        "topic": "SHe-Box — Sexual Harassment Online Complaint Portal",
        "section": "safety",
    },
    {
        "id": "cybercrime",
        "url": "https://cybercrime.gov.in/",
        "domain": "Safety",
        "topic": "National Cyber Crime Reporting Portal — 1930",
        "section": "safety",
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _strip_html(html: str) -> str:
    """Minimal HTML → text: remove tags, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def _fetch_page(url: str) -> Optional[str]:
    """Fetch a URL and return stripped text, or None on failure."""
    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "SeelenruhKnowledgeBot/1.0 (educational project; contact: admin@seelenruh.app)"},
        ) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return None
            # Only process HTML pages — skip PDFs, images, etc.
            ct = r.headers.get("content-type", "")
            if "html" not in ct and "text" not in ct:
                return None
            return _strip_html(r.text)
    except Exception as err:
        log.warning("fetch_page failed", url=url, error=str(err))
        return None


def _chunk_text(text: str, source: dict, max_chars: int = _MAX_PAGE_CHARS) -> list[dict]:
    """Split *text* into chunks suitable for FAISS ingestion."""
    text = text[:max_chars]
    # Split on paragraphs / double newlines
    paragraphs = [p.strip() for p in re.split(r"\n{2,}|\.\s{2,}", text) if len(p.strip()) > 60]

    chunks: list[dict] = []
    for i, para in enumerate(paragraphs[:5]):   # max 5 chunks per page
        chunk_id = f"crawl_{source['id']}_{i}"
        chunks.append({
            "id": chunk_id,
            "domain": source["domain"],
            "topic": source["topic"],
            "text": para[:1500],
            "source": source["url"],
            "sourceAuthority": "Official",
            "reviewStatus": "Verified",
            "crawled": True,
            "crawledAt": datetime.now(timezone.utc).isoformat(),
        })
    return chunks


async def _get_source_record(source_id: str) -> Optional[dict]:
    if not db.is_connected():
        return None
    try:
        return await db._db["knowledge_sources"].find_one({"sourceId": source_id})
    except Exception:
        return None


async def _upsert_source_record(source_id: str, **fields) -> None:
    if not db.is_connected():
        return
    try:
        await db._db["knowledge_sources"].update_one(
            {"sourceId": source_id},
            {"$set": {"sourceId": source_id, **fields}},
            upsert=True,
        )
    except Exception as err:
        log.warning("upsert_source_record failed", source_id=source_id, error=str(err))


async def _check_and_update_source(source: dict) -> bool:
    """Check one source URL. If content changed, re-ingest into FAISS.

    Returns True if an update was ingested.
    """
    source_id = source["id"]
    url = source["url"]

    # Record that we checked this source
    await _upsert_source_record(source_id, lastChecked=datetime.now(timezone.utc), url=url, status="checking")

    text = await _fetch_page(url)
    if not text or len(text) < _MIN_CONTENT_CHARS:
        # JS-rendered sites return empty HTML — store a reference stub so the
        # source is still findable in RAG even without live content.
        log.warning("knowledge_updater: empty/short page (JS-rendered?)", source_id=source_id, url=url)
        stub_text = (
            f"{source['topic']}. "
            f"Official resource available at {url}. "
            f"Domain: {source['domain']}."
        )
        stub_chunks = [{
            "id": f"crawl_{source_id}_stub",
            "domain": source["domain"],
            "topic": source["topic"],
            "text": stub_text,
            "source": url,
            "sourceAuthority": "Official",
            "reviewStatus": "Verified",
            "crawled": True,
            "crawledAt": datetime.now(timezone.utc).isoformat(),
        }]
        try:
            from rag import retriever as _retriever
            await _retriever.ingest(stub_chunks)
        except Exception:
            pass
        await _upsert_source_record(
            source_id,
            status="partial",
            lastError="js_rendered_stub_only",
            lastErrorAt=datetime.now(timezone.utc),
            lastUpdated=datetime.now(timezone.utc),
        )
        return False

    new_checksum = _checksum(text)
    record = await _get_source_record(source_id)
    if record and record.get("checksum") == new_checksum:
        log.debug("knowledge_updater: no change", source_id=source_id)
        await _upsert_source_record(source_id, status="ok")
        return False

    # Content changed — re-ingest
    log.info("knowledge_updater: change detected", source_id=source_id, url=url)
    chunks = _chunk_text(text, source)
    if not chunks:
        await _upsert_source_record(source_id, status="ok")
        return False

    try:
        from rag import retriever as _retriever
        added = await _retriever.ingest(chunks)
        version = (record.get("version", 0) + 1) if record else 1
        await _upsert_source_record(
            source_id,
            status="ok",
            checksum=new_checksum,
            lastUpdated=datetime.now(timezone.utc),
            version=version,
            chunksIngested=added,
            lastError=None,
        )
        log.info("knowledge_updater: ingested", source_id=source_id, chunks=added, version=version)
        return True
    except Exception as err:
        log.error("knowledge_updater: ingest failed", source_id=source_id, error=str(err))
        await _upsert_source_record(
            source_id,
            status="error",
            lastError=str(err),
            lastErrorAt=datetime.now(timezone.utc),
        )
        return False


async def run_update_cycle() -> dict:
    """Check all sources and ingest any changes. Returns a summary dict."""
    t0 = time.time()
    checked = 0
    updated = 0
    errors = 0

    for source in _SOURCES:
        try:
            changed = await _check_and_update_source(source)
            checked += 1
            if changed:
                updated += 1
            # Polite delay between requests — don't hammer government servers
            await asyncio.sleep(2.0)
        except Exception as err:
            errors += 1
            log.error("knowledge_updater: source error", source_id=source["id"], error=str(err))

    elapsed = round(time.time() - t0, 1)
    summary = {"checked": checked, "updated": updated, "errors": errors, "elapsed_s": elapsed}
    log.info("knowledge_updater: cycle complete", **summary)
    return summary


async def _scheduler_loop() -> None:
    """Infinite loop: wait for RAG to be ready, then run update cycles."""
    # Wait for RAG index to finish building before the first crawl
    from rag import retriever as _retriever
    for _ in range(60):  # wait up to 5 minutes
        if _retriever.is_ready():
            break
        await asyncio.sleep(5)

    while True:
        try:
            await run_update_cycle()
        except Exception as err:
            log.error("knowledge_updater: scheduler cycle error", error=str(err))
        await asyncio.sleep(_UPDATE_INTERVAL_S)


_scheduler_task: Optional[asyncio.Task] = None


def start_scheduler() -> None:
    """Start the background update scheduler. Safe to call multiple times."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    log.info("knowledge_updater: scheduler started", interval_h=_UPDATE_INTERVAL_S // 3600)
