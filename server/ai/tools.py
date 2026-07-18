"""Web search tools — Brave → Tavily → DuckDuckGo → Wikipedia fallback chain."""
import asyncio

import httpx

from config import BRAVE_SEARCH_KEY, TAVILY_API_KEY, SERPAPI_KEY
from logger import get_logger

log = get_logger("tools")

SEARCH_TIMEOUT = 5.0   # hard cap per source
MIN_RESULTS_BEFORE_FALLBACK = 2  # if DDG returns fewer than this, also try Wikipedia
_MAX_RETRIES = 2  # retry each search source up to 2 times on transient failure

# ---------------------------------------------------------------------------
# Trusted domain scoring — Indian government / authoritative sources first
# ---------------------------------------------------------------------------
# Format: (domain_substring, trust_score 0.0–1.0)
# Higher score = surfaced earlier when results are re-ranked.
_TRUSTED_DOMAINS: list[tuple[str, float]] = [
    # Primary legislation / judiciary / apex bodies
    ("legislative.gov.in",      1.00),
    ("indiacode.nic.in",        1.00),
    ("supremecourt.gov.in",     1.00),
    ("ecourts.gov.in",          0.95),
    ("nalsa.gov.in",            0.95),
    ("egazette.gov.in",         0.95),
    ("gazette.india.gov.in",    0.95),
    # National portals and ministry homepages
    ("india.gov.in",            0.92),
    ("pib.gov.in",              0.90),
    ("mhfw.gov.in",             0.90),
    ("mohfw.gov.in",            0.90),
    ("wcd.nic.in",              0.90),
    ("labour.gov.in",           0.90),
    ("niti.gov.in",             0.88),
    # Specific scheme / service portals
    ("pmjay.gov.in",            0.88),
    ("pmkisan.gov.in",          0.88),
    ("scholarships.gov.in",     0.88),
    ("cybercrime.gov.in",       0.88),
    ("rtionline.gov.in",        0.88),
    ("consumerhelpline.gov.in", 0.88),
    ("nrega.nic.in",            0.88),
    ("pmaymis.gov.in",          0.88),
    ("myscheme.gov.in",         0.88),
    ("eshram.gov.in",           0.88),
    ("shebox.wcd.gov.in",       0.88),
    ("ncw.nic.in",              0.88),
    ("nhrc.nic.in",             0.88),
    # Generic .gov.in / .nic.in catch-all (must be after specifics)
    (".gov.in",                 0.82),
    (".nic.in",                 0.80),
    # RBI, SEBI, statutory regulators
    ("rbi.org.in",              0.85),
    ("sebi.gov.in",             0.85),
    ("trai.gov.in",             0.83),
    ("cci.gov.in",              0.83),
    # Mental health / safety helplines
    ("nimhans.ac.in",           0.75),
    ("icallhelpline.org",       0.72),
    ("telemanas.mohfw.gov.in",  0.75),
    # Wikipedia (useful for definitions, not primary)
    ("wikipedia.org",           0.40),
]


def _domain_trust_score(url: str) -> float:
    """Return a trust score 0.0–1.0 for a web result URL.

    Official Indian government domains score highest.
    Unknown / no URL → 0.3 (below all known sources).
    """
    if not url:
        return 0.3
    url_lower = url.lower()
    for domain, score in _TRUSTED_DOMAINS:
        if domain in url_lower:
            return score
    return 0.35   # generic unrecognised source


def _sort_by_trust(results: list[dict]) -> list[dict]:
    """Stable-sort results so trusted government sources surface first."""
    return sorted(results, key=lambda r: _domain_trust_score(r.get("url", "")), reverse=True)


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


async def _tavily_search(query: str, max_results: int) -> list[dict]:
    """Tavily AI search — second in priority after Brave. Free tier: 1000 queries/month."""
    if not TAVILY_API_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            r = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                    "include_answer": True,
                },
            )
        data = r.json()
    except Exception as err:
        log.warning("Tavily search failed", error=str(err))
        return []

    results: list[dict] = []
    if data.get("answer"):
        results.append({"text": data["answer"], "title": "AI Answer", "url": ""})
    for item in data.get("results", [])[:max_results]:
        content = item.get("content") or item.get("snippet") or ""
        if content:
            results.append({
                "text": content[:500],
                "title": item.get("title", ""),
                "url": item.get("url", ""),
            })
    return results[:max_results]


async def _serpapi_search(query: str, max_results: int) -> list[dict]:
    """SerpAPI Google Search — optional tertiary fallback."""
    if not SERPAPI_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            r = await client.get(
                "https://serpapi.com/search",
                params={
                    "q": query, "api_key": SERPAPI_KEY,
                    "num": max_results, "hl": "en", "gl": "in",
                },
            )
        data = r.json()
    except Exception as err:
        log.warning("SerpAPI search failed", error=str(err))
        return []

    results: list[dict] = []
    for item in data.get("organic_results", [])[:max_results]:
        snippet = item.get("snippet") or ""
        if snippet:
            results.append({
                "text": snippet[:500],
                "title": item.get("title", ""),
                "url": item.get("link", ""),
            })
    return results


def _merge_unique(base: list[dict], additions: list[dict], seen: set[str]) -> None:
    """Merge *additions* into *base*, skipping duplicates by text prefix."""
    for r in additions:
        key = r["text"][:80]
        if key not in seen:
            base.append(r)
            seen.add(key)


async def web_search(query: str, max_results: int = 4) -> list[dict]:
    """Cascading search: Brave → Tavily → DuckDuckGo → SerpAPI → Wikipedia.

    Each source is tried only when the previous yields fewer than
    MIN_RESULTS_BEFORE_FALLBACK results. Results are re-ranked by domain
    trust so Indian government sources surface first.
    """
    combined: list[dict] = []
    seen: set[str] = set()
    source_chain = "?"

    # 1. Brave (best quality, requires API key)
    brave_results = await _with_retry(_brave_search, query, max_results)
    _merge_unique(combined, brave_results, seen)
    if len(combined) >= MIN_RESULTS_BEFORE_FALLBACK:
        source_chain = "Brave"
    else:
        # 2. Tavily (no key needed on free tier, AI-enhanced)
        tavily_results = await _with_retry(_tavily_search, query, max_results)
        _merge_unique(combined, tavily_results, seen)
        if len(combined) >= MIN_RESULTS_BEFORE_FALLBACK:
            source_chain = "Brave+Tavily"
        else:
            # 3. DuckDuckGo (free, no key)
            ddg_results = await _with_retry(_ddg_search, query, max_results)
            _merge_unique(combined, ddg_results, seen)
            if len(combined) >= MIN_RESULTS_BEFORE_FALLBACK:
                source_chain = "Brave+Tavily+DDG"
            else:
                # 4. SerpAPI (optional)
                serp_results = await _with_retry(_serpapi_search, query, max_results)
                _merge_unique(combined, serp_results, seen)
                # 5. Wikipedia (always free, last resort)
                wiki_results = await _with_retry(_wikipedia_search, query, max_results)
                _merge_unique(combined, wiki_results, seen)
                source_chain = "all-sources"

    sorted_results = _sort_by_trust(combined)[:max_results]
    if sorted_results:
        log.info("web_search complete", results=len(sorted_results), source=source_chain)
    return sorted_results
