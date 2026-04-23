"""Eurostat collector — EU statistical data and datasets."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_EUROSTAT_SEARCH = "https://ec.europa.eu/eurostat/api/dissemination/catalogue/toc/json"
_EUROSTAT_DATA = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"
_EUROSTAT_NAVIGATOR = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

# High-value datasets for EU research
_KEY_DATASETS = [
    ("une_rt_m", "Monthly unemployment by country"),
    ("nama_10_gdp", "GDP and main components"),
    ("ilc_di12", "Gini coefficient of equivalised disposable income"),
    ("hlth_ehis_bm1e", "Body mass index by country"),
    ("env_air_emis", "Air pollutant emissions by country"),
]


class EurostatCollector(BaseCollector):
    """Collects statistical data from Eurostat (EU statistics office).

    Free API, no key required.
    Covers EU/EEA countries: employment, GDP, health, environment, trade.
    """

    def __init__(
        self,
        max_results: int = 20,
        country_codes: list[str] | None = None,
    ) -> None:
        self._max_results = max_results
        # Filter to EU countries only
        _eu_codes = {"AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE",
                     "GR","HU","IE","IT","LV","LT","LU","MT","NL","PL","PT",
                     "RO","SK","SI","ES","SE","NO","IS","LI","CH","UK"}
        self._country_codes = [c for c in (country_codes or []) if c in _eu_codes]

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen_ids: set[str] = set()
        count = 0

        # Search Eurostat catalogue
        for query in queries[:3]:
            if count >= self._max_results:
                break
            async for doc in self._search_catalogue(query, seen_ids):
                if count >= self._max_results:
                    break
                yield doc
                count += 1
            await asyncio.sleep(0.3)

        # Fetch key dataset summaries
        if count < self._max_results:
            async for doc in self._fetch_key_datasets(seen_ids):
                if count >= self._max_results:
                    break
                yield doc
                count += 1

    async def _search_catalogue(
        self, query: str, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(_EUROSTAT_SEARCH, params={"lang": "en"})
                if resp.status_code != 200:
                    return

                data = resp.json()
                all_datasets = data.get("link", [])

                # Simple keyword filter
                q_lower = query.lower()
                matches = [
                    d for d in all_datasets
                    if q_lower in (d.get("label", "") or "").lower()
                    or q_lower in (d.get("code", "") or "").lower()
                ][:5]

                for item in matches:
                    code = item.get("code", "")
                    if code in seen_ids:
                        continue
                    seen_ids.add(code)

                    label = item.get("label", "")
                    last_update = item.get("lastUpdate", "")
                    data_start = item.get("dataStart", "")
                    data_end = item.get("dataEnd", "")

                    text_parts = [label]
                    text_parts.append(f"Dataset: {code}")
                    if data_start and data_end:
                        text_parts.append(f"Coverage: {data_start}–{data_end}")
                    if last_update:
                        text_parts.append(f"Last updated: {last_update}")

                    text = "\n".join(text_parts).strip()
                    if len(text) < 20:
                        continue

                    yield {
                        "url": f"https://ec.europa.eu/eurostat/databrowser/view/{code}/default/table",
                        "title": label,
                        "text": text,
                        "source_type": "statistics",
                        "platform": "eurostat",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "eurostat",
                            "dataset_code": code,
                            "data_start": data_start,
                            "data_end": data_end,
                            "query": query,
                        },
                    }

        except Exception as exc:
            logger.warning("EurostatCollector: catalogue search error: %s", exc)

    async def _fetch_key_datasets(
        self, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        geo_filter = "+".join(self._country_codes[:10]) if self._country_codes else "EU27_2020+DE+FR+IT+ES"

        async with httpx.AsyncClient(timeout=25) as client:
            for code, name in _KEY_DATASETS[:3]:
                if code in seen_ids:
                    continue

                try:
                    # Fetch last 3 years of data for selected countries
                    url = f"{_EUROSTAT_NAVIGATOR}/{code}?format=JSON&lang=en&geo={geo_filter}&lastTimePeriod=3"
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    dimension = data.get("dimension", {})
                    value = data.get("value", {})

                    if not value:
                        continue

                    seen_ids.add(code)
                    lines = [f"{name} — Eurostat ({code})"]
                    lines.append(f"Countries: {geo_filter.replace('+', ', ')}")

                    # Just note we have data
                    lines.append(f"Data points available: {len(value)}")

                    text = "\n".join(lines)
                    yield {
                        "url": f"https://ec.europa.eu/eurostat/databrowser/view/{code}/default/table",
                        "title": name,
                        "text": text,
                        "source_type": "statistics",
                        "platform": "eurostat",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "eurostat_api",
                            "dataset_code": code,
                            "countries": self._country_codes,
                        },
                    }
                    await asyncio.sleep(0.3)

                except Exception as exc:
                    logger.debug("EurostatCollector: dataset %s error: %s", code, exc)
