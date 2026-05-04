"""CORE.ac.uk API collector — 300M+ open access research papers."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_API_URL = "https://api.core.ac.uk/v3/search/works"


class CoreAcCollector(BaseCollector):
    """Searches CORE.ac.uk for open access academic papers.

    Optional: CORE_API_KEY env var for higher rate limits (free registration
    at core.ac.uk/api-keys). Works without a key at reduced rate.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results
        self._api_key = os.getenv("CORE_API_KEY", "")

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=20) as client:
            for query in queries[:5]:
                params = {"q": query, "limit": min(self._max_results, 25)}
                try:
                    resp = await client.get(_API_URL, params=params, headers=headers)
                    if resp.status_code != 200:
                        logger.debug("CORE.ac: HTTP %s for '%s'", resp.status_code, query)
                        continue
                    for item in resp.json().get("results", []):
                        doi = item.get("doi", "")
                        url = f"https://doi.org/{doi}" if doi else item.get("downloadUrl", "")
                        if not url or url in seen:
                            continue
                        seen.add(url)

                        title = item.get("title", "")
                        abstract = item.get("abstract", "") or ""
                        full_text = item.get("fullText", "") or ""
                        text = (full_text[:8000] if full_text else abstract).strip()
                        if not title and not text:
                            continue

                        authors = item.get("authors", []) or []
                        author_str = ", ".join(
                            a.get("name", "") for a in authors[:5] if a.get("name")
                        )
                        year = str(item.get("yearPublished", "")) if item.get("yearPublished") else ""

                        yield {
                            "url": url,
                            "title": title,
                            "text": f"{title}\n\n{text}".strip(),
                            "source_type": "academic_paper",
                            "platform": "core_ac",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "doi": doi,
                                "authors": author_str,
                                "year": year,
                                "download_url": item.get("downloadUrl", ""),
                                "query": query,
                            },
                        }
                    await asyncio.sleep(0.5)
                except Exception as exc:
                    logger.warning("CORE.ac: error for '%s': %s", query, exc)
