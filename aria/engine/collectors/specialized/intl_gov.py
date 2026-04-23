"""International Government collector — UN, EU, national open data portals."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

# EU Open Data Portal API
_EU_DATA = "https://data.europa.eu/api/hub/search/datasets"
# UN Documentation system
_UN_DOCS = "https://undocs.org/api/search"
# UN Statistics
_UNSD_API = "https://unstats.un.org/sdgs/UNSDGAPIV5/v1/sdg/Series/List"


class IntlGovCollector(BaseCollector):
    """Collects from international government portals.

    Sources:
    1. EU Open Data Portal (data.europa.eu)
    2. UN SDG Statistics API
    3. Country-specific gov portals (via web search with site: filters)
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

        # EU Open Data
        for query in queries[:3]:
            if count >= self._max_results:
                break
            async for doc in self._search_eu_data(query, seen_urls):
                if count >= self._max_results:
                    break
                yield doc
                count += 1
            await asyncio.sleep(0.3)

        # Country gov portals via web search
        if self._country_codes and count < self._max_results:
            for query in queries[:2]:
                if count >= self._max_results:
                    break
                async for doc in self._search_country_gov(query, seen_urls):
                    if count >= self._max_results:
                        break
                    yield doc
                    count += 1

        # UN SDG data
        if count < self._max_results:
            async for doc in self._fetch_un_sdg(seen_urls):
                if count >= self._max_results:
                    break
                yield doc
                count += 1

    async def _search_eu_data(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            params = {
                "q": query,
                "limit": 8,
                "facets": "country",
                "minScore": "0.5",
            }
            if self._country_codes:
                # EU portal uses ISO-2 codes
                eu_countries = [c.lower() for c in self._country_codes if c not in ("US", "CN", "IN", "GLOBAL")]
                if eu_countries:
                    params["filter"] = f"country:({' OR '.join(eu_countries[:5])})"

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(_EU_DATA, params=params)
                if resp.status_code != 200:
                    return

                data = resp.json()
                results = data.get("result", {}).get("results", [])

                for item in results:
                    uid = item.get("id", "")
                    url = item.get("landingPage", [""])[0] if item.get("landingPage") else ""
                    if not url:
                        url = f"https://data.europa.eu/data/datasets/{uid}"
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title_obj = item.get("title", {})
                    title = title_obj.get("en", "") or (list(title_obj.values())[0] if title_obj else "")
                    desc_obj = item.get("description", {})
                    desc = desc_obj.get("en", "") or (list(desc_obj.values())[0] if desc_obj else "")

                    publisher = item.get("publisher", {}).get("name", "")
                    country = item.get("country", {}).get("id", "")
                    modified = item.get("modified", "")

                    text_parts = [title]
                    if publisher:
                        text_parts.append(f"Publisher: {publisher}")
                    if country:
                        text_parts.append(f"Country: {country.upper()}")
                    if modified:
                        text_parts.append(f"Modified: {modified[:10]}")
                    if desc:
                        text_parts.append(f"\n{desc[:500]}")

                    text = "\n".join(text_parts).strip()
                    if len(text) < 20:
                        continue

                    yield {
                        "url": url,
                        "title": title,
                        "text": text,
                        "source_type": "gov_policy",
                        "platform": "intl_gov",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "eu_open_data",
                            "country": country,
                            "publisher": publisher,
                            "query": query,
                        },
                    }

        except Exception as exc:
            logger.warning("IntlGovCollector: EU data error for '%s': %s", query, exc)

    async def _search_country_gov(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        from aria.engine.domains.countries import COUNTRIES

        gov_sites = []
        for cc in self._country_codes[:5]:
            cfg = COUNTRIES.get(cc)
            if cfg and cfg.gov_domain:
                gov_sites.append(f"site:{cfg.gov_domain}")
                for extra in cfg.extra_gov_domains[:1]:
                    gov_sites.append(f"site:{extra}")

        if not gov_sites:
            return

        site_filter = " OR ".join(gov_sites[:6])
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            results: list[dict] = []
            with DDGS() as ddgs:
                for r in ddgs.text(f"({site_filter}) {query}", max_results=8):
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
                    "source_type": "gov_policy",
                    "platform": "intl_gov",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"source": "country_gov_search", "query": query},
                }

            await asyncio.sleep(0.4)
        except Exception as exc:
            logger.debug("IntlGovCollector: gov search error: %s", exc)

    async def _fetch_un_sdg(
        self, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            url = "https://unstats.un.org/sdgs/UNSDGAPIV5/v1/sdg/Series/List?pageSize=20"
            if url in seen_urls:
                return
            seen_urls.add(url)

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return

                data = resp.json()
                series_list = data if isinstance(data, list) else data.get("data", [])

                for series in series_list[:5]:
                    code = series.get("code", "")
                    description = series.get("description", "") or ""
                    goal = series.get("goal", {})
                    goal_num = goal.get("goal", "") if isinstance(goal, dict) else ""

                    if not code or not description:
                        continue

                    doc_url = f"https://unstats.un.org/sdgs/report/2023/"
                    text = f"UN SDG Series: {code}\nSDG Goal: {goal_num}\n\n{description}"
                    text = text.strip()

                    yield {
                        "url": doc_url,
                        "title": f"UN SDG Indicator: {code}",
                        "text": text,
                        "source_type": "statistics",
                        "platform": "intl_gov",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {"source": "un_sdg", "series_code": code},
                    }

        except Exception as exc:
            logger.debug("IntlGovCollector: UN SDG error: %s", exc)
