"""UN Data collector — UN Statistics, UNSD, UNHCR, and UN agency databases."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

# UNData API (legacy but still active)
_UNDATA_API = "http://data.un.org/ws/rest/data"
# UN Comtrade trade statistics
_COMTRADE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
# UNHCR displacement data
_UNHCR_API = "https://api.unhcr.org/population/v1/population/"


class UNDataCollector(BaseCollector):
    """Collects data from UN statistical databases.

    Sources:
    1. UN Comtrade (trade statistics) — free public API
    2. UNHCR Population Statistics — displacement + refugee data
    3. UNData indicators via web search fallback
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

        # UNHCR data
        async for doc in self._fetch_unhcr(seen_urls):
            if count >= self._max_results:
                break
            yield doc
            count += 1

        # UN agency sites web search
        for query in queries[:4]:
            if count >= self._max_results:
                break
            async for doc in self._search_un_sites(query, seen_urls):
                if count >= self._max_results:
                    break
                yield doc
                count += 1
            await asyncio.sleep(0.3)

    async def _fetch_unhcr(
        self, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            params: dict[str, Any] = {
                "limit": 10,
                "page": 1,
                "yearFrom": 2015,
                "yearTo": datetime.now().year,
            }
            if self._country_codes:
                # UNHCR uses ISO-3 codes — convert roughly
                coa = "+".join(self._country_codes[:5])
                params["coa"] = coa

            url = _UNHCR_API
            if url in seen_urls:
                return
            seen_urls.add(url)

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    return

                data = resp.json()
                items = data.get("items", [])

                if not items:
                    return

                lines = ["UNHCR Global Population Statistics"]
                for item in items[:15]:
                    year = item.get("year", "")
                    coa_name = item.get("coa_name", "")
                    refugees = item.get("refugees", 0) or 0
                    asylum_seekers = item.get("asylum_seekers", 0) or 0
                    total = item.get("total_pop", 0) or 0
                    if year and coa_name:
                        lines.append(
                            f"  {coa_name} ({year}): Refugees={refugees:,}, "
                            f"Asylum seekers={asylum_seekers:,}, Total={total:,}"
                        )

                text = "\n".join(lines)
                if len(text) < 50:
                    return

                yield {
                    "url": "https://www.unhcr.org/refugee-statistics/",
                    "title": "UNHCR Global Refugee and Displacement Statistics",
                    "text": text,
                    "source_type": "statistics",
                    "platform": "un_data",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "source": "unhcr_api",
                        "countries": self._country_codes,
                        "year_range": f"{params.get('yearFrom')}-{params.get('yearTo')}",
                    },
                }

        except Exception as exc:
            logger.debug("UNDataCollector: UNHCR error: %s", exc)

    async def _search_un_sites(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        un_sites = [
            "un.org", "data.un.org", "unstats.un.org",
            "undp.org", "unicef.org", "unfpa.org", "unep.org",
        ]
        site_filter = " OR ".join(f"site:{s}" for s in un_sites[:4])

        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            results: list[dict] = []
            with DDGS() as ddgs:
                for r in ddgs.text(f"({site_filter}) {query}", max_results=6):
                    results.append(r)

            for r in results:
                url = r.get("href", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                title = r.get("title", "")
                body = r.get("body", "")
                text = f"{title}\n\n{body}".strip()
                if len(text) < 30:
                    continue
                yield {
                    "url": url,
                    "title": title,
                    "text": text,
                    "source_type": "statistics",
                    "platform": "un_data",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"source": "un_web_search", "query": query},
                }

        except Exception as exc:
            logger.debug("UNDataCollector: UN sites search error: %s", exc)
