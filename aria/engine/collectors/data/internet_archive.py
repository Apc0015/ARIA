"""Internet Archive collector — archived web pages, books, and documents."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_SEARCH_URL = "https://archive.org/advancedsearch.php"


class InternetArchiveCollector(BaseCollector):
    """Searches the Internet Archive for texts, documents, and web archives.

    No credentials required.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=20) as client:
            for query in queries[:4]:
                params = {
                    "q": query,
                    "output": "json",
                    "rows": min(self._max_results, 20),
                    "fl[]": ["identifier", "title", "description", "date", "mediatype", "creator"],
                    "sort[]": "downloads desc",
                }
                try:
                    resp = await client.get(_SEARCH_URL, params=params)
                    if resp.status_code != 200:
                        continue
                    for item in resp.json().get("response", {}).get("docs", []):
                        identifier = item.get("identifier", "")
                        if not identifier or identifier in seen:
                            continue
                        seen.add(identifier)

                        url = f"https://archive.org/details/{identifier}"
                        title = item.get("title", identifier)
                        description = item.get("description", "")
                        if isinstance(description, list):
                            description = " ".join(description)
                        creator = item.get("creator", "")
                        if isinstance(creator, list):
                            creator = ", ".join(creator[:3])
                        mediatype = item.get("mediatype", "")

                        text = f"{title}\n\n{description}".strip()
                        if not text or len(text) < 20:
                            continue

                        source_type = {
                            "web": "web_archive",
                            "texts": "document",
                            "books": "document",
                        }.get(mediatype, "document")

                        yield {
                            "url": url,
                            "title": title,
                            "text": text,
                            "source_type": source_type,
                            "platform": "internet_archive",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "identifier": identifier,
                                "mediatype": mediatype,
                                "date": str(item.get("date", "")),
                                "creator": creator,
                                "query": query,
                            },
                        }
                    await asyncio.sleep(0.3)
                except Exception as exc:
                    logger.warning("InternetArchive: error for '%s': %s", query, exc)
