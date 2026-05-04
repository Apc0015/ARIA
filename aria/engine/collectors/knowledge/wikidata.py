"""Wikidata entity collector — structured knowledge for the knowledge graph."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_SEARCH_URL = "https://www.wikidata.org/w/api.php"


class WikidataCollector(BaseCollector):
    """Fetches Wikidata entity descriptions and aliases.

    No credentials required. Feeds structured entities into the knowledge graph.
    """

    def __init__(self, max_results: int = 15) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen: set[str] = set()
        headers = {"User-Agent": "ARIA-Research-Bot/5.0 (https://github.com/aria-research; research@aria.local)"}
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            for query in queries[:5]:
                params = {
                    "action": "wbsearchentities",
                    "search": query,
                    "language": "en",
                    "format": "json",
                    "limit": min(self._max_results, 20),
                    "type": "item",
                }
                try:
                    resp = await client.get(_SEARCH_URL, params=params)
                    if resp.status_code != 200:
                        continue
                    for entity in resp.json().get("search", []):
                        entity_id = entity.get("id", "")
                        url = f"https://www.wikidata.org/wiki/{entity_id}"
                        if not entity_id or url in seen:
                            continue
                        seen.add(url)

                        label = entity.get("label", "")
                        description = entity.get("description", "")
                        if not description:
                            continue  # skip stub entities

                        aliases = entity.get("aliases", [])
                        text = f"{label}\n\n{description}"
                        if aliases:
                            text += f"\n\nAliases: {', '.join(aliases[:5])}"

                        yield {
                            "url": url,
                            "title": label,
                            "text": text,
                            "source_type": "knowledge_base",
                            "platform": "wikidata",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "entity_id": entity_id,
                                "description": description,
                                "aliases": aliases[:10],
                                "query": query,
                            },
                        }
                    await asyncio.sleep(0.5)
                except Exception as exc:
                    logger.warning("Wikidata: error for '%s': %s", query, exc)
