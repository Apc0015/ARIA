"""Web search collector using DuckDuckGo (with SerpAPI fallback).

After collecting stubs from DuckDuckGo, each result is enriched with
full-page content via Jina AI Reader (primary) then WebScraperCollector
(fallback).  Jina bypasses most anti-scraping measures and returns clean
Markdown without requiring credentials.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any, Optional

import aiohttp

from .base import BaseCollector

logger = logging.getLogger("aria")

_JINA_TIMEOUT = 20   # seconds per page
_SCRAPE_TIMEOUT = 30  # WebScraperCollector timeout
_MAX_CONCURRENT = 3   # parallel scrape workers


class WebSearchCollector(BaseCollector):
    """Collect documents via web search + full-page scraping.

    Flow per query:
      1. DuckDuckGo (or SerpAPI) → list of URL stubs (title + snippet)
      2. For each stub, try Jina AI Reader → full Markdown page
      3. If Jina fails, try WebScraperCollector (aiohttp + BS4)
      4. If both fail, keep the snippet with a WARNING log
    """

    def __init__(
        self,
        max_results: int = 10,
        region: str = "wt-wt",
        safesearch: str = "off",
        timeout: int = 20,
    ) -> None:
        self._max_results = max_results
        self._region = region
        self._safesearch = safesearch
        self._timeout = timeout
        self._serpapi_key: Optional[str] = os.getenv("SERPAPI_KEY")

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen_urls: set[str] = set()
        for query in queries:
            try:
                async for doc in self._search_query(query, seen_urls):
                    yield doc
                await asyncio.sleep(0.5)
            except Exception as exc:
                logger.warning("WebSearchCollector: error for query '%s': %s", query, exc)

    async def _search_query(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        if self._serpapi_key:
            async for doc in self._serpapi_search(query, seen_urls):
                yield doc
        else:
            async for doc in self._ddgs_search(query, seen_urls):
                yield doc

    async def _ddgs_search(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """DDGS → stubs → parallel full-page scrape."""
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: list(
                    DDGS().text(
                        query,
                        max_results=self._max_results,
                        region=self._region,
                        safesearch=self._safesearch,
                    )
                ),
            )
        except Exception as exc:
            logger.warning("WebSearchCollector DDGS error for '%s': %s", query, exc)
            return

        stubs: list[dict] = []
        for item in results:
            url = item.get("href", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            text  = item.get("body", "")
            title = item.get("title", "")
            stubs.append(_make_doc(
                url=url, title=title, text=text,
                source_type="web_search", platform="duckduckgo",
                metadata={"query": query, "snippet": text},
            ))

        if not stubs:
            return

        # Enrich all stubs in parallel (capped at _MAX_CONCURRENT)
        sem = asyncio.Semaphore(_MAX_CONCURRENT)
        enriched = await asyncio.gather(*[_scrape(stub, sem) for stub in stubs])
        for doc in enriched:
            yield doc

    async def _serpapi_search(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            import httpx
            params = {
                "q": query,
                "api_key": self._serpapi_key,
                "engine": "google",
                "num": self._max_results,
            }
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get("https://serpapi.com/search", params=params)
                if resp.status_code != 200:
                    return
                data = resp.json()
                stubs: list[dict] = []
                for item in data.get("organic_results", []):
                    url = item.get("link", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    stubs.append(_make_doc(
                        url=url,
                        title=item.get("title", ""),
                        text=item.get("snippet", ""),
                        source_type="web_search",
                        platform="serpapi",
                        metadata={"query": query, "position": item.get("position")},
                    ))
                sem = asyncio.Semaphore(_MAX_CONCURRENT)
                enriched = await asyncio.gather(*[_scrape(stub, sem) for stub in stubs])
                for doc in enriched:
                    yield doc
        except Exception as exc:
            logger.warning("WebSearchCollector SerpAPI error for '%s': %s", query, exc)


# ---------------------------------------------------------------------------
# Full-page scraping helpers (module-level so they can be tested directly)
# ---------------------------------------------------------------------------

async def _scrape(stub: dict, sem: asyncio.Semaphore) -> dict:
    """Enrich a stub dict with full-page text.

    Strategy:
      1. Jina AI Reader  — clean Markdown, no credentials, bypasses most blocks
      2. WebScraperCollector.scrape_url — aiohttp + BS4 + Camofox fallback
      3. Keep snippet — log WARNING so operators know scraping failed
    """
    url      = stub["url"]
    snip_len = len(stub.get("text", ""))

    async with sem:
        # ── 1. Jina ───────────────────────────────────────────────────────────
        try:
            jina_url = f"https://r.jina.ai/{url}"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    jina_url,
                    timeout=aiohttp.ClientTimeout(total=_JINA_TIMEOUT),
                    headers={"User-Agent": "ARIA-Research-Bot/5.0"},
                ) as resp:
                    if resp.status == 200:
                        text = (await resp.text()).strip()
                        if len(text) > snip_len:
                            stub["text"]        = text
                            stub["word_count"]  = len(text.split())
                            stub["source_type"] = "web_page"
                            logger.debug(
                                "WebSearch(Jina): OK %s (%d words)",
                                url[:60], stub["word_count"],
                            )
                            return stub
        except Exception as exc:
            logger.debug("WebSearch(Jina): failed %s — %s", url[:60], exc)

        # ── 2. WebScraperCollector ────────────────────────────────────────────
        try:
            from aria.engine.collectors.web.scraper import WebScraperCollector
            scraper = WebScraperCollector(timeout=_SCRAPE_TIMEOUT, max_concurrent=1)
            full = await scraper.scrape_url(url)
            if full and len(full.get("text", "")) > snip_len:
                stub["text"]        = full["text"]
                stub["word_count"]  = full.get("word_count", 0)
                stub["source_type"] = "web_page"
                logger.debug(
                    "WebSearch(scraper): OK %s (%d words)",
                    url[:60], stub["word_count"],
                )
                return stub
        except Exception as exc:
            logger.warning("WebSearch(scraper): error %s — %s", url[:60], exc)

        # ── 3. Snippet-only fallback ──────────────────────────────────────────
        logger.warning(
            "WebSearch: full-page scrape failed for %s "
            "(keeping %d-word snippet) — Jina and scraper both returned no content",
            url[:60], stub.get("word_count", 0),
        )
        return stub


def _make_doc(
    url: str,
    title: str,
    text: str,
    source_type: str,
    platform: str,
    metadata: Optional[dict] = None,
) -> dict:
    return {
        "url":          url,
        "title":        title,
        "text":         text,
        "source_type":  source_type,
        "platform":     platform,
        "language":     "en",
        "word_count":   len(text.split()) if text else 0,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "metadata":     metadata or {},
    }
