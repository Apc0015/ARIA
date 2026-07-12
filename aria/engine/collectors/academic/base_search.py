"""BASE (Bielefeld Academic Search Engine) collector — 300M+ open access docs."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_API_URL = "https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi"


class BaseSearchCollector(BaseCollector):
    """Searches BASE (Bielefeld Academic Search Engine) for open access papers.

    No API key required. 300M+ academic documents indexed.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=25) as client:
            for query in queries[:5]:
                params = {
                    "func": "PerformSearch",
                    "query": query,
                    "format": "json",
                    "hits": min(self._max_results, 20),
                    "offset": 0,
                }
                try:
                    resp = await client.get(_API_URL, params=params)
                    if resp.status_code != 200:
                        logger.debug("BASE: HTTP %s for '%s'", resp.status_code, query)
                        continue
                    for item in resp.json().get("response", {}).get("docs", []):
                        raw_id = item.get("dcidentifier", "")
                        url = (raw_id[0] if isinstance(raw_id, list) and raw_id else raw_id) or ""
                        if not url or url in seen:
                            continue
                        seen.add(url)

                        raw_title = item.get("dctitle", "")
                        title = (raw_title[0] if isinstance(raw_title, list) else raw_title) or ""
                        raw_abstract = item.get("dcdescription", "")
                        abstract = (raw_abstract[0] if isinstance(raw_abstract, list) else raw_abstract) or ""
                        raw_authors = item.get("dccreator", [])
                        author_str = ", ".join(raw_authors[:5]) if isinstance(raw_authors, list) else str(raw_authors)
                        year = str(item.get("dcyear", ""))
                        raw_subject = item.get("dcsubject", [])
                        subject_str = ", ".join(raw_subject[:5]) if isinstance(raw_subject, list) else str(raw_subject)

                        text = f"{title}\n\n{abstract}".strip()
                        if not text or len(text) < 20:
                            continue

                        yield {
                            "url": url,
                            "title": title,
                            "text": text,
                            "source_type": "academic_paper",
                            "platform": "base_search",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "authors": author_str,
                                "year": year,
                                "subject": subject_str,
                                "query": query,
                            },
                        }
                    await asyncio.sleep(0.5)
                except Exception as exc:
                    logger.warning("BASE: error for '%s': %s", query, exc)
