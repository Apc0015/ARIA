"""Vimeo collector — searches videos via the Vimeo API v3 (requires VIMEO_ACCESS_TOKEN)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from urllib.parse import quote

from .base import BaseCollector

logger = logging.getLogger("aria")

_SEARCH_URL = "https://api.vimeo.com/videos?query={query}&per_page=10&fields=uri,name,description,link,duration,created_time,stats"


class VimeoCollector(BaseCollector):
    """Collects videos from Vimeo via the Vimeo API v3.

    Requires the VIMEO_ACCESS_TOKEN environment variable.
    Silently skips if the token is not set.
    """

    async def validate(self) -> bool:
        return bool(os.getenv("VIMEO_ACCESS_TOKEN"))

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Search Vimeo for videos matching queries.

        Args:
            queries: Search query strings.

        Yields:
            Document dicts with platform='vimeo', source_type='video_transcript'.
        """
        import httpx

        token = os.getenv("VIMEO_ACCESS_TOKEN")
        if not token:
            logger.info("VimeoCollector: no VIMEO_ACCESS_TOKEN set, skipping")
            return

        headers = {
            "Authorization": f"bearer {token}",
            "Accept": "application/vnd.vimeo.*+json;version=3.4",
            "User-Agent": "ARIA Research Collector/1.0",
        }
        seen_uris: set[str] = set()

        for query in queries:
            try:
                url = _SEARCH_URL.format(query=quote(query))
                async with httpx.AsyncClient(timeout=15, headers=headers) as client:
                    resp = await client.get(url)
                    if resp.status_code == 401:
                        logger.warning("VimeoCollector: invalid access token (401)")
                        return
                    if resp.status_code != 200:
                        logger.debug(
                            "VimeoCollector: HTTP %s for query '%s'",
                            resp.status_code,
                            query,
                        )
                        continue

                    data = resp.json()
                    videos = data.get("data", [])

                    for video in videos:
                        uri = video.get("uri", "")
                        if uri in seen_uris:
                            continue
                        seen_uris.add(uri)

                        name = video.get("name", "")
                        description = video.get("description", "") or ""
                        link = video.get("link", "")
                        if not link and uri:
                            link = f"https://vimeo.com{uri}"

                        text = f"{name}\n\n{description}".strip()
                        if len(text) < 10:
                            continue

                        stats = video.get("stats", {})
                        yield {
                            "url": link,
                            "title": name,
                            "text": text,
                            "source_type": "video_transcript",
                            "platform": "vimeo",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "query": query,
                                "uri": uri,
                                "duration_seconds": video.get("duration", 0),
                                "created_time": video.get("created_time", ""),
                                "plays": stats.get("plays", 0),
                                "likes": stats.get("likes", 0),
                            },
                        }

            except Exception as exc:
                logger.warning(
                    "VimeoCollector: error for query '%s': %s", query, exc
                )
        yield  # ensure this is an async generator even if token is set but no results
