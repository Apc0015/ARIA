"""SSRN collector — preprints via DuckDuckGo site search + BeautifulSoup."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx
from bs4 import BeautifulSoup

from .base import BaseCollector

logger = logging.getLogger("aria")

_DDG_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


class SSRNCollector(BaseCollector):
    """Collects SSRN preprints via DuckDuckGo site:ssrn.com search."""

    def __init__(self, max_results: int = 10) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen: set[str] = set()
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            for query in queries[:3]:
                # Step 1: DuckDuckGo site:ssrn.com search
                try:
                    resp = await client.post(_DDG_URL, data={"q": f"site:ssrn.com {query}"})
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    result_links = [
                        a["href"]
                        for a in soup.select("a.result__a")
                        if a.get("href") and "ssrn.com/abstract=" in a["href"]
                    ][:self._max_results]
                except Exception as exc:
                    logger.debug("SSRN DDG search failed for '%s': %s", query, exc)
                    continue

                # Step 2: Scrape each SSRN abstract page
                for url in result_links:
                    if url in seen:
                        continue
                    seen.add(url)
                    try:
                        page_resp = await client.get(url)
                        if page_resp.status_code != 200:
                            continue
                        page_soup = BeautifulSoup(page_resp.text, "html.parser")

                        title_el = page_soup.select_one("h1.title, .paper-title")
                        title = title_el.get_text(strip=True) if title_el else ""

                        abstract_el = page_soup.select_one(".abstract-text, #abstract")
                        abstract = abstract_el.get_text(strip=True) if abstract_el else ""

                        authors_el = page_soup.select_one(".authors")
                        authors = authors_el.get_text(strip=True) if authors_el else ""

                        date_el = page_soup.select_one(".paper-date, .date")
                        date = date_el.get_text(strip=True) if date_el else ""

                        text = f"{title}\n\n{abstract}".strip()
                        if not text:
                            continue

                        yield {
                            "url": url,
                            "title": title,
                            "text": text,
                            "source_type": "academic_paper",
                            "platform": "ssrn",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {"authors": authors, "date": date, "query": query},
                        }
                        await asyncio.sleep(1.0)
                    except Exception as exc:
                        logger.debug("SSRN page scrape failed for %s: %s", url, exc)
