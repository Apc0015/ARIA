"""Government portal collector — data.gov, regulations.gov, and .gov site search."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from urllib.parse import quote

import httpx

from .base import BaseCollector
from ..utils.camofox import get_client as _camofox

logger = logging.getLogger("aria")

_DATAGOV_SEARCH = "https://catalog.data.gov/api/3/action/package_search"
_REGULATIONSGOV_SEARCH = "https://api.regulations.gov/v4/documents"


class GovernmentCollector(BaseCollector):
    """Collects documents from government portals.

    Sources (in priority order):
    1. data.gov catalog API (no key needed)
    2. regulations.gov API (REGULATIONS_GOV_KEY required)
    3. DuckDuckGo site:.gov fallback (always available)
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results
        self._regulations_key = os.getenv("REGULATIONS_GOV_KEY", "")

    async def validate(self) -> bool:
        # data.gov and DDG fallback always available
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Collect government documents for the given queries.

        Args:
            queries: Research query strings.

        Yields:
            Document dicts with platform='government', source_type='gov_policy'.
        """
        seen_urls: set[str] = set()
        count = 0

        for query in queries:
            if count >= self._max_results:
                break

            # 1. data.gov catalog
            async for doc in self._search_datagov(query, seen_urls):
                if count >= self._max_results:
                    break
                yield doc
                count += 1

            # 2. regulations.gov (if key set)
            if self._regulations_key and count < self._max_results:
                async for doc in self._search_regulations(query, seen_urls):
                    if count >= self._max_results:
                        break
                    yield doc
                    count += 1

            # 3. DuckDuckGo .gov fallback
            if count < self._max_results:
                async for doc in self._search_gov_duckduckgo(query, seen_urls):
                    if count >= self._max_results:
                        break
                    yield doc
                    count += 1

    async def _search_datagov(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Search data.gov catalog API."""
        try:
            params = {"q": query, "rows": 10, "sort": "score desc, metadata_modified desc"}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(_DATAGOV_SEARCH, params=params)
                if resp.status_code != 200:
                    logger.debug("GovernmentCollector: data.gov HTTP %s", resp.status_code)
                    return

                data = resp.json()
                results = data.get("result", {}).get("results", [])

                for item in results:
                    name = item.get("name", "")
                    title = item.get("title", "")
                    notes = item.get("notes", "")
                    organization = item.get("organization", {}).get("title", "")
                    url = f"https://catalog.data.gov/dataset/{name}" if name else ""
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    resources = item.get("resources", [])
                    resource_info = ", ".join(
                        r.get("format", "") for r in resources[:3] if r.get("format")
                    )

                    text = f"{title}\n\nOrganization: {organization}\n\n{notes}"
                    if resource_info:
                        text += f"\n\nAvailable formats: {resource_info}"
                    text = text.strip()
                    if len(text) < 20:
                        continue

                    tags = [t.get("name", "") for t in item.get("tags", [])[:10]]

                    yield {
                        "url": url,
                        "title": title or name,
                        "text": text,
                        "source_type": "gov_policy",
                        "platform": "government",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "data.gov",
                            "organization": organization,
                            "tags": tags,
                            "query": query,
                        },
                    }

            await asyncio.sleep(0.3)

        except Exception as exc:
            logger.warning("GovernmentCollector: data.gov error for '%s': %s", query, exc)

    async def _search_regulations(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Search regulations.gov API (requires REGULATIONS_GOV_KEY)."""
        try:
            params = {
                "filter[searchTerm]": query,
                "api_key": self._regulations_key,
                "page[size]": 10,
                "sort": "relevance",
            }
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(_REGULATIONSGOV_SEARCH, params=params)
                if resp.status_code == 403:
                    logger.warning(
                        "GovernmentCollector: regulations.gov API key invalid (403)"
                    )
                    return
                if resp.status_code != 200:
                    logger.debug(
                        "GovernmentCollector: regulations.gov HTTP %s", resp.status_code
                    )
                    return

                data = resp.json()
                items = data.get("data", [])

                for item in items:
                    attrs = item.get("attributes", {})
                    doc_id = item.get("id", "")
                    url = f"https://www.regulations.gov/document/{doc_id}" if doc_id else ""
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = attrs.get("title", "")
                    summary = attrs.get("summary", "") or attrs.get("comment", "") or ""
                    agency = attrs.get("agencyId", "")
                    doc_type = attrs.get("documentType", "")
                    posted_date = attrs.get("postedDate", "")

                    text = f"{title}\n\nAgency: {agency}\nType: {doc_type}\nPosted: {posted_date}\n\n{summary}"
                    text = text.strip()
                    if len(text) < 20:
                        continue

                    yield {
                        "url": url,
                        "title": title,
                        "text": text,
                        "source_type": "gov_policy",
                        "platform": "government",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "regulations.gov",
                            "agency": agency,
                            "document_type": doc_type,
                            "query": query,
                        },
                    }

            await asyncio.sleep(0.3)

        except Exception as exc:
            logger.warning(
                "GovernmentCollector: regulations.gov error for '%s': %s", query, exc
            )

    async def _search_gov_duckduckgo(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Search .gov sites — Camofox Google search preferred, DDG fallback."""
        camofox = _camofox()

        if camofox.available:
            async for doc in self._search_gov_camofox(query, seen_urls, camofox):
                yield doc
            return

        # Plain DDG fallback
        try:
            search_query = f"site:.gov {query}"
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            results: list[dict] = []
            with DDGS() as ddgs:
                for r in ddgs.text(search_query, max_results=8):
                    results.append(r)

            for result in results:
                url = result.get("href", "")
                if not url or ".gov" not in url:
                    continue
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                title = result.get("title", "")
                body = result.get("body", "")
                text = f"{title}\n\n{body}".strip()
                if len(text) < 30:
                    continue

                yield {
                    "url": url,
                    "title": title,
                    "text": text,
                    "source_type": "gov_policy",
                    "platform": "government",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"source": "duckduckgo_gov", "query": query},
                }

            await asyncio.sleep(0.3)

        except Exception as exc:
            logger.warning(
                "GovernmentCollector: DDG .gov search error for '%s': %s", query, exc
            )

    async def _search_gov_camofox(
        self, query: str, seen_urls: set[str], camofox: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Search .gov via Camofox Google search — bypasses JS rendering issues."""
        try:
            links = await camofox.search(f"site:.gov {query}", engine="google")
            for link in links:
                url  = link.get("href", "")
                text = link.get("text", "")
                if not url or ".gov" not in url or url in seen_urls:
                    continue
                seen_urls.add(url)
                if len(text) < 15:
                    continue

                # Fetch full page for JS-rendered .gov sites
                try:
                    page = await camofox.fetch_page(url, wait_seconds=3.0)
                    full_text = page.get("text", "") or text
                    title = page.get("title", "") or text[:120]
                except Exception:
                    full_text = text
                    title = text[:120]

                yield {
                    "url": url,
                    "title": title,
                    "text": full_text,
                    "source_type": "gov_policy",
                    "platform": "government",
                    "language": "en",
                    "word_count": len(full_text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"source": "camofox_gov_search", "query": query},
                }

        except Exception as exc:
            logger.warning("GovernmentCollector: Camofox error for '%s': %s", query, exc)
