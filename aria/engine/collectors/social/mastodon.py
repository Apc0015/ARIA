"""Mastodon public status search — no auth required for public posts."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_SEARCH_URL = "https://mastodon.social/api/v2/search"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


class MastodonCollector(BaseCollector):
    """Searches mastodon.social for public posts matching queries.

    No credentials required for public search.
    Optional: MASTODON_ACCESS_TOKEN for higher rate limits.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results
        self._token = os.getenv("MASTODON_ACCESS_TOKEN", "")

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            for query in queries[:4]:
                params = {
                    "q": query,
                    "type": "statuses",
                    "limit": min(self._max_results, 20),
                    "resolve": "false",
                }
                try:
                    resp = await client.get(_SEARCH_URL, params=params)
                    if resp.status_code == 401:
                        logger.info("MastodonCollector: 401 — unauthenticated search restricted")
                        continue
                    if resp.status_code != 200:
                        logger.debug("Mastodon: HTTP %s for '%s'", resp.status_code, query)
                        continue
                    for status in resp.json().get("statuses", []):
                        url = status.get("url", "")
                        if not url or url in seen:
                            continue
                        seen.add(url)

                        content = _strip_html(status.get("content", ""))
                        if not content or len(content) < 20:
                            continue

                        account = status.get("account", {})
                        author = account.get("acct", "") or account.get("username", "")

                        yield {
                            "url": url,
                            "title": f"@{author}: {content[:80]}",
                            "text": content,
                            "source_type": "social_media",
                            "platform": "mastodon",
                            "language": "en",
                            "word_count": len(content.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "author": author,
                                "created_at": status.get("created_at", ""),
                                "favourites_count": status.get("favourites_count", 0),
                                "reblogs_count": status.get("reblogs_count", 0),
                                "query": query,
                            },
                        }
                    await asyncio.sleep(1.0)  # 300 req/5min rate limit
                except Exception as exc:
                    logger.warning("Mastodon: error for '%s': %s", query, exc)
