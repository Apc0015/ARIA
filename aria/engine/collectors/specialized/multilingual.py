"""Multilingual collector — searches across language regions via DuckDuckGo."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

from .base import BaseCollector

logger = logging.getLogger("aria")

DDGS: Any | None = None


def _ddgs_client() -> Any:
    """Return a DDG search client, allowing tests to patch module-level DDGS."""
    global DDGS
    if DDGS is None:
        try:
            from ddgs import DDGS as ddgs_cls
        except ImportError:
            from duckduckgo_search import DDGS as ddgs_cls
        DDGS = ddgs_cls

    if isinstance(DDGS, type) or not hasattr(DDGS, "__enter__"):
        return DDGS()
    return DDGS


# DuckDuckGo region codes → language label
_REGION_LANG_MAP: dict[str, str] = {
    "de-de": "de",
    "fr-fr": "fr",
    "es-es": "es",
    "zh-cn": "zh",
    "ja-jp": "ja",
    "pt-br": "pt",
    "ar-xa": "ar",
    "ru-ru": "ru",
    "it-it": "it",
    "ko-kr": "ko",
    "nl-nl": "nl",
    "pl-pl": "pl",
}

# Default regions if MULTILINGUAL_REGIONS not set
_DEFAULT_REGIONS = ["de-de", "fr-fr", "es-es", "zh-cn"]


def _parse_regions() -> list[str]:
    """Read and validate region list from env var."""
    env_val = os.getenv("MULTILINGUAL_REGIONS", "")
    if not env_val.strip():
        return _DEFAULT_REGIONS
    regions = [r.strip().lower() for r in env_val.split(",") if r.strip()]
    valid = [r for r in regions if r in _REGION_LANG_MAP]
    if not valid:
        logger.warning(
            "MultilingualCollector: no valid regions in "
            "MULTILINGUAL_REGIONS='%s', using defaults",
            env_val,
        )
        return _DEFAULT_REGIONS
    return valid


class MultilingualCollector(BaseCollector):
    """Collects web content from non-English language regions.

    Uses DuckDuckGo region-specific search (no translation of queries needed —
    DDG localizes results automatically for each region code).

    Configurable via MULTILINGUAL_REGIONS env var (comma-separated region codes).
    Supported regions: de-de, fr-fr, es-es, zh-cn, ja-jp, pt-br, ar-xa, ru-ru,
                       it-it, ko-kr, nl-nl, pl-pl

    Documents are yielded with their original language; the downstream LLM
    cleaning agent handles relevance scoring and can extract an English summary.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results
        self._regions = _parse_regions()

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Search each configured region for each query.

        Args:
            queries: Research query strings (used as-is — DDG localizes results).

        Yields:
            Document dicts with language field set from region, platform='multilingual'.
        """
        seen_urls: set[str] = set()
        count = 0
        # Distribute budget across regions
        per_region = max(2, self._max_results // len(self._regions))

        for region in self._regions:
            if count >= self._max_results:
                break

            lang = _REGION_LANG_MAP.get(region, "unknown")
            region_count = 0

            for query in queries[:3]:  # limit queries per region to avoid rate limits
                if count >= self._max_results or region_count >= per_region:
                    break

                try:
                    results: list[dict] = []
                    with _ddgs_client() as ddgs:
                        for r in ddgs.text(
                            query,
                            region=region,
                            safesearch="moderate",
                            max_results=min(5, per_region - region_count),
                        ):
                            results.append(r)

                    for result in results:
                        if count >= self._max_results or region_count >= per_region:
                            break

                        url = result.get("href", "")
                        if not url or url in seen_urls:
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
                            "source_type": "web_page",
                            "platform": "multilingual",
                            "language": lang,
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "region": region,
                                "query": query,
                            },
                        }
                        count += 1
                        region_count += 1

                    await asyncio.sleep(0.5)  # respect DDG rate limits

                except Exception as exc:
                    logger.warning(
                        "MultilingualCollector: region=%s query='%s' error: %s",
                        region,
                        query,
                        exc,
                    )
