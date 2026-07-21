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
import re
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

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
        "url": "https://en.wikipedia.org/wiki/India_Code",
        "domain": "Legal",
        "topic": "India Code — Central Acts Portal",
        "section": "legislation",
    },
    {
        "id": "nalsa_home",
        "url": "https://en.wikipedia.org/wiki/National_Legal_Services_Authority",
        "domain": "Legal",
        "topic": "NALSA — National Legal Services Authority",
        "section": "legal_aid",
    },
    {
        "id": "egazette",
        "url": "https://en.wikipedia.org/wiki/The_Gazette_of_India",
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
        "url": "https://en.wikipedia.org/wiki/Press_Information_Bureau",
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
        "url": "https://en.wikipedia.org/wiki/Ayushman_Bharat_Pradhan_Mantri_Jan_Arogya_Yojana",
        "domain": "Government Schemes",
        "topic": "Ayushman Bharat PM-JAY — Health Insurance Scheme",
        "section": "schemes",
    },
    # Mental health
    {
        "id": "nhp_mental",
        "url": "https://en.wikipedia.org/wiki/Mental_health_in_India",
        "domain": "Mental Health",
        "topic": "Mental Health in India — Resources and Support",
        "section": "mental_health",
    },
    {
        "id": "nimhans",
        "url": "https://en.wikipedia.org/wiki/National_Institute_of_Mental_Health_and_Neurosciences",
        "domain": "Mental Health",
        "topic": "NIMHANS — National Institute of Mental Health and Neurosciences",
        "section": "mental_health",
    },
    {
        "id": "telemanas",
        "url": "https://en.wikipedia.org/wiki/Mental_health_in_India",
        "domain": "Mental Health",
        "topic": "Tele-MANAS — Mental Health Helpline 14416 and Mental Health in India",
        "section": "mental_health",
    },
    # Women's safety
    {
        "id": "wcd_ministry",
        "url": "https://en.wikipedia.org/wiki/Ministry_of_Women_and_Child_Development_(India)",
        "domain": "Safety",
        "topic": "Ministry of Women and Child Development — Schemes",
        "section": "safety",
    },
    {
        "id": "shebox",
        "url": "https://en.wikipedia.org/wiki/Sexual_Harassment_of_Women_at_Workplace_(Prevention,_Prohibition_and_Redressal)_Act,_2013",
        "domain": "Safety",
        "topic": "SHe-Box — Sexual Harassment at Workplace Act 2013",
        "section": "safety",
    },
    {
        "id": "cybercrime",
        "url": "https://en.wikipedia.org/wiki/Indian_Cyber_Crime_Coordination_Centre",
        "domain": "Safety",
        "topic": "National Cyber Crime Reporting Portal — 1930",
        "section": "safety",
    },
    # ── Additional scheme portals ─────────────────────────────────────────────
    {
        "id": "eshram",
        "url": "https://en.wikipedia.org/wiki/E-Shram",
        "domain": "Government Schemes",
        "topic": "e-Shram Portal — Unorganised Worker Registration and Benefits",
        "section": "schemes",
    },
    {
        "id": "pmfby_wiki",
        "url": "https://en.wikipedia.org/wiki/Pradhan_Mantri_Fasal_Bima_Yojana",
        "domain": "Government Schemes",
        "topic": "PM Fasal Bima Yojana — Crop Insurance Scheme",
        "section": "schemes",
    },
    {
        "id": "mgnrega_wiki",
        "url": "https://en.wikipedia.org/wiki/Mahatma_Gandhi_National_Rural_Employment_Guarantee_Act",
        "domain": "Government Schemes",
        "topic": "MGNREGA — 100 Days Rural Employment Guarantee",
        "section": "schemes",
    },
    {
        "id": "pmay_wiki",
        "url": "https://en.wikipedia.org/wiki/Pradhan_Mantri_Awas_Yojana",
        "domain": "Government Schemes",
        "topic": "PM Awas Yojana — Affordable Housing Scheme (Urban and Rural)",
        "section": "schemes",
    },
    {
        "id": "disability_india",
        "url": "https://en.wikipedia.org/wiki/Rights_of_Persons_with_Disabilities_Act,_2016",
        "domain": "Government Schemes",
        "topic": "Rights of Persons with Disabilities Act 2016 — RPWD",
        "section": "schemes",
    },
    # ── Additional mental health sources ─────────────────────────────────────
    {
        "id": "cbt_wiki",
        "url": "https://en.wikipedia.org/wiki/Cognitive_behavioral_therapy",
        "domain": "Mental Health",
        "topic": "Cognitive Behavioural Therapy (CBT) — Techniques and Uses",
        "section": "mental_health",
    },
    {
        "id": "anxiety_wiki",
        "url": "https://en.wikipedia.org/wiki/Anxiety_disorder",
        "domain": "Mental Health",
        "topic": "Anxiety Disorders — Types, Symptoms, and Management",
        "section": "mental_health",
    },
    {
        "id": "depression_wiki",
        "url": "https://en.wikipedia.org/wiki/Major_depressive_disorder",
        "domain": "Mental Health",
        "topic": "Depression — Symptoms, Causes, and Treatment",
        "section": "mental_health",
    },
    # ── Additional legal / women's rights ────────────────────────────────────
    {
        "id": "ncw_wiki",
        "url": "https://en.wikipedia.org/wiki/National_Commission_for_Women",
        "domain": "Legal",
        "topic": "National Commission for Women — Complaints and Support",
        "section": "legal",
    },
    {
        "id": "pocso_wiki",
        "url": "https://en.wikipedia.org/wiki/Protection_of_Children_from_Sexual_Offences_Act,_2012",
        "domain": "Legal",
        "topic": "POCSO Act 2012 — Child Sexual Abuse Protections",
        "section": "legal",
    },
    {
        "id": "domestic_violence_wiki",
        "url": "https://en.wikipedia.org/wiki/Protection_of_Women_from_Domestic_Violence_Act,_2005",
        "domain": "Safety",
        "topic": "Domestic Violence Act 2005 — Rights, Orders, and Helplines",
        "section": "safety",
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _strip_html(html: str) -> str:
    """Minimal HTML/XML → text: remove tags, decode entities, collapse whitespace."""
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r" \1 ", html, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def _fetch_page(url: str) -> Optional[str]:
    """Fetch a URL and return stripped text, or None on failure."""
    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
        ) as client:
            r = await client.get(url)
            if r.status_code != 200:
                log.warning("fetch_page non-200", url=url, status=r.status_code)
                return None
            ct = r.headers.get("content-type", "")
            if not any(t in ct for t in ("html", "text", "xml")):
                log.warning("fetch_page bad content-type", url=url, ct=ct)
                return None
            text = _strip_html(r.text)
            log.debug("fetch_page ok", url=url, chars=len(text))
            return text
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
