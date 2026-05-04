"""ProPublica Congress + Nonprofit Explorer collector."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_CONGRESS_URL = "https://api.propublica.org/congress/v1"
_NONPROFIT_URL = "https://projects.propublica.org/nonprofits/api/v2/search.json"


class ProPublicaCollector(BaseCollector):
    """Collects US congressional data and nonprofit records via ProPublica APIs.

    PROPUBLICA_API_KEY env var required for Congress API (free at propublica.org/datastore).
    Nonprofit Explorer works without a key.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results
        self._api_key = os.getenv("PROPUBLICA_API_KEY", "")

    async def validate(self) -> bool:
        return True  # Nonprofit search works without a key

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=20) as client:
            for query in queries[:3]:
                async for doc in self._search_nonprofits(client, query, seen):
                    yield doc
                if self._api_key:
                    async for doc in self._search_congress(client, query, seen):
                        yield doc
                await asyncio.sleep(0.5)

    async def _search_nonprofits(
        self, client: httpx.AsyncClient, query: str, seen: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            resp = await client.get(_NONPROFIT_URL, params={"q": query})
            if resp.status_code != 200:
                return
            for org in (resp.json().get("organizations") or [])[:self._max_results // 2]:
                ein = org.get("ein", "")
                url = f"https://projects.propublica.org/nonprofits/organizations/{ein}"
                if url in seen:
                    continue
                seen.add(url)
                name = org.get("name", "")
                city = org.get("city", "")
                state = org.get("state", "")
                ntee = org.get("ntee_code", "")
                text = f"{name}\nLocation: {city}, {state}\nNTEE: {ntee}"
                yield {
                    "url": url,
                    "title": name,
                    "text": text,
                    "source_type": "gov_policy",
                    "platform": "propublica",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"ein": ein, "city": city, "state": state, "query": query},
                }
        except Exception as exc:
            logger.warning("ProPublica Nonprofit: error for '%s': %s", query, exc)

    async def _search_congress(
        self, client: httpx.AsyncClient, query: str, seen: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        headers = {"X-API-Key": self._api_key}
        try:
            resp = await client.get(
                f"{_CONGRESS_URL}/bills/search.json",
                params={"query": query},
                headers=headers,
            )
            if resp.status_code != 200:
                return
            bills = (resp.json().get("results") or [{}])[0].get("bills") or []
            for bill in bills[:self._max_results // 2]:
                bill_url = bill.get("congressdotgov_url", "")
                if not bill_url or bill_url in seen:
                    continue
                seen.add(bill_url)
                title = bill.get("title", "")
                summary = bill.get("summary", "") or bill.get("short_summary", "")
                text = f"{title}\n\n{summary}".strip()
                if not text:
                    continue
                yield {
                    "url": bill_url,
                    "title": title,
                    "text": text,
                    "source_type": "gov_policy",
                    "platform": "propublica",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "bill_id": bill.get("bill_id", ""),
                        "introduced_date": bill.get("introduced_date", ""),
                        "sponsor": bill.get("sponsor_name", ""),
                        "query": query,
                    },
                }
        except Exception as exc:
            logger.warning("ProPublica Congress: error for '%s': %s", query, exc)
