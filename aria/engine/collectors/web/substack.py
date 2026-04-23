"""Substack collector — reads RSS feeds from known/user-provided Substack newsletters."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

from .base import BaseCollector

logger = logging.getLogger("aria")

# Default well-known tech/research Substack newsletters
_DEFAULT_FEEDS = [
    "https://www.oneusefulthing.org/feed",
    "https://stratechery.com/feed/",
    "https://www.ben-evans.com/benedictevans?format=rss",
    "https://interconnected.org/home/feed",
    "https://simonwillison.net/atom/everything/",
    "https://thezvi.substack.com/feed",
    "https://astralcodexten.substack.com/feed",
    "https://www.lesswrong.com/feed.xml",
    "https://diffusiondigest.beehiiv.com/feed",
    "https://newsletter.pragmaticengineer.com/feed",
]


class SubstackCollector(BaseCollector):
    """Collects posts from Substack newsletters via RSS feeds."""

    def __init__(
        self,
        feed_urls: list[str] | None = None,
        max_results: int = 20,
    ) -> None:
        self._feed_urls = feed_urls if feed_urls is not None else _DEFAULT_FEEDS
        self._max_results = max_results

    async def validate(self) -> bool:
        try:
            import feedparser  # noqa: F401
            return True
        except ImportError:
            logger.warning("SubstackCollector: feedparser not installed")
            return False

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Fetch Substack RSS feeds and yield matching entries.

        Args:
            queries: Search query strings used for relevance filtering.

        Yields:
            Document dicts with platform='substack', source_type='opinion_essay'.
        """
        import feedparser

        query_tokens = {t.lower() for q in queries for t in q.split()}
        count = 0
        seen_urls: set[str] = set()

        for feed_url in self._feed_urls:
            if count >= self._max_results:
                break
            try:
                feed = await asyncio.get_event_loop().run_in_executor(
                    None, lambda u=feed_url: feedparser.parse(u)
                )
                feed_title = feed.feed.get("title", "") if hasattr(feed, "feed") else ""

                for entry in feed.get("entries", []):
                    if count >= self._max_results:
                        break

                    entry_url = entry.get("link", "")
                    if not entry_url or entry_url in seen_urls:
                        continue

                    title = entry.get("title", "")
                    summary = entry.get("summary", "") or entry.get("content", [{}])[0].get(
                        "value", ""
                    ) if entry.get("content") else entry.get("summary", "")
                    text = _strip_html(f"{title}\n\n{summary}".strip())

                    if len(text) < 30:
                        continue

                    # Relevance check: at least one query token in title/text
                    text_lower = text.lower()
                    if query_tokens and not any(t in text_lower for t in query_tokens):
                        continue

                    seen_urls.add(entry_url)
                    count += 1

                    published = entry.get("published", "") or entry.get("updated", "")

                    yield {
                        "url": entry_url,
                        "title": title,
                        "text": text,
                        "source_type": "opinion_essay",
                        "platform": "substack",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "feed_url": feed_url,
                            "feed_title": feed_title,
                            "published": published,
                            "author": entry.get("author", ""),
                        },
                    }

                await asyncio.sleep(0.3)
            except Exception as exc:
                logger.warning(
                    "SubstackCollector: error fetching feed '%s': %s", feed_url, exc
                )

        # Fallback: if nothing yielded, note it
        if count == 0:
            logger.debug(
                "SubstackCollector: no matching entries found across %d feeds",
                len(self._feed_urls),
            )


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    import re
    import html as html_module
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_module.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
