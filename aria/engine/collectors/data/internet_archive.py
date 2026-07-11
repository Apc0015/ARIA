"""Internet Archive collector — archived web pages, books, and documents."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_SEARCH_URL = "https://archive.org/advancedsearch.php"
# Fields to fetch — sent as repeated fl[]=field params
_FIELDS = ["identifier", "title", "description", "date", "mediatype", "creator", "subject"]


class InternetArchiveCollector(BaseCollector):
    """Searches the Internet Archive for texts, documents, and web archives.

    No credentials required.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen: set[str] = set()
        count = 0
        # Use a longer timeout — Archive.org can be slow
        async with httpx.AsyncClient(timeout=30) as client:
            for query in queries[:4]:
                if count >= self._max_results:
                    break
                async for doc in self._search(client, query, seen):
                    yield doc
                    count += 1
                    if count >= self._max_results:
                        break
                await asyncio.sleep(0.5)

    async def _search(
        self,
        client: httpx.AsyncClient,
        query: str,
        seen: set[str],
    ) -> AsyncGenerator[dict[str, Any], None]:
        # Restrict to text-based media only — avoids audio/video/images
        # that have no description and cause low yield
        q = f'({query}) AND mediatype:(texts OR books OR web)'

        # Build params as list of tuples — httpx does NOT expand list values
        # in dict-form params for keys with [] suffix; tuples work correctly.
        params: list[tuple[str, str]] = [
            ("q",        q),
            ("output",   "json"),
            ("rows",     str(min(self._max_results * 5, 50))),  # fetch 5× to survive filtering
            ("sort[]",   "downloads desc"),
        ]
        for field in _FIELDS:
            params.append(("fl[]", field))

        try:
            resp = await client.get(_SEARCH_URL, params=params)
            if resp.status_code != 200:
                logger.warning("InternetArchive: HTTP %d for '%s'", resp.status_code, query)
                return

            docs = resp.json().get("response", {}).get("docs", [])
            logger.debug("InternetArchive: '%s' → %d raw results", query, len(docs))

            for item in docs:
                identifier = item.get("identifier", "")
                if not identifier or identifier in seen:
                    continue
                seen.add(identifier)

                title = item.get("title") or identifier

                description = item.get("description") or ""
                if isinstance(description, list):
                    description = " ".join(description)

                subject = item.get("subject") or ""
                if isinstance(subject, list):
                    subject = ", ".join(subject[:5])

                creator = item.get("creator") or ""
                if isinstance(creator, list):
                    creator = ", ".join(creator[:3])

                mediatype = item.get("mediatype", "")

                # Build text from all available metadata
                parts = [title]
                if description:
                    parts.append(description)
                if subject:
                    parts.append(f"Subject: {subject}")
                if creator:
                    parts.append(f"Creator: {creator}")
                text = "\n\n".join(p.strip() for p in parts if p.strip())

                # Skip items with truly no content
                if len(text) < 10:
                    continue

                source_type = {
                    "web":   "web_archive",
                    "texts": "document",
                    "books": "document",
                }.get(mediatype, "document")

                yield {
                    "url":         f"https://archive.org/details/{identifier}",
                    "title":       title,
                    "text":        text,
                    "source_type": source_type,
                    "platform":    "internet_archive",
                    "language":    "en",
                    "word_count":  len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "identifier": identifier,
                        "mediatype":  mediatype,
                        "date":       str(item.get("date", "")),
                        "creator":    creator,
                        "subject":    subject,
                        "query":      query,
                    },
                }

        except Exception as exc:
            logger.warning("InternetArchive: error for '%s': %s", query, exc)
