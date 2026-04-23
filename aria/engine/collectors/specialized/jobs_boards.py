"""Jobs Boards collector — multi-source job listings aggregator."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

# Adzuna API (free tier: 250 calls/month)
_ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs"

# Country code → Adzuna country slug
_ADZUNA_COUNTRIES = {
    "US": "us", "UK": "gb", "AU": "au", "CA": "ca", "DE": "de",
    "FR": "fr", "IN": "in", "NL": "nl", "NZ": "nz", "PL": "pl",
    "SG": "sg", "ZA": "za", "BR": "br", "MX": "mx",
}


class JobsBoardsCollector(BaseCollector):
    """Collects job listings from multiple job boards.

    Primary: Adzuna API (requires ADZUNA_APP_ID + ADZUNA_APP_KEY env vars)
    Fallback: DuckDuckGo search across major job boards
    """

    def __init__(
        self,
        max_results: int = 30,
        country_codes: list[str] | None = None,
    ) -> None:
        self._max_results = max_results
        self._country_codes = country_codes or ["US"]
        self._adzuna_id = os.getenv("ADZUNA_APP_ID", "")
        self._adzuna_key = os.getenv("ADZUNA_APP_KEY", "")

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen_urls: set[str] = set()
        count = 0

        if self._adzuna_id and self._adzuna_key:
            async for doc in self._collect_adzuna(queries, seen_urls):
                if count >= self._max_results:
                    break
                yield doc
                count += 1

        if count < self._max_results:
            async for doc in self._collect_web_search(queries, seen_urls):
                if count >= self._max_results:
                    break
                yield doc
                count += 1

    async def _collect_adzuna(
        self, queries: list[str], seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        adzuna_slugs = list({
            _ADZUNA_COUNTRIES[cc]
            for cc in self._country_codes
            if cc in _ADZUNA_COUNTRIES
        }) or ["us"]

        for slug in adzuna_slugs[:3]:
            for query in queries[:3]:
                try:
                    params: dict[str, Any] = {
                        "app_id": self._adzuna_id,
                        "app_key": self._adzuna_key,
                        "results_per_page": 10,
                        "what": query,
                        "content-type": "application/json",
                    }
                    url = f"{_ADZUNA_BASE}/{slug}/search/1"
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.get(url, params=params)
                        if resp.status_code != 200:
                            continue

                        data = resp.json()
                        results = data.get("results", [])

                        for job in results:
                            job_url = job.get("redirect_url", "")
                            if not job_url or job_url in seen_urls:
                                continue
                            seen_urls.add(job_url)

                            title = job.get("title", "")
                            company = job.get("company", {}).get("display_name", "")
                            location = job.get("location", {}).get("display_name", "")
                            description = job.get("description", "") or ""
                            salary_min = job.get("salary_min")
                            salary_max = job.get("salary_max")
                            created = job.get("created", "")
                            contract_type = job.get("contract_type", "")
                            category = job.get("category", {}).get("label", "")

                            text_parts = [title]
                            if company:
                                text_parts.append(f"Company: {company}")
                            if location:
                                text_parts.append(f"Location: {location}")
                            if contract_type:
                                text_parts.append(f"Type: {contract_type}")
                            if category:
                                text_parts.append(f"Category: {category}")
                            if salary_min and salary_max:
                                text_parts.append(f"Salary: {salary_min:,.0f}–{salary_max:,.0f}")
                            elif salary_min:
                                text_parts.append(f"Salary from: {salary_min:,.0f}")
                            if created:
                                text_parts.append(f"Posted: {created[:10]}")
                            if description:
                                text_parts.append(f"\n{description[:600]}")

                            text = "\n".join(text_parts).strip()
                            if len(text) < 30:
                                continue

                            yield {
                                "url": job_url,
                                "title": title,
                                "text": text,
                                "source_type": "job_listing",
                                "platform": "jobs_boards",
                                "language": "en",
                                "word_count": len(text.split()),
                                "collected_at": datetime.now(timezone.utc).isoformat(),
                                "metadata": {
                                    "source": f"adzuna_{slug}",
                                    "company": company,
                                    "location": location,
                                    "salary_min": salary_min,
                                    "salary_max": salary_max,
                                    "contract_type": contract_type,
                                    "posted": created[:10] if created else "",
                                    "query": query,
                                },
                            }

                    await asyncio.sleep(0.4)
                except Exception as exc:
                    logger.warning("JobsBoardsCollector: Adzuna error for '%s': %s", query, exc)

    async def _collect_web_search(
        self, queries: list[str], seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        job_sites = [
            "linkedin.com/jobs", "indeed.com", "glassdoor.com",
            "monster.com", "reed.co.uk", "naukri.com", "seek.com.au",
            "jobstreet.com", "bayt.com", "gulftalent.com",
        ]
        # Pick relevant job sites for selected countries
        site_filter = " OR ".join(f"site:{s}" for s in job_sites[:4])

        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            for query in queries[:3]:
                results: list[dict] = []
                search_q = f"({site_filter}) {query} job vacancy hiring"
                with DDGS() as ddgs:
                    for r in ddgs.text(search_q, max_results=8):
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

                    platform = "jobs_boards"
                    for site in job_sites:
                        if site in url:
                            platform = site.split(".")[0]
                            break

                    yield {
                        "url": url,
                        "title": title,
                        "text": text,
                        "source_type": "job_listing",
                        "platform": platform,
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {"source": "jobs_web_search", "query": query},
                    }

                await asyncio.sleep(0.4)

        except Exception as exc:
            logger.warning("JobsBoardsCollector: web search error: %s", exc)
