"""Wikidata entity collector — structured knowledge for the knowledge graph."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_API = "https://www.wikidata.org/w/api.php"
_HEADERS = {"User-Agent": "ARIA-Research-Bot/5.0 (https://github.com/aria-research; research@aria.local)"}

# Stop words to strip before extracting key terms from a query
_STOP = frozenset({
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for",
    "is", "are", "was", "were", "be", "been", "with", "by", "from",
    "about", "how", "what", "why", "when", "where", "which", "who",
    "latest", "recent", "new", "best", "top", "key", "major",
    "2020", "2021", "2022", "2023", "2024", "2025",
})


def _key_terms(query: str) -> list[str]:
    """Extract meaningful search terms from an arbitrary query phrase.

    Returns the original phrase first, then individual bigrams and
    unigrams — so any topic yields at least a few entity candidates.
    """
    terms: list[str] = [query]  # always try full phrase first

    words = [w for w in re.split(r"\W+", query.lower()) if w and w not in _STOP]

    # Bigrams (adjacent pairs)
    for i in range(len(words) - 1):
        terms.append(f"{words[i]} {words[i+1]}")

    # Unigrams (individual meaningful words, length ≥ 4)
    for w in words:
        if len(w) >= 4:
            terms.append(w)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


class WikidataCollector(BaseCollector):
    """Fetches Wikidata entity descriptions for any keyword topic.

    Strategy:
      1. wbsearchentities on the full query phrase
      2. wbsearchentities on extracted key terms (bigrams then unigrams)
      3. MediaWiki fulltext search fallback for topics with no named entity

    No credentials required.
    """

    def __init__(self, max_results: int = 15) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen: set[str] = set()
        count = 0
        async with httpx.AsyncClient(timeout=20, headers=_HEADERS) as client:
            for query in queries[:5]:
                if count >= self._max_results:
                    break
                async for doc in self._collect_query(client, query, seen):
                    yield doc
                    count += 1
                    if count >= self._max_results:
                        break
                await asyncio.sleep(0.4)

    async def _collect_query(
        self, client: httpx.AsyncClient, query: str, seen: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Try entity search then fulltext fallback for one query."""
        found = 0
        target = max(3, self._max_results // 3)

        # ── Strategy 1: entity search on key terms ───────────────────────────
        for term in _key_terms(query):
            if found >= target:
                break
            try:
                resp = await client.get(_API, params={
                    "action":   "wbsearchentities",
                    "search":   term,
                    "language": "en",
                    "format":   "json",
                    "limit":    10,
                    "type":     "item",
                })
                if resp.status_code != 200:
                    continue
                for entity in resp.json().get("search", []):
                    entity_id = entity.get("id", "")
                    url = f"https://www.wikidata.org/wiki/{entity_id}"
                    if not entity_id or url in seen:
                        continue
                    description = entity.get("description", "")
                    if not description:
                        continue
                    seen.add(url)
                    label   = entity.get("label", entity_id)
                    aliases = entity.get("aliases", [])
                    text    = f"{label}\n\n{description}"
                    if aliases:
                        text += f"\n\nAlso known as: {', '.join(aliases[:5])}"

                    yield _make_doc(url, label, text, entity_id, aliases, description, query)
                    found += 1
                    if found >= target:
                        break
                await asyncio.sleep(0.2)
            except Exception as exc:
                logger.debug("Wikidata entity search '%s': %s", term, exc)

        # ── Strategy 2: MediaWiki fulltext search (works for any phrase) ──────
        if found < target:
            try:
                resp = await client.get(_API, params={
                    "action":   "query",
                    "list":     "search",
                    "srsearch": query,
                    "srwhat":   "text",
                    "srlimit":  min(10, target * 2),
                    "format":   "json",
                })
                if resp.status_code == 200:
                    for item in resp.json().get("query", {}).get("search", []):
                        if found >= target:
                            break
                        title     = item.get("title", "")
                        snippet   = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
                        page_id   = item.get("pageid", "")
                        url       = f"https://www.wikidata.org/?search={title.replace(' ', '+')}"
                        if url in seen or not snippet:
                            continue
                        seen.add(url)
                        text = f"{title}\n\n{snippet}"

                        yield _make_doc(
                            url=url, label=title, text=text,
                            entity_id=str(page_id), aliases=[],
                            description=snippet, query=query,
                        )
                        found += 1
            except Exception as exc:
                logger.debug("Wikidata fulltext search '%s': %s", query, exc)

        logger.debug("Wikidata: '%s' → %d entities", query, found)


def _make_doc(
    url: str,
    label: str,
    text: str,
    entity_id: str,
    aliases: list[str],
    description: str,
    query: str,
) -> dict[str, Any]:
    return {
        "url":          url,
        "title":        label,
        "text":         text,
        "source_type":  "knowledge_base",
        "platform":     "wikidata",
        "language":     "en",
        "word_count":   len(text.split()),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "entity_id":   entity_id,
            "description": description,
            "aliases":     aliases[:10],
            "query":       query,
        },
    }
