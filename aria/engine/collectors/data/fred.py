"""FRED collector — Federal Reserve Economic Data (economic time-series)."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_FRED_BASE = "https://api.stlouisfed.org/fred"

# High-value series to fetch when no specific query
_DEFAULT_SERIES = [
    ("GDP", "Gross Domestic Product"),
    ("UNRATE", "Unemployment Rate"),
    ("CPIAUCSL", "Consumer Price Index (All Urban)"),
    ("FEDFUNDS", "Federal Funds Effective Rate"),
    ("DGS10", "10-Year Treasury Constant Maturity Rate"),
    ("PAYEMS", "Total Nonfarm Payrolls"),
    ("INDPRO", "Industrial Production Index"),
    ("HOUST", "Housing Starts: Total"),
]


class FREDCollector(BaseCollector):
    """Collects economic time-series from FRED (Federal Reserve Bank of St. Louis).

    Requires FRED_API_KEY env var (free at fred.stlouisfed.org).
    Falls back to DuckDuckGo search if no key.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results
        self._api_key = os.getenv("FRED_API_KEY", "")

    async def validate(self) -> bool:
        return bool(self._api_key)

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen_ids: set[str] = set()
        count = 0

        if self._api_key:
            # Search for series matching each query
            for query in queries[:3]:
                if count >= self._max_results:
                    break
                async for doc in self._search_series(query, seen_ids):
                    if count >= self._max_results:
                        break
                    yield doc
                    count += 1
                await asyncio.sleep(0.3)

            # Fetch default key series if still under limit
            if count < self._max_results:
                async for doc in self._fetch_default_series(seen_ids):
                    if count >= self._max_results:
                        break
                    yield doc
                    count += 1
        else:
            # No API key — search FRED via web
            for query in queries[:3]:
                if count >= self._max_results:
                    break
                async for doc in self._search_fred_web(query, seen_ids):
                    if count >= self._max_results:
                        break
                    yield doc
                    count += 1

    async def _search_series(
        self, query: str, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            params = {
                "search_text": query,
                "api_key": self._api_key,
                "file_type": "json",
                "limit": 5,
                "order_by": "popularity",
                "sort_order": "desc",
            }
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{_FRED_BASE}/series/search", params=params)
                if resp.status_code != 200:
                    return

                data = resp.json()
                series_list = data.get("seriess", [])

                for s in series_list[:5]:
                    series_id = s.get("id", "")
                    if series_id in seen_ids:
                        continue
                    seen_ids.add(series_id)

                    title = s.get("title", "")
                    notes = s.get("notes", "") or ""
                    frequency = s.get("frequency_short", "")
                    units = s.get("units", "")
                    seasonal = s.get("seasonal_adjustment_short", "")
                    last_updated = s.get("last_updated", "")

                    # Fetch recent observations
                    obs_text = await self._fetch_observations(series_id)

                    text = (
                        f"{title}\n"
                        f"Series ID: {series_id} | Frequency: {frequency} | Units: {units}"
                    )
                    if seasonal:
                        text += f" | Adjustment: {seasonal}"
                    if notes:
                        text += f"\n\n{notes[:500]}"
                    if obs_text:
                        text += f"\n\nRecent data:\n{obs_text}"
                    text = text.strip()

                    yield {
                        "url": f"https://fred.stlouisfed.org/series/{series_id}",
                        "title": title,
                        "text": text,
                        "source_type": "statistics",
                        "platform": "fred",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "fred",
                            "series_id": series_id,
                            "frequency": frequency,
                            "units": units,
                            "last_updated": last_updated,
                            "query": query,
                        },
                    }

        except Exception as exc:
            logger.warning("FREDCollector: search error for '%s': %s", query, exc)

    async def _fetch_observations(self, series_id: str) -> str:
        try:
            params = {
                "series_id": series_id,
                "api_key": self._api_key,
                "file_type": "json",
                "limit": 12,
                "sort_order": "desc",
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{_FRED_BASE}/series/observations", params=params)
                if resp.status_code != 200:
                    return ""
                data = resp.json()
                obs = data.get("observations", [])
                lines = [f"  {o['date']}: {o['value']}" for o in obs if o.get("value", ".") != "."]
                return "\n".join(lines[:12])
        except Exception:
            return ""

    async def _fetch_default_series(
        self, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        for series_id, name in _DEFAULT_SERIES:
            if series_id in seen_ids:
                continue
            seen_ids.add(series_id)
            obs_text = await self._fetch_observations(series_id)
            if not obs_text:
                continue
            text = f"{name} (FRED: {series_id})\n\nRecent data:\n{obs_text}"
            yield {
                "url": f"https://fred.stlouisfed.org/series/{series_id}",
                "title": name,
                "text": text,
                "source_type": "statistics",
                "platform": "fred",
                "language": "en",
                "word_count": len(text.split()),
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {"source": "fred", "series_id": series_id},
            }
            await asyncio.sleep(0.2)

    async def _search_fred_web(
        self, query: str, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            results: list[dict] = []
            with DDGS() as ddgs:
                for r in ddgs.text(f"site:fred.stlouisfed.org {query}", max_results=5):
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
                    "source_type": "statistics",
                    "platform": "fred",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"source": "fred_web", "query": query},
                }
        except Exception as exc:
            logger.debug("FREDCollector: web search error: %s", exc)
