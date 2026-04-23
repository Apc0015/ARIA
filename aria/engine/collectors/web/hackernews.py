"""Hacker News collector using the Algolia HN search API."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

from .base import BaseCollector

logger = logging.getLogger("aria")


class HackerNewsCollector(BaseCollector):
    """Collects stories from Hacker News via the Algolia search API."""

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Search HN and yield story documents.

        Args:
            queries: Search query strings.

        Yields:
            Document dicts with platform='hackernews', source_type='web_post'.
        """
        import httpx

        seen_ids: set[str] = set()

        for query in queries:
            try:
                url = (
                    f"https://hn.algolia.com/api/v1/search"
                    f"?query={query}&tags=story&hitsPerPage={self._max_results}"
                )
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.debug(
                            "HackerNewsCollector: HTTP %s for query '%s'",
                            resp.status_code,
                            query,
                        )
                        continue
                    data = resp.json()
                    hits = data.get("hits", [])
                    for hit in hits:
                        hit_id = str(hit.get("objectID", ""))
                        if hit_id in seen_ids:
                            continue
                        seen_ids.add(hit_id)

                        hn_url = (
                            hit.get("url")
                            or f"https://news.ycombinator.com/item?id={hit_id}"
                        )
                        title = hit.get("title", "")
                        text = hit.get("story_text", "") or title
                        if not text or len(text.strip()) < 10:
                            continue

                        yield {
                            "url": hn_url,
                            "title": title,
                            "text": text,
                            "source_type": "web_post",
                            "platform": "hackernews",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "query": query,
                                "hn_id": hit_id,
                                "points": hit.get("points", 0),
                                "num_comments": hit.get("num_comments", 0),
                                "author": hit.get("author", ""),
                                "created_at": hit.get("created_at", ""),
                            },
                        }
                await asyncio.sleep(0.3)
            except Exception as exc:
                logger.warning(
                    "HackerNewsCollector: error for query '%s': %s", query, exc
                )
