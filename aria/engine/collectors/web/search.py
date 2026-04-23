"""Web search collector using DuckDuckGo (with SerpAPI fallback)."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any, Optional

from .base import BaseCollector

logger = logging.getLogger("aria")


class WebSearchCollector(BaseCollector):
    """Collects documents via web search.

    Primary backend: DuckDuckGo (via duckduckgo_search)
    Fallback: SerpAPI (if SERPAPI_KEY environment variable is set)
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
        """Search the web for each query and yield document dicts.

        Args:
            queries: List of search query strings.

        Yields:
            Document dicts with source_type='web_search'.
        """
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
        """Search using DuckDuckGo."""
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

            for item in results:
                url = item.get("href", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                text = item.get("body", "")
                title = item.get("title", "")

                yield _make_doc(
                    url=url,
                    title=title,
                    text=text,
                    source_type="web_search",
                    platform="duckduckgo",
                    metadata={"query": query, "snippet": text},
                )

        except Exception as exc:
            logger.warning("WebSearchCollector DDGS error for '%s': %s", query, exc)

    async def _serpapi_search(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Search using SerpAPI."""
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
                organic = data.get("organic_results", [])
                for item in organic:
                    url = item.get("link", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    yield _make_doc(
                        url=url,
                        title=item.get("title", ""),
                        text=item.get("snippet", ""),
                        source_type="web_search",
                        platform="serpapi",
                        metadata={"query": query, "position": item.get("position")},
                    )
        except Exception as exc:
            logger.warning("WebSearchCollector SerpAPI error for '%s': %s", query, exc)


def _make_doc(
    url: str,
    title: str,
    text: str,
    source_type: str,
    platform: str,
    metadata: Optional[dict] = None,
) -> dict:
    return {
        "url": url,
        "title": title,
        "text": text,
        "source_type": source_type,
        "platform": platform,
        "language": "en",
        "word_count": len(text.split()) if text else 0,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
    }
