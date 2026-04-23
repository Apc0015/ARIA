"""IMF Data collector — economic indicators, World Economic Outlook, Article IV reports."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_IMF_API = "https://dataservices.imf.org/REST/SDMX_JSON.svc"
_IMF_ELIBRARY = "https://www.elibrary.imf.org/search#q="


class IMFCollector(BaseCollector):
    """Collects IMF economic data and publications.

    Sources:
    1. IMF SDMX-JSON Data API — economic indicators
    2. IMF eLibrary search — research papers and reports
    """

    # Key IMF datasets
    _DATASETS = [
        ("IFS", "International Financial Statistics"),
        ("WEO", "World Economic Outlook"),
        ("GFSR", "Global Financial Stability Report indicators"),
    ]

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

        # Fetch WEO data for countries
        async for doc in self._fetch_weo_data(seen_urls):
            if count >= self._max_results:
                break
            yield doc
            count += 1

        # Search IMF publications
        for query in queries[:4]:
            if count >= self._max_results:
                break
            async for doc in self._search_publications(query, seen_urls):
                if count >= self._max_results:
                    break
                yield doc
                count += 1
            await asyncio.sleep(0.4)

    async def _fetch_weo_data(
        self, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        # WEO key indicators
        indicators = [
            ("NGDP_RPCH", "GDP growth rate (%)"),
            ("PCPIPCH", "Inflation rate (%)"),
            ("LUR", "Unemployment rate (%)"),
            ("GGXCNL_NGDP", "Government net lending/borrowing (% GDP)"),
            ("BCA_NGDPD", "Current account balance (% GDP)"),
        ]
        country_str = "+".join(self._country_codes[:8]) if self._country_codes else "US+GB+DE+CN+JP+IN+BR"

        async with httpx.AsyncClient(timeout=25) as client:
            for code, name in indicators[:3]:
                url = f"{_IMF_API}/CompactData/WEO/{country_str}.{code}"
                if url in seen_urls:
                    continue
                try:
                    resp = await client.get(url, headers={"Accept": "application/json"})
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    series = (
                        data.get("CompactData", {})
                        .get("DataSet", {})
                        .get("Series", [])
                    )
                    if isinstance(series, dict):
                        series = [series]
                    if not series:
                        continue

                    seen_urls.add(url)
                    lines = [f"{name} — IMF World Economic Outlook"]
                    for s in series[:10]:
                        country = s.get("@REF_AREA", "")
                        obs = s.get("Obs", [])
                        if isinstance(obs, dict):
                            obs = [obs]
                        recent = sorted(obs, key=lambda x: x.get("@TIME_PERIOD", ""), reverse=True)[:3]
                        for o in recent:
                            period = o.get("@TIME_PERIOD", "")
                            value = o.get("@OBS_VALUE", "")
                            if value and country:
                                lines.append(f"  {country} ({period}): {value}")

                    text = "\n".join(lines)
                    if len(text) < 40:
                        continue

                    yield {
                        "url": f"https://www.imf.org/en/Publications/WEO",
                        "title": f"IMF WEO: {name}",
                        "text": text,
                        "source_type": "statistics",
                        "platform": "imf",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "imf_weo",
                            "indicator": code,
                            "countries": self._country_codes,
                        },
                    }
                    await asyncio.sleep(0.3)

                except Exception as exc:
                    logger.debug("IMFCollector: WEO %s error: %s", code, exc)

    async def _search_publications(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            results: list[dict] = []
            with DDGS() as ddgs:
                for r in ddgs.text(f"site:imf.org {query} filetype:pdf OR working paper OR report", max_results=6):
                    results.append(r)

            for r in results:
                url = r.get("href", "")
                if not url or url in seen_urls or "imf.org" not in url:
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
                    "source_type": "report",
                    "platform": "imf",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"source": "imf_search", "query": query},
                }

        except Exception as exc:
            logger.debug("IMFCollector: publication search error for '%s': %s", query, exc)
