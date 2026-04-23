"""SEC EDGAR collector — company filings, 10-K, 10-Q, 8-K, prospectuses."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
_EDGAR_FULL = "https://efts.sec.gov/LATEST/search-index"
_EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions"


class SECEdgarCollector(BaseCollector):
    """Collects financial disclosures from SEC EDGAR.

    Free, no API key required.
    Returns 10-K, 10-Q, 8-K filings, proxy statements, etc.
    """

    # Filing types of highest research value
    _FILING_TYPES = ["10-K", "10-Q", "8-K", "DEF 14A", "S-1"]

    def __init__(
        self,
        max_results: int = 20,
        filing_types: list[str] | None = None,
    ) -> None:
        self._max_results = max_results
        self._filing_types = filing_types or ["10-K", "10-Q", "8-K"]
        self._headers = {
            "User-Agent": "ARIA Research Tool aria@research.tool",
            "Accept-Encoding": "gzip, deflate",
        }

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen_ids: set[str] = set()
        count = 0

        for query in queries[:4]:
            if count >= self._max_results:
                break
            async for doc in self._search_filings(query, seen_ids):
                if count >= self._max_results:
                    break
                yield doc
                count += 1
            await asyncio.sleep(0.5)

    async def _search_filings(
        self, query: str, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            # EDGAR full-text search
            params: dict[str, Any] = {
                "q": f'"{query}"',
                "dateRange": "custom",
                "startdt": "2020-01-01",
                "enddt": datetime.now().strftime("%Y-%m-%d"),
                "forms": ",".join(self._filing_types[:3]),
            }
            search_url = "https://efts.sec.gov/LATEST/search-index?q=" + params["q"]

            # Use the public EDGAR full-text search
            api_url = "https://efts.sec.gov/LATEST/search-index"
            async with httpx.AsyncClient(
                timeout=20, headers=self._headers
            ) as client:
                resp = await client.get(
                    "https://efts.sec.gov/LATEST/search-index",
                    params={
                        "q": query,
                        "dateRange": "custom",
                        "startdt": "2022-01-01",
                        "forms": ",".join(self._filing_types[:2]),
                        "hits.hits.total.value": "true",
                    },
                )
                if resp.status_code != 200:
                    # Fallback to EDGAR EFTS search
                    async for doc in self._search_edgar_efts(query, seen_ids):
                        yield doc
                    return

                data = resp.json()
                hits = data.get("hits", {}).get("hits", [])

                for hit in hits[:8]:
                    src = hit.get("_source", {})
                    filing_id = hit.get("_id", "")
                    if filing_id in seen_ids:
                        continue
                    seen_ids.add(filing_id)

                    entity = src.get("entity_name", "") or src.get("display_names", [""])[0]
                    form_type = src.get("form_type", "")
                    filed_at = src.get("file_date", "")
                    period = src.get("period_of_report", "")
                    description = src.get("file_description", "")

                    accession = src.get("accession_no", "").replace("-", "")
                    cik = src.get("entity_id", "")
                    if accession and cik:
                        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}.txt"
                    else:
                        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={query}&type={form_type}"

                    if url in seen_ids:
                        continue

                    text_parts = [f"{entity} — {form_type} Filing"]
                    if period:
                        text_parts.append(f"Period: {period}")
                    if filed_at:
                        text_parts.append(f"Filed: {filed_at}")
                    if description:
                        text_parts.append(f"Description: {description}")
                    text_parts.append(f"\nFiling URL: {url}")

                    text = "\n".join(text_parts).strip()
                    if len(text) < 30:
                        continue

                    yield {
                        "url": url,
                        "title": f"{entity} {form_type} ({filed_at[:7] if filed_at else ''})",
                        "text": text,
                        "source_type": "filing",
                        "platform": "sec_edgar",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "sec_edgar",
                            "entity": entity,
                            "form_type": form_type,
                            "filed_at": filed_at,
                            "period": period,
                            "query": query,
                        },
                    }

        except Exception as exc:
            logger.warning("SECEdgarCollector: search error for '%s': %s", query, exc)

    async def _search_edgar_efts(
        self, query: str, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """EDGAR full-text search via the EFTS endpoint."""
        try:
            async with httpx.AsyncClient(
                timeout=20, headers=self._headers
            ) as client:
                resp = await client.get(
                    "https://efts.sec.gov/LATEST/search-index",
                    params={"q": query, "forms": "10-K,10-Q"},
                )
                if resp.status_code != 200:
                    return
                data = resp.json()
                for hit in data.get("hits", {}).get("hits", [])[:5]:
                    src = hit.get("_source", {})
                    filing_id = hit.get("_id", "")
                    if filing_id in seen_ids:
                        continue
                    seen_ids.add(filing_id)

                    entity = src.get("entity_name", "") or ""
                    form = src.get("form_type", "")
                    filed = src.get("file_date", "")
                    url = src.get("file_date", "")

                    text = f"{entity} — {form}\nFiled: {filed}\nQuery: {query}".strip()
                    if len(text) < 20:
                        continue

                    yield {
                        "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={entity}&type={form}",
                        "title": f"{entity} {form}",
                        "text": text,
                        "source_type": "filing",
                        "platform": "sec_edgar",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {"source": "sec_edgar_efts", "query": query},
                    }
        except Exception as exc:
            logger.debug("SECEdgarCollector: EFTS error: %s", exc)
