"""Generic RSS/Atom feed collector using feedparser."""

from __future__ import annotations

import asyncio
import logging
import re
import html as html_module
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

from .base import BaseCollector

logger = logging.getLogger("aria")

# Sensible default feeds covering tech, science, and research
_DEFAULT_FEEDS: list[str] = [
    "https://feeds.feedburner.com/TechCrunch",
    "https://www.wired.com/feed/rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.theverge.com/rss/index.xml",
    "https://news.ycombinator.com/rss",
    "https://feeds.nature.com/nature/rss/current",
    "https://www.sciencedaily.com/rss/top.xml",
]


class RSSCollector(BaseCollector):
    """Reads any RSS/Atom feed and returns entries matching the queries."""

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
            logger.warning("RSSCollector: feedparser not installed")
            return False

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Parse configured RSS/Atom feeds and yield matching entries.

        Matching is done by simple case-insensitive token search in title + summary.

        Args:
            queries: Search query strings.

        Yields:
            Document dicts with the feed's domain as platform, source_type='web_post'.
        """
        import feedparser

        query_tokens = {t.lower() for q in queries for t in q.split() if len(t) > 2}
        count = 0
        seen_urls: set[str] = set()

        for feed_url in self._feed_urls:
            if count >= self._max_results:
                break
            try:
                feed = await asyncio.get_event_loop().run_in_executor(
                    None, lambda u=feed_url: feedparser.parse(u)
                )
                feed_title = ""
                if hasattr(feed, "feed"):
                    feed_title = feed.feed.get("title", "")

                platform = _domain_from_url(feed_url)

                for entry in feed.get("entries", []):
                    if count >= self._max_results:
                        break

                    entry_url = entry.get("link", "")
                    if not entry_url or entry_url in seen_urls:
                        continue

                    title = entry.get("title", "")
                    # Prefer full content over summary
                    content_list = entry.get("content", [])
                    if content_list:
                        raw_text = content_list[0].get("value", "")
                    else:
                        raw_text = entry.get("summary", "")

                    text = _strip_html(f"{title}\n\n{raw_text}".strip())
                    if len(text) < 20:
                        continue

                    # Relevance filter
                    if query_tokens:
                        text_lower = text.lower()
                        if not any(t in text_lower for t in query_tokens):
                            continue

                    seen_urls.add(entry_url)
                    count += 1

                    published = entry.get("published", "") or entry.get("updated", "")

                    yield {
                        "url": entry_url,
                        "title": title,
                        "text": text,
                        "source_type": "web_post",
                        "platform": platform,
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

                await asyncio.sleep(0.2)
            except Exception as exc:
                logger.warning(
                    "RSSCollector: error fetching feed '%s': %s", feed_url, exc
                )


def _domain_from_url(url: str) -> str:
    """Extract a short domain name to use as platform identifier."""
    match = re.search(r"https?://(?:www\.)?([^/]+)", url)
    if match:
        domain = match.group(1)
        # Strip TLD for short name
        parts = domain.split(".")
        if len(parts) >= 2:
            return parts[-2]
        return domain
    return "rss"


def _strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_module.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
