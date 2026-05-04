"""Europe PMC collector — biomedical literature including bioRxiv/medRxiv."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


class EuropePMCCollector(BaseCollector):
    """Searches Europe PMC for biomedical literature.

    No API key required. Covers PubMed Central, bioRxiv, medRxiv, and more.
    """

    def __init__(self, max_results: int = 25) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=20) as client:
            for query in queries[:5]:
                params = {
                    "query": query,
                    "format": "json",
                    "resultType": "core",
                    "pageSize": min(self._max_results, 25),
                }
                try:
                    resp = await client.get(_API_URL, params=params)
                    if resp.status_code != 200:
                        logger.debug("EuropePMC: HTTP %s for '%s'", resp.status_code, query)
                        continue
                    results = resp.json().get("resultList", {}).get("result", [])
                    for item in results:
                        doi = item.get("doi", "")
                        url = (
                            f"https://doi.org/{doi}" if doi
                            else f"https://europepmc.org/article/{item.get('source', '')}/{item.get('id', '')}"
                        )
                        if not url or url in seen:
                            continue
                        seen.add(url)

                        title = item.get("title", "")
                        abstract = item.get("abstractText", "") or ""
                        text = f"{title}\n\n{abstract}".strip()
                        if not text:
                            continue

                        yield {
                            "url": url,
                            "title": title,
                            "text": text,
                            "source_type": "academic_paper",
                            "platform": "europe_pmc",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "doi": doi,
                                "pmcid": item.get("pmcid", ""),
                                "authors": item.get("authorString", ""),
                                "year": str(item.get("pubYear", "")),
                                "source": item.get("source", ""),
                                "query": query,
                            },
                        }
                    await asyncio.sleep(0.3)
                except Exception as exc:
                    logger.warning("EuropePMC: error for '%s': %s", query, exc)
