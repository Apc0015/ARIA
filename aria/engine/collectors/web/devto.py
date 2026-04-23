"""dev.to collector using the public dev.to API."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from urllib.parse import quote

from .base import BaseCollector

logger = logging.getLogger("aria")

_ARTICLES_URL = "https://dev.to/api/articles?tag={tag}&per_page=10"
_SEARCH_URL = "https://dev.to/api/articles?q={query}&per_page=10"


class DevToCollector(BaseCollector):
    """Collects articles from dev.to using the public API."""

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Fetch dev.to articles matching queries.

        Args:
            queries: Search query strings. First token used as tag, full query for search.

        Yields:
            Document dicts with platform='devto', source_type='technical_doc'.
        """
        import httpx

        seen_ids: set[int] = set()
        count = 0
        headers = {
            "User-Agent": "ARIA Research Collector/1.0",
            "Accept": "application/json",
        }

        for query in queries:
            if count >= self._max_results:
                break
            try:
                async with httpx.AsyncClient(timeout=15, headers=headers) as client:
                    # Try tag-based search first (cleaner results)
                    tag = query.split()[0].lower().replace("-", "")
                    results = await self._fetch_articles(
                        client, _ARTICLES_URL.format(tag=quote(tag))
                    )
                    # Also try full-text search
                    search_results = await self._fetch_articles(
                        client, _SEARCH_URL.format(query=quote(query))
                    )
                    # Merge, deduplicating by id
                    all_items = {
                        item["id"]: item
                        for item in (results + search_results)
                        if item.get("id")
                    }

                    for item in all_items.values():
                        if count >= self._max_results:
                            break
                        item_id = item.get("id")
                        if item_id in seen_ids:
                            continue
                        seen_ids.add(item_id)

                        doc = _build_doc(item, query)
                        if doc:
                            count += 1
                            yield doc

                await asyncio.sleep(0.5)
            except Exception as exc:
                logger.warning(
                    "DevToCollector: error for query '%s': %s", query, exc
                )

    async def _fetch_articles(self, client: Any, url: str) -> list[dict]:
        """Fetch article list from a dev.to API endpoint."""
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.debug("DevToCollector: HTTP %s for %s", resp.status_code, url)
                return []
            return resp.json() if isinstance(resp.json(), list) else []
        except Exception as exc:
            logger.debug("DevToCollector: fetch failed for %s: %s", url, exc)
            return []


def _build_doc(item: dict, query: str) -> dict[str, Any] | None:
    """Build a document from a dev.to article item."""
    try:
        title = item.get("title", "")
        description = item.get("description", "")
        body_markdown = item.get("body_markdown", "") or description
        slug = item.get("slug", "")
        username = (item.get("user") or {}).get("username", "")
        url = item.get("url", "")
        if not url and slug and username:
            url = f"https://dev.to/{username}/{slug}"
        if not url:
            return None

        text = f"{title}\n\n{body_markdown}".strip() if body_markdown else title
        if len(text) < 20:
            return None

        tags = item.get("tag_list", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        return {
            "url": url,
            "title": title,
            "text": text,
            "source_type": "technical_doc",
            "platform": "devto",
            "language": "en",
            "word_count": len(text.split()),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "query": query,
                "author": username,
                "tags": tags,
                "reactions_count": item.get("public_reactions_count", 0),
                "comments_count": item.get("comments_count", 0),
                "reading_time_minutes": item.get("reading_time_minutes", 0),
                "published_at": item.get("published_at", ""),
            },
        }
    except Exception as exc:
        logger.debug("DevToCollector: doc build error: %s", exc)
        return None
