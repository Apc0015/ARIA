"""WHO Global Health Observatory collector — health statistics and indicators."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_GHO_BASE = "https://ghoapi.azureedge.net/api"
_WHO_DOCS = "https://www.who.int/api/news"

# Key GHO indicators worth fetching for health queries
_KEY_INDICATORS = [
    ("WHOSIS_000001", "Life expectancy at birth"),
    ("WHOSIS_000015", "Healthy life expectancy (HALE) at birth"),
    ("MDG_0000000026", "Under-five mortality rate"),
    ("WHS4_100", "Maternal mortality ratio"),
    ("MDG_0000000007", "Infant mortality rate (per 1000 live births)"),
    ("WHS7_156", "Total health expenditure (% of GDP)"),
    ("SA_0000001688", "Prevalence of obesity among adults"),
    ("SDGPM25", "Annual mean concentration of PM2.5"),
]


class WHOCollector(BaseCollector):
    """Collects global health data from WHO GHO API and WHO news/publications.

    Sources:
    1. WHO Global Health Observatory (GHO) — indicator data
    2. WHO news API — announcements and publications
    """

    def __init__(
        self,
        max_results: int = 20,
        country_codes: list[str] | None = None,
    ) -> None:
        self._max_results = max_results
        self._country_codes = country_codes or []

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen_ids: set[str] = set()
        count = 0

        # Fetch GHO indicator data
        async for doc in self._fetch_indicators(seen_ids):
            if count >= self._max_results:
                break
            yield doc
            count += 1

        # Fetch WHO news for queries
        for query in queries[:3]:
            if count >= self._max_results:
                break
            async for doc in self._fetch_who_news(query, seen_ids):
                if count >= self._max_results:
                    break
                yield doc
                count += 1
            await asyncio.sleep(0.3)

    async def _fetch_indicators(
        self, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        country_filter = ""
        if self._country_codes:
            # GHO uses WHO country codes (mostly same as ISO-2)
            country_filter = f"$filter=SpatialDim in ({', '.join(repr(c) for c in self._country_codes[:10])})"

        async with httpx.AsyncClient(timeout=20) as client:
            for code, name in _KEY_INDICATORS[:6]:
                indicator_id = f"gho:{code}"
                if indicator_id in seen_ids:
                    continue

                url = f"{_GHO_BASE}/{code}"
                if country_filter:
                    url += f"?{country_filter}&$top=20"
                else:
                    url += "?$top=20"

                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    values = data.get("value", [])
                    if not values:
                        continue

                    seen_ids.add(indicator_id)

                    # Summarize data points
                    lines = [f"{name} — WHO Global Health Observatory"]
                    recent = sorted(values, key=lambda x: x.get("TimeDim", ""), reverse=True)[:15]
                    for item in recent:
                        country = item.get("SpatialDim", "")
                        year = item.get("TimeDim", "")
                        val = item.get("NumericValue") or item.get("Value", "")
                        if val and country and year:
                            lines.append(f"  {country} ({year}): {val}")

                    text = "\n".join(lines)
                    if len(text) < 40:
                        continue

                    yield {
                        "url": f"https://www.who.int/data/gho/data/indicators/indicator-details/GHO/{code}",
                        "title": name,
                        "text": text,
                        "source_type": "statistics",
                        "platform": "who",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "who_gho",
                            "indicator_code": code,
                            "countries": self._country_codes,
                        },
                    }
                    await asyncio.sleep(0.2)

                except Exception as exc:
                    logger.debug("WHOCollector: GHO indicator %s error: %s", code, exc)

    async def _fetch_who_news(
        self, query: str, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            params = {
                "sf_culture": "en",
                "pageSize": "8",
                "q": query,
            }
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(_WHO_DOCS, params=params)
                if resp.status_code != 200:
                    # Fallback: search WHO website via DDG
                    async for doc in self._search_who_ddg(query, seen_ids):
                        yield doc
                    return

                data = resp.json()
                items = data.get("value", []) or []

                for item in items:
                    item_id = str(item.get("Id", ""))
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)

                    title = item.get("Title", "") or item.get("NewsTitle", "") or ""
                    summary = item.get("Summary", "") or item.get("NewsText", "") or ""
                    url = item.get("Url", "") or item.get("NewsUrl", "")
                    if not url:
                        continue
                    if not url.startswith("http"):
                        url = f"https://www.who.int{url}"

                    date = item.get("PublicationDateAndTime", "")
                    text = f"{title}\n\nDate: {date}\n\n{summary}".strip()
                    if len(text) < 30:
                        continue

                    yield {
                        "url": url,
                        "title": title,
                        "text": text,
                        "source_type": "news",
                        "platform": "who",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "who_news",
                            "date": date,
                            "query": query,
                        },
                    }

        except Exception as exc:
            logger.debug("WHOCollector: news error for '%s': %s", query, exc)

    async def _search_who_ddg(
        self, query: str, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            results: list[dict] = []
            with DDGS() as ddgs:
                for r in ddgs.text(f"site:who.int {query}", max_results=5):
                    results.append(r)

            for r in results:
                url = r.get("href", "")
                if not url or url in seen_ids:
                    continue
                seen_ids.add(url)
                title = r.get("title", "")
                body = r.get("body", "")
                text = f"{title}\n\n{body}".strip()
                if len(text) < 30:
                    continue
                yield {
                    "url": url,
                    "title": title,
                    "text": text,
                    "source_type": "news",
                    "platform": "who",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"source": "who_ddg", "query": query},
                }
        except Exception as exc:
            logger.debug("WHOCollector: DDG fallback error: %s", exc)
