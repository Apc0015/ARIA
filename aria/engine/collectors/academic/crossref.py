"""CrossRef REST API collector — scholarly metadata without credentials."""

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

_API_URL = "https://api.crossref.org/works"


class CrossRefCollector(BaseCollector):
    """Fetches scholarly work metadata from the CrossRef REST API.

    No API key required. Provide UNPAYWALL_EMAIL env var to join the
    polite pool and get higher rate limits.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results
        self._email = os.getenv("UNPAYWALL_EMAIL", "")

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=20) as client:
            for query in queries[:5]:
                params: dict[str, Any] = {
                    "query": query,
                    "rows": min(self._max_results, 20),
                    "select": "DOI,title,abstract,author,published,is-referenced-by-count",
                }
                if self._email:
                    params["mailto"] = self._email
                try:
                    resp = await client.get(_API_URL, params=params)
                    if resp.status_code != 200:
                        logger.debug("CrossRef: HTTP %s for '%s'", resp.status_code, query)
                        continue
                    items = resp.json().get("message", {}).get("items", [])
                    for item in items:
                        doi = item.get("DOI", "")
                        url = f"https://doi.org/{doi}" if doi else ""
                        if not url or url in seen:
                            continue
                        seen.add(url)

                        titles = item.get("title", [])
                        title = titles[0] if titles else ""
                        abstract = re.sub(r"<[^>]+>", "", item.get("abstract", ""))

                        authors = item.get("author", [])
                        author_str = ", ".join(
                            f"{a.get('given', '')} {a.get('family', '')}".strip()
                            for a in authors[:5]
                        )
                        date_parts = item.get("published", {}).get("date-parts", [[]])
                        year = str(date_parts[0][0]) if date_parts and date_parts[0] else ""
                        citation_count = item.get("is-referenced-by-count", 0)
                        text = f"{title}\n\n{abstract}".strip() if abstract else title

                        if not text:
                            continue

                        yield {
                            "url": url,
                            "title": title,
                            "text": text,
                            "source_type": "academic_paper",
                            "platform": "crossref",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "doi": doi,
                                "authors": author_str,
                                "year": year,
                                "citation_count": citation_count,
                                "query": query,
                            },
                        }
                    await asyncio.sleep(0.3)
                except Exception as exc:
                    logger.warning("CrossRef: error for '%s': %s", query, exc)
