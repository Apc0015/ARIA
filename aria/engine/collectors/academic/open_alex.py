"""OpenAlex collector — 250M+ academic works, free open API."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from urllib.parse import quote

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_OPENALEX_BASE = "https://api.openalex.org"


class OpenAlexCollector(BaseCollector):
    """Collects academic works from OpenAlex (250M+ papers, books, datasets).

    Uses the polite pool by sending User-Agent with email.
    No API key needed.
    """

    def __init__(
        self,
        max_results: int = 20,
        email: str = "aria@research.tool",
    ) -> None:
        self._max_results = max_results
        self._email = email
        self._headers = {
            "User-Agent": f"ARIA-Research/5.0 (mailto:{email})",
            "Accept": "application/json",
        }

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen_ids: set[str] = set()
        count = 0

        for query in queries:
            if count >= self._max_results:
                break
            async for doc in self._search_works(query, seen_ids):
                if count >= self._max_results:
                    break
                yield doc
                count += 1
            await asyncio.sleep(0.5)

    async def _search_works(
        self, query: str, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            params = {
                "search": query,
                "per-page": min(10, self._max_results),
                "select": "id,title,abstract_inverted_index,publication_year,doi,type,cited_by_count,authorships,primary_location,open_access,topics",
                "sort": "relevance_score:desc",
                "filter": "is_paratext:false",
            }
            async with httpx.AsyncClient(timeout=20, headers=self._headers) as client:
                resp = await client.get(f"{_OPENALEX_BASE}/works", params=params)
                if resp.status_code == 429:
                    logger.debug("OpenAlex: rate limited, sleeping 2s")
                    await asyncio.sleep(2)
                    return
                if resp.status_code != 200:
                    logger.debug("OpenAlex: HTTP %s for query '%s'", resp.status_code, query)
                    return

                data = resp.json()
                results = data.get("results", [])

                for work in results:
                    work_id = work.get("id", "")
                    if work_id in seen_ids:
                        continue
                    seen_ids.add(work_id)

                    title = work.get("title", "") or ""
                    if not title:
                        continue

                    doi = work.get("doi", "") or ""
                    url = doi if doi else work_id
                    if not url:
                        continue

                    year = work.get("publication_year", "")
                    cited = work.get("cited_by_count", 0)
                    work_type = work.get("type", "article")

                    # Reconstruct abstract from inverted index
                    abstract = _reconstruct_abstract(
                        work.get("abstract_inverted_index")
                    )

                    # Authors
                    authorships = work.get("authorships", [])[:5]
                    authors = ", ".join(
                        a.get("author", {}).get("display_name", "")
                        for a in authorships
                        if a.get("author")
                    )

                    # Topics
                    topics = work.get("topics", [])[:3]
                    topic_names = ", ".join(t.get("display_name", "") for t in topics)

                    # Location
                    loc = work.get("primary_location", {}) or {}
                    source = loc.get("source", {}) or {}
                    venue = source.get("display_name", "") or ""

                    text_parts = [title]
                    if authors:
                        text_parts.append(f"Authors: {authors}")
                    if venue:
                        text_parts.append(f"Published in: {venue}")
                    if year:
                        text_parts.append(f"Year: {year}")
                    if cited:
                        text_parts.append(f"Citations: {cited}")
                    if topic_names:
                        text_parts.append(f"Topics: {topic_names}")
                    if abstract:
                        text_parts.append(f"\n{abstract}")

                    text = "\n".join(text_parts).strip()
                    if len(text) < 30:
                        continue

                    oa = work.get("open_access", {}) or {}
                    oa_url = oa.get("oa_url", "")
                    final_url = oa_url or url

                    yield {
                        "url": final_url,
                        "title": title,
                        "text": text,
                        "source_type": "academic_paper",
                        "platform": "open_alex",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "open_alex",
                            "doi": doi,
                            "year": year,
                            "cited_by_count": cited,
                            "work_type": work_type,
                            "open_access": oa.get("is_oa", False),
                            "query": query,
                        },
                    }

        except Exception as exc:
            logger.warning("OpenAlexCollector: error for '%s': %s", query, exc)


def _reconstruct_abstract(inverted_index: dict | None) -> str:
    if not inverted_index:
        return ""
    try:
        max_pos = max(pos for positions in inverted_index.values() for pos in positions)
        words = [""] * (max_pos + 1)
        for word, positions in inverted_index.items():
            for pos in positions:
                words[pos] = word
        return " ".join(w for w in words if w)
    except Exception:
        return ""
