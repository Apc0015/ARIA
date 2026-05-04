"""Mastodon collector — three-tier strategy for public post collection.

Part A: Hashtag public timelines (no auth, works on most instances).
Part B: Token-based v2 search on mastodon.social (MASTODON_ACCESS_TOKEN).
Part C: DuckDuckGo site:mastodon.social fallback when both above return nothing.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_SEARCH_URL = "https://mastodon.social/api/v2/search"

# Public instances to try for unauthenticated hashtag timelines (in order).
# Each allows public access to /api/v1/timelines/tag/{hashtag}.
_HASHTAG_INSTANCES = [
    "https://fosstodon.org",
    "https://mas.to",
    "https://scholar.social",
    "https://mastodon.social",
]


def _strip_html(text: str) -> str:
    """Remove HTML tags and normalise whitespace."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _query_to_hashtags(query: str) -> list[str]:
    """Derive hashtag candidates from a search query string.

    Strategy:
    - Lowercase, split on spaces.
    - Take words > 4 chars (skip stop words / noise).
    - Also produce a single concatenated hashtag for multi-word topics
      (e.g. "machine learning" → "machinelearning").

    Returns a deduplicated list, concatenated form first.
    """
    words = [w for w in query.lower().split() if len(w) > 4 and w.isalpha()]
    tags: list[str] = []
    if len(words) >= 2:
        tags.append("".join(words))   # "machinelearning"
    tags.extend(words)
    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _status_to_doc(status: dict, query: str) -> dict | None:
    """Convert a Mastodon status object to an ARIA document dict.

    Returns None if the content is too short to be useful.
    """
    url = status.get("url", "")
    if not url:
        return None

    content = _strip_html(status.get("content", ""))
    if not content or len(content.split()) <= 20:
        return None

    account = status.get("account", {})
    author = account.get("acct", "") or account.get("username", "")

    return {
        "url": url,
        "title": f"@{author}: {content[:80]}",
        "text": content,
        "source_type": "social_media",
        "platform": "mastodon",
        "language": "en",
        "word_count": len(content.split()),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "author": author,
            "created_at": status.get("created_at", ""),
            "favourites_count": status.get("favourites_count", 0),
            "reblogs_count": status.get("reblogs_count", 0),
            "query": query,
        },
    }


