"""Hacker News collector using the Algolia HN search API."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_ALGOLIA_SEARCH     = "https://hn.algolia.com/api/v1/search"
_ALGOLIA_BY_DATE    = "https://hn.algolia.com/api/v1/search_by_date"


class HackerNewsCollector(BaseCollector):
    """Collects stories from Hacker News via the Algolia search API.

    Most HN stories are link posts with no body text — the collector
    builds meaningful content from title + external URL + comment count
    rather than requiring story_text (which only exists on Ask/Show HN).
    Tries both relevance-sorted and date-sorted endpoints so recent and
    popular posts are both covered.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen_ids: set[str] = set()
        count = 0

        async with httpx.AsyncClient(timeout=20) as client:
            for query in queries:
                if count >= self._max_results:
                    break
                async for doc in self._search_query(client, query, seen_ids):
                    yield doc
                    count += 1
                    if count >= self._max_results:
                        break
                await asyncio.sleep(0.3)

    async def _search_query(
        self,
        client: httpx.AsyncClient,
        query: str,
        seen_ids: set[str],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Try relevance search then date search for one query."""
        per_page = min(self._max_results * 2, 30)  # fetch extra to survive filtering

        for endpoint in (_ALGOLIA_SEARCH, _ALGOLIA_BY_DATE):
            try:
                resp = await client.get(
                    endpoint,
                    params={
                        "query":        query,
                        "tags":         "story",
                        "hitsPerPage":  per_page,
                    },
                )
                if resp.status_code == 429:
                    logger.debug("HackerNews: rate limited, backing off")
                    await asyncio.sleep(2)
                    continue
                if resp.status_code != 200:
                    logger.debug("HackerNews: HTTP %d for '%s'", resp.status_code, query)
                    continue

                hits = resp.json().get("hits", [])
                logger.debug("HackerNews: '%s' → %d hits from %s", query, len(hits), endpoint)

                for hit in hits:
                    hit_id = str(hit.get("objectID", ""))
                    if not hit_id or hit_id in seen_ids:
                        continue
                    seen_ids.add(hit_id)

                    title   = (hit.get("title") or "").strip()
                    if not title:
                        continue

                    ext_url = hit.get("url") or ""
                    hn_url  = ext_url or f"https://news.ycombinator.com/item?id={hit_id}"

                    # story_text only exists for Ask/Show HN self-posts.
                    # For link posts, build useful text from title + context.
                    story_text = (hit.get("story_text") or "").strip()
                    if story_text:
                        text = f"{title}\n\n{story_text}"
                    elif ext_url:
                        text = (
                            f"{title}\n\n"
                            f"Link: {ext_url}\n"
                            f"Points: {hit.get('points', 0)} | "
                            f"Comments: {hit.get('num_comments', 0)}"
                        )
                    else:
                        text = title

                    yield {
                        "url":          hn_url,
                        "title":        title,
                        "text":         text,
                        "source_type":  "web_post",
                        "platform":     "hackernews",
                        "language":     "en",
                        "word_count":   len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "query":        query,
                            "hn_id":        hit_id,
                            "points":       hit.get("points", 0),
                            "num_comments": hit.get("num_comments", 0),
                            "author":       hit.get("author", ""),
                            "created_at":   hit.get("created_at", ""),
                            "external_url": ext_url,
                        },
                    }

                # If relevance search returned results, skip date search
                if hits:
                    break

            except Exception as exc:
                logger.warning("HackerNews: error for '%s': %s", query, exc)
