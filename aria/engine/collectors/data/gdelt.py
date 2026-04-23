"""GDELT collector — global news events in 100+ languages."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from urllib.parse import quote

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


class GDELTCollector(BaseCollector):
    """Collects news events from GDELT project — global news in 100+ languages.

    Uses GDELT DOC 2.0 API — no API key required.
    Supports: English articles + translated articles from global sources.
    """

    def __init__(
        self,
        max_results: int = 20,
        timespan: str = "1month",
    ) -> None:
        self._max_results = max_results
        self._timespan = timespan  # e.g. 1week, 1month, 3months

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen_urls: set[str] = set()
        count = 0

        for query in queries:
            if count >= self._max_results:
                break
            async for doc in self._search_gdelt(query, seen_urls):
                if count >= self._max_results:
                    break
                yield doc
                count += 1
            await asyncio.sleep(0.5)

    async def _search_gdelt(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            params = {
                "query": query,
                "mode": "ArtList",
                "maxrecords": min(10, self._max_results),
                "timespan": self._timespan,
                "format": "json",
                "sort": "HybridRel",
            }
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(_GDELT_DOC_API, params=params)
                if resp.status_code == 429:
                    await asyncio.sleep(2)
                    return
                if resp.status_code != 200:
                    logger.debug("GDELT: HTTP %s for '%s'", resp.status_code, query)
                    return

                data = resp.json()
                articles = data.get("articles", [])

                for art in articles:
                    url = art.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = art.get("title", "") or ""
                    seendate = art.get("seendate", "")
                    domain = art.get("domain", "")
                    language = art.get("language", "English").lower()
                    lang_code = _lang_code(language)
                    socialimage = art.get("socialimage", "")

                    # GDELT doesn't return full text — build from metadata
                    text = f"{title}"
                    if domain:
                        text += f"\nSource: {domain}"
                    if seendate:
                        text += f"\nDate: {seendate}"

                    # Try to get article content via GDELT's own viewer
                    text = text.strip()
                    if len(text) < 20:
                        continue

                    yield {
                        "url": url,
                        "title": title,
                        "text": text,
                        "source_type": "news",
                        "platform": "gdelt",
                        "language": lang_code,
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "gdelt",
                            "domain": domain,
                            "seen_date": seendate,
                            "original_language": language,
                            "social_image": socialimage,
                            "query": query,
                        },
                    }

        except Exception as exc:
            logger.warning("GDELTCollector: error for '%s': %s", query, exc)


def _lang_code(language: str) -> str:
    mapping = {
        "english": "en", "spanish": "es", "french": "fr",
        "german": "de", "portuguese": "pt", "arabic": "ar",
        "chinese": "zh", "russian": "ru", "hindi": "hi",
        "japanese": "ja", "korean": "ko",
    }
    return mapping.get(language.lower(), "en")