class MastodonCollector(BaseCollector):
    """Collects Mastodon posts using a three-tier fallback strategy.

    Part A (always): public hashtag timelines — no credentials required.
    Part B (optional): token-based v2 search when MASTODON_ACCESS_TOKEN is set.
    Part C (fallback): DuckDuckGo site:mastodon.social when A+B both return nothing.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results
        self._token = os.getenv("MASTODON_ACCESS_TOKEN", "")

    async def validate(self) -> bool:
        # Always valid — Part A works without credentials.
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        seen: set[str] = set()
        yielded = 0

        async with httpx.AsyncClient(
            timeout=15,
            headers={"Accept": "application/json"},
        ) as client:
            for query in queries[:4]:
                if yielded >= self._max_results:
                    break

                # ── Part A: hashtag public timelines ──────────────────────────
                part_a_docs, part_a_got_response = await self._collect_hashtag_timelines(
                    client, query, seen
                )
                for doc in part_a_docs:
                    if yielded >= self._max_results:
                        break
                    yield doc
                    yielded += 1

                if yielded >= self._max_results:
                    break

                # ── Part B: token-based search ────────────────────────────────
                if self._token and not part_a_docs:
                    async for doc in self._collect_token_search(client, query, seen):
                        if yielded >= self._max_results:
                            break
                        yield doc
                        yielded += 1

                # ── Part C: DDG fallback ──────────────────────────────────────
                # Only fire if Part A got no HTTP 200 at all (not just filtered results).
                if yielded == 0 and not part_a_got_response:
                    async for doc in self._collect_ddg_fallback(query, seen):
                        if yielded >= self._max_results:
                            break
                        yield doc
                        yielded += 1

                await asyncio.sleep(0.5)

    # ------------------------------------------------------------------
    # Part A — Hashtag public timelines
    # ------------------------------------------------------------------

    async def _collect_hashtag_timelines(
        self,
        client: httpx.AsyncClient,
        query: str,
        seen: set[str],
    ) -> tuple[list[dict], bool]:
        """Try hashtag timelines across multiple public Mastodon instances.

        Returns (docs, got_http_response) where got_http_response is True if
        at least one instance returned HTTP 200 (even if all posts were filtered).
        This lets the caller suppress the DDG fallback when Part A was reachable.
        """
        hashtags = _query_to_hashtags(query)
        if not hashtags:
            return [], False

        results: list[dict] = []
        got_response = False
        for hashtag in hashtags[:3]:  # cap hashtag attempts per query
            for instance in _HASHTAG_INSTANCES:
                url = f"{instance}/api/v1/timelines/tag/{hashtag}?limit=10"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    statuses = resp.json()
                    if not isinstance(statuses, list):
                        continue
                    if statuses:
                        got_response = True  # instance returned actual posts
                    for status in statuses:
                        doc = _status_to_doc(status, query)
                        if doc and doc["url"] not in seen:
                            seen.add(doc["url"])
                            results.append(doc)
                    if results:
                        return results, got_response  # got usable docs — stop
                    await asyncio.sleep(0.2)
                except Exception as exc:
                    logger.debug("Mastodon hashtag timeline %s/%s: %s", instance, hashtag, exc)

        return results, got_response

    # ------------------------------------------------------------------
    # Part B — Token-based v2 search
    # ------------------------------------------------------------------

    async def _collect_token_search(
        self,
        client: httpx.AsyncClient,
        query: str,
        seen: set[str],
    ) -> AsyncGenerator[dict, None]:
        """Use mastodon.social v2 search with bearer token."""
        headers = {"Authorization": f"Bearer {self._token}"}
        params = {
            "q": query,
            "type": "statuses",
            "limit": min(self._max_results, 20),
            "resolve": "false",
        }
        try:
            resp = await client.get(_SEARCH_URL, headers=headers, params=params)
            if resp.status_code == 401:
                logger.warning("MastodonCollector: token rejected (401)")
                return
            if resp.status_code != 200:
                logger.debug("Mastodon token search: HTTP %s for '%s'", resp.status_code, query)
                return
            for status in resp.json().get("statuses", []):
                doc = _status_to_doc(status, query)
                if doc and doc["url"] not in seen:
                    seen.add(doc["url"])
                    yield doc
        except Exception as exc:
            logger.warning("Mastodon token search error for '%s': %s", query, exc)

    # ------------------------------------------------------------------
    # Part C — DuckDuckGo site:mastodon.social fallback
    # ------------------------------------------------------------------

    async def _collect_ddg_fallback(
        self,
        query: str,
        seen: set[str],
    ) -> AsyncGenerator[dict, None]:
        """Yield stub docs from DuckDuckGo results for mastodon.social."""
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            ddg_query = f"{query} site:mastodon.social"

            def _search() -> list:
                with DDGS() as ddgs:
                    return list(ddgs.text(ddg_query, max_results=8))

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, _search)

            for result in results:
                url = result.get("href", "") or result.get("url", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                snippet = result.get("body", "") or result.get("snippet", "")
                if not snippet or len(snippet.split()) <= 5:
                    continue
                title = result.get("title", url)
                yield {
                    "url": url,
                    "title": title,
                    "text": snippet,
                    "source_type": "social_media",
                    "platform": "mastodon",
                    "language": "en",
                    "word_count": len(snippet.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "author": "",
                        "created_at": "",
                        "favourites_count": 0,
                        "reblogs_count": 0,
                        "query": query,
                        "via": "ddg_fallback",
                    },
                }
        except Exception as exc:
            logger.debug("Mastodon DDG fallback error for '%s': %s", query, exc)
