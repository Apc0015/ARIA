"""Wikipedia collector using the MediaWiki REST and Action APIs."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from urllib.parse import quote

from .base import BaseCollector

logger = logging.getLogger("aria")

_SEARCH_URL = (
    "https://en.wikipedia.org/w/api.php"
    "?action=query&list=search&srsearch={query}&srlimit=5&format=json&srprop=snippet"
)
_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"


class WikipediaCollector(BaseCollector):
    """Searches Wikipedia and fetches article summaries via the MediaWiki APIs."""

    def __init__(self, max_results: int = 10) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Search Wikipedia and yield article summary documents.

        Args:
            queries: Search query strings.

        Yields:
            Document dicts with platform='wikipedia', source_type='encyclopedia'.
        """
        import httpx

        seen_titles: set[str] = set()
        count = 0

        for query in queries:
            if count >= self._max_results:
                break
            try:
                search_url = _SEARCH_URL.format(query=quote(query))
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        search_url,
                        headers={"User-Agent": "ARIA/4.1 (https://github.com/aria-research; research@aria.local) python-httpx"},
                    )
                    if resp.status_code != 200:
                        logger.debug(
                            "WikipediaCollector: search HTTP %s for '%s'",
                            resp.status_code,
                            query,
                        )
                        continue
                    data = resp.json()
                    results = data.get("query", {}).get("search", [])

                    for result in results:
                        if count >= self._max_results:
                            break
                        title = result.get("title", "")
                        if not title or title in seen_titles:
                            continue
                        seen_titles.add(title)

                        doc = await self._fetch_summary(client, title, query)
                        if doc:
                            count += 1
                            yield doc
                        await asyncio.sleep(0.2)

            except Exception as exc:
                logger.warning(
                    "WikipediaCollector: error for query '%s': %s", query, exc
                )

    async def _fetch_summary(
        self, client: Any, title: str, query: str
    ) -> dict[str, Any] | None:
        """Fetch a page summary from the REST API."""
        try:
            encoded_title = quote(title.replace(" ", "_"))
            url = _SUMMARY_URL.format(title=encoded_title)
            resp = await client.get(
                url, headers={"User-Agent": "ARIA/4.1 (https://github.com/aria-research; research@aria.local) python-httpx"}
            )
            if resp.status_code != 200:
                return None
            data = resp.json()

            page_title = data.get("title", title)
            extract = data.get("extract", "")
            if not extract or len(extract.strip()) < 50:
                return None

            page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
            if not page_url:
                page_url = (
                    f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
                )

            return {
                "url": page_url,
                "title": page_title,
                "text": extract,
                "source_type": "encyclopedia",
                "platform": "wikipedia",
                "language": data.get("lang", "en"),
                "word_count": len(extract.split()),
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "query": query,
                    "pageid": data.get("pageid"),
                    "description": data.get("description", ""),
                    "thumbnail": (data.get("thumbnail") or {}).get("source", ""),
                    "last_modified": data.get("timestamp", ""),
                },
            }
        except Exception as exc:
            logger.debug(
                "WikipediaCollector: summary fetch failed for '%s': %s", title, exc
            )
            return None
