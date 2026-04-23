"""World Bank Open Data collector — indicators, country data, development stats."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_WB_BASE = "https://api.worldbank.org/v2"
_WB_SEARCH = "https://search.worldbank.org/api/v2/wds"


class WorldBankCollector(BaseCollector):
    """Collects data from World Bank Open Data API and document search.

    Sources:
    1. World Bank document search (research, reports, policy papers)
    2. World Bank indicators API (time-series economic data)
    """

    def __init__(
        self,
        max_results: int = 20,
        country_codes: list[str] | None = None,
    ) -> None:
        self._max_results = max_results
        self._country_codes = country_codes or []

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen_urls: set[str] = set()
        count = 0

        for query in queries:
            if count >= self._max_results:
                break
            async for doc in self._search_documents(query, seen_urls):
                if count >= self._max_results:
                    break
                yield doc
                count += 1
            await asyncio.sleep(0.3)

        if self._country_codes and count < self._max_results:
            async for doc in self._fetch_indicator_data(seen_urls):
                if count >= self._max_results:
                    break
                yield doc
                count += 1

    async def _search_documents(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            params: dict[str, Any] = {
                "qterm": query,
                "format": "json",
                "rows": min(10, self._max_results),
                "fl": "id,docdt,display_title,abstract,url,source,subtopic,docty",
                "sort": "score desc",
            }
            if self._country_codes:
                params["countrycode_exact"] = " OR ".join(self._country_codes[:5])

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(_WB_SEARCH, params=params)
                if resp.status_code != 200:
                    return
                data = resp.json()
                docs = data.get("documents", {})
                # The response is a dict of id→doc
                if isinstance(docs, dict):
                    items = [v for k, v in docs.items() if k != "facets"]
                else:
                    items = docs

                for item in items:
                    url = item.get("url", "") or f"https://documents.worldbank.org/en/publication/documents-reports/documentdetail/{item.get('id', '')}"
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = item.get("display_title", "") or item.get("docty", "")
                    abstract = item.get("abstract", "") or ""
                    source = item.get("source", "World Bank")
                    subtopic = item.get("subtopic", "")
                    doc_date = item.get("docdt", "")

                    text = f"{title}\n\nSource: {source}"
                    if subtopic:
                        text += f"\nTopic: {subtopic}"
                    if doc_date:
                        text += f"\nDate: {doc_date}"
                    if abstract:
                        text += f"\n\n{abstract}"
                    text = text.strip()
                    if len(text) < 20:
                        continue

                    yield {
                        "url": url,
                        "title": title,
                        "text": text,
                        "source_type": "report",
                        "platform": "world_bank",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "world_bank_docs",
                            "document_type": item.get("docty", ""),
                            "date": doc_date,
                            "query": query,
                        },
                    }

        except Exception as exc:
            logger.warning("WorldBankCollector: document search error: %s", exc)

    async def _fetch_indicator_data(
        self, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        key_indicators = [
            ("NY.GDP.MKTP.CD", "GDP (current US$)"),
            ("SP.POP.TOTL", "Population, total"),
            ("SL.UEM.TOTL.ZS", "Unemployment rate (% of total labor force)"),
            ("SI.POV.DDAY", "Poverty headcount ratio ($2.15/day, %)"),
        ]
        country_str = ";".join(self._country_codes[:5]) if self._country_codes else "WLD"

        async with httpx.AsyncClient(timeout=20) as client:
            for indicator_code, indicator_name in key_indicators:
                url = f"{_WB_BASE}/country/{country_str}/indicator/{indicator_code}?format=json&mrv=5&per_page=50"
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    payload = resp.json()
                    if not isinstance(payload, list) or len(payload) < 2:
                        continue
                    data_points = payload[1] or []
                    if not data_points:
                        continue

                    # Build a text summary from recent data
                    lines = [f"{indicator_name} — World Bank Data"]
                    for dp in data_points[:10]:
                        country = dp.get("country", {}).get("value", "")
                        year = dp.get("date", "")
                        value = dp.get("value")
                        if value is not None:
                            lines.append(f"  {country} ({year}): {value:,.2f}" if isinstance(value, float) else f"  {country} ({year}): {value}")

                    text = "\n".join(lines)
                    yield {
                        "url": f"https://data.worldbank.org/indicator/{indicator_code}",
                        "title": indicator_name,
                        "text": text,
                        "source_type": "statistics",
                        "platform": "world_bank",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "world_bank_api",
                            "indicator": indicator_code,
                            "countries": self._country_codes,
                        },
                    }
                    await asyncio.sleep(0.2)
                except Exception as exc:
                    logger.debug("WorldBankCollector: indicator %s error: %s", indicator_code, exc)
