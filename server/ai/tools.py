"""Web search tools — DuckDuckGo, Wikipedia, Brave Search (optional)."""
import asyncio

import httpx

from config import BRAVE_SEARCH_KEY
from logger import get_logger

log = get_logger("tools")

SEARCH_TIMEOUT = 5.0   # hard cap per source
MIN_RESULTS_BEFORE_FALLBACK = 2  # if DDG returns fewer than this, also try Wikipedia
_MAX_RETRIES = 2  # retry each search source up to 2 times on transient failure


async def _with_retry(coro_fn, *args, **kwargs) -> list[dict]:
    for attempt in range(_MAX_RETRIES):
        try:
            result = await coro_fn(*args, **kwargs)
            if result:
                return result
        except Exception as err:
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
            else:
                log.warning("search retry exhausted", fn=coro_fn.__name__, error=str(err))
    return []

# Keywords that hint the user wants real-time / current information.
REALTIME_SIGNALS = {
    "latest", "current", "recent", "today", "now", "2024", "2025", "2026",
    "updated", "news", "new scheme", "just announced", "this year",
    "helpline", "toll free", "number", "contact",
    # Hindi / Hinglish equivalents
    "abhi", "naya", "nayi", "iss saal", "aaj",
    # Tamil / Telugu / Marathi signals (romanised)
    "ippo", "ippothu", "ippatiki", "aata",
}


def needs_web_search(query: str, n_hits: int, top_score: float, domain: str = "") -> bool:
    q = query.lower()
    has_signal = any(sig in q for sig in REALTIME_SIGNALS)

    # Legal and Schemes go stale faster — use a tighter RAG quality bar
    if domain in ("Legal", "Government Schemes"):
        weak_rag = n_hits < 2 or top_score < 0.65
    else:
        weak_rag = n_hits < 2 or top_score < 0.5

    return has_signal or weak_rag


async def _ddg_search(query: str, max_results: int) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            r = await client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query, "format": "json",
                    "no_html": "1", "skip_disambig": "1", "t": "seelenruh",
                },
                headers={"User-Agent": "SeelenruhBot/1.0 (educational project)"},
                follow_redirects=True,
            )
        data = r.json()
    except Exception as err:
        log.warning("DDG search failed", error=str(err))
        return []

    results: list[dict] = []
    if data.get("Answer"):
        results.append({"text": data["Answer"], "title": "Quick answer", "url": ""})
    if data.get("AbstractText"):
        results.append({
            "text": data["AbstractText"],
            "title": data.get("Heading", ""),
            "url": data.get("AbstractURL", ""),
        })
    for topic in data.get("RelatedTopics", []):
        if not isinstance(topic, dict):
            continue
        text = topic.get("Text", "")
        if text:
            results.append({"text": text, "title": "", "url": topic.get("FirstURL", "")})
        if len(results) >= max_results:
            break
    return results[:max_results]


async def _wikipedia_search(query: str, max_results: int) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            r = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "opensearch", "search": query,
                    "limit": max_results, "format": "json", "redirects": "resolve",
                },
                headers={"User-Agent": "SeelenruhBot/1.0 (educational project)"},
            )
            search_data = r.json()
            titles: list[str] = search_data[1] if len(search_data) > 1 else []
            urls: list[str] = search_data[3] if len(search_data) > 3 else []
            if not titles:
                return []

            r2 = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query", "titles": "|".join(titles[:max_results]),
                    "prop": "extracts", "exintro": "1", "explaintext": "1",
                    "exsentences": "3", "format": "json", "redirects": "resolve",
                },
                headers={"User-Agent": "SeelenruhBot/1.0 (educational project)"},
            )
            pages = r2.json().get("query", {}).get("pages", {})

        results: list[dict] = []
        for (title, url) in zip(titles, urls):
            for page in pages.values():
                if page.get("title", "").lower() == title.lower():
                    extract = (page.get("extract") or "").strip()
                    if extract:
                        results.append({"text": extract[:500], "title": title, "url": url})
                    break
        return results[:max_results]
    except Exception as err:
        log.warning("Wikipedia search failed", error=str(err))
        return []


async def _brave_search(query: str, max_results: int) -> list[dict]:
    """Only called when BRAVE_SEARCH_KEY is set."""
    if not BRAVE_SEARCH_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            r = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": max_results, "safesearch": "moderate"},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": BRAVE_SEARCH_KEY,
                },
            )
        data = r.json()
    except Exception as err:
        log.warning("Brave search failed", error=str(err))
        return []

    results: list[dict] = []
    for item in data.get("web", {}).get("results", [])[:max_results]:
        desc = item.get("description") or item.get("extra_snippets", [""])[0] or ""
        if desc:
            results.append({
                "text": desc[:500],
                "title": item.get("title", ""),
                "url": item.get("url", ""),
            })
    return results


async def web_search(query: str, max_results: int = 4) -> list[dict]:
    """Run Brave + DDG + Wikipedia concurrently, return best combined results."""
    brave_task = asyncio.create_task(_with_retry(_brave_search, query, max_results))
    ddg_task = asyncio.create_task(_with_retry(_ddg_search, query, max_results))
    wiki_task = asyncio.create_task(_with_retry(_wikipedia_search, query, max_results))

    brave_results = await brave_task
    if len(brave_results) >= MIN_RESULTS_BEFORE_FALLBACK:
        ddg_task.cancel()
        wiki_task.cancel()
        log.info("web_search complete", results=len(brave_results), source="Brave")
        return brave_results

    ddg_results = await ddg_task
    combined = brave_results[:]
    seen: set[str] = {r["text"][:80] for r in combined}
    for r in ddg_results:
        if r["text"][:80] not in seen:
            combined.append(r)
            seen.add(r["text"][:80])

    if len(combined) >= MIN_RESULTS_BEFORE_FALLBACK:
        wiki_task.cancel()
        if combined:
            log.info("web_search complete", results=len(combined), source="Brave+DDG")
        return combined[:max_results]

    try:
        wiki_results = await wiki_task
    except asyncio.CancelledError:
        wiki_results = []

    for r in wiki_results:
        if r["text"][:80] not in seen:
            combined.append(r)
            seen.add(r["text"][:80])

    if combined:
        log.info("web_search complete", results=len(combined), source="Brave+DDG+Wikipedia")
    return combined[:max_results]
