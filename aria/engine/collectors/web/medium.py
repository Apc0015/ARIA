"""Medium collector — uses DuckDuckGo site search (medium.com is a JS SPA)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

from .base import BaseCollector

logger = logging.getLogger("aria")


class MediumCollector(BaseCollector):
    """Collects Medium articles via DuckDuckGo site:medium.com search.

    Medium's website is a JavaScript SPA — direct scraping returns an empty
    shell. DuckDuckGo indexes Medium's content and provides reliable results
    without requiring a Medium account or API key.
    """

    def __init__(self, max_results: int = 15) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Search Medium articles via DuckDuckGo and yield documents.

        Args:
            queries: Search query strings.

        Yields:
            Document dicts with platform='medium', source_type='opinion_essay'.
        """
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        seen_urls: set[str] = set()
        count = 0
        now = datetime.now(timezone.utc).isoformat()

        for query in queries:
            if count >= self._max_results:
                break
            try:
                search_query = f"site:medium.com {query}"
                results = []

                def _search() -> list:
                    with DDGS() as ddgs:
                        return list(ddgs.text(search_query, max_results=8))

                # Run blocking DDGS in thread pool
                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(None, _search)

                for result in results:
                    if count >= self._max_results:
                        break

                    url = result.get("href", "")
                    if not url or "medium.com" not in url:
                        continue
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = result.get("title", "").strip()
                    body = result.get("body", "").strip()
                    text = f"{title}\n\n{body}".strip() if body else title

                    if not title or len(text) < 20:
                        continue

                    count += 1
                    yield {
                        "url": url,
                        "title": title,
                        "text": text,
                        "source_type": "opinion_essay",
                        "platform": "medium",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": now,
                        "metadata": {
                            "query": query,
                            "snippet": body[:200],
                        },
                    }

                await asyncio.sleep(0.5)
            except Exception as exc:
                logger.warning("MediumCollector: error for query '%s': %s", query, exc)
