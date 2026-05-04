"""News collector — NewsAPI, GNews, and major RSS news feeds."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from urllib.parse import quote

import httpx

from .base import BaseCollector
from ...utils.camofox import get_client as _camofox

logger = logging.getLogger("aria")

# Domains that block plain HTTP — use Camofox for full-text fetch
_PAYWALLED_NEWS = {
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com",
    "nytimes.com", "washingtonpost.com", "economist.com",
    "apnews.com", "thetimes.co.uk",
}

_NEWSAPI_URL = "https://newsapi.org/v2/everything"
_GNEWS_URL = "https://gnews.io/api/v4/search"

# Major news RSS feeds — always available, no key needed
_NEWS_RSS_FEEDS: list[tuple[str, str]] = [
    ("BBC News", "https://feeds.bbci.co.uk/news/rss.xml"),
    ("Reuters", "https://feeds.reuters.com/reuters/topNews"),
    ("AP News", "https://rsshub.app/apnews/topics/apf-topnews"),
    ("NPR", "https://feeds.npr.org/1001/rss.xml"),
    ("The Guardian", "https://www.theguardian.com/world/rss"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Science Daily", "https://www.sciencedaily.com/rss/all.xml"),
    ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ("Wired", "https://www.wired.com/feed/rss"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
]


class NewsCollector(BaseCollector):
    """Collects news articles from multiple sources.

    Sources (in priority order):
    1. NewsAPI.org (NEWS_API_KEY) — 100 req/day free tier
    2. GNews (GNEWS_API_KEY) — 100 req/day free tier
    3. RSS feeds from major news organizations (always available)
    """

    def __init__(self, max_results: int = 30) -> None:
        self._max_results = max_results
        self._newsapi_key = os.getenv("NEWS_API_KEY", "")
        self._gnews_key = os.getenv("GNEWS_API_KEY", "")

    async def validate(self) -> bool:
        # RSS feeds always available
        try:
            import feedparser  # noqa: F401
            return True
        except ImportError:
            logger.warning("NewsCollector: feedparser not installed")
            return False

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Collect news articles matching queries.

        Args:
            queries: Research query strings.

        Yields:
            Document dicts with platform='news', source_type='news_article'.
        """
        seen_urls: set[str] = set()
        count = 0

        for query in queries[:4]:
            if count >= self._max_results:
                break

            # 1. NewsAPI
            if self._newsapi_key and count < self._max_results:
                async for doc in self._search_newsapi(query, seen_urls):
                    if count >= self._max_results:
                        break
                    yield doc
                    count += 1

            # 2. GNews
            if self._gnews_key and count < self._max_results:
                async for doc in self._search_gnews(query, seen_urls):
                    if count >= self._max_results:
                        break
                    yield doc
                    count += 1

        # 3. RSS feeds — always run (query-filtered client-side)
        if count < self._max_results:
            async for doc in self._collect_rss(queries, seen_urls):
                if count >= self._max_results:
                    break
                yield doc
                count += 1

    async def _search_newsapi(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Search NewsAPI.org everything endpoint."""
        try:
            params = {
                "q": query,
                "apiKey": self._newsapi_key,
                "pageSize": 10,
                "sortBy": "relevancy",
                "language": "en",
            }
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(_NEWSAPI_URL, params=params)

            if resp.status_code == 401:
                logger.warning("NewsCollector: NewsAPI key invalid (401)")
                return
            if resp.status_code == 426:
                logger.info("NewsCollector: NewsAPI free tier limit reached (426)")
                return
            if resp.status_code != 200:
                logger.debug("NewsCollector: NewsAPI HTTP %s", resp.status_code)
                return

            data = resp.json()
            articles = data.get("articles", [])

            for article in articles:
                url = article.get("url", "")
                if not url or url in seen_urls or "removed" in url.lower():
                    continue
                seen_urls.add(url)

                title = article.get("title", "") or ""
                description = article.get("description", "") or ""
                content = article.get("content", "") or ""
                # content is truncated in free tier — use description as primary
                text_body = content if len(content) > len(description) else description
                text = f"{title}\n\n{text_body}".strip()
                if len(text) < 30:
                    continue

                source_name = article.get("source", {}).get("name", "")
                published = article.get("publishedAt", "")
                author = article.get("author", "") or ""

                yield {
                    "url": url,
                    "title": title,
                    "text": text,
                    "source_type": "news_article",
                    "platform": "news",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "source": source_name,
                        "published_at": published,
                        "author": author,
                        "provider": "newsapi",
                        "query": query,
                    },
                }

            await asyncio.sleep(0.3)

        except Exception as exc:
            logger.warning("NewsCollector: NewsAPI error for '%s': %s", query, exc)

    async def _search_gnews(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Search GNews API."""
        try:
            params = {
                "q": query,
                "token": self._gnews_key,
                "max": 10,
                "lang": "en",
                "sortby": "relevance",
            }
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(_GNEWS_URL, params=params)

            if resp.status_code == 403:
                logger.warning("NewsCollector: GNews API key invalid (403)")
                return
            if resp.status_code != 200:
                logger.debug("NewsCollector: GNews HTTP %s", resp.status_code)
                return

            data = resp.json()
            articles = data.get("articles", [])

            for article in articles:
                url = article.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                title = article.get("title", "") or ""
                description = article.get("description", "") or ""
                content = article.get("content", "") or ""
                text_body = content if len(content) > len(description) else description
                text = f"{title}\n\n{text_body}".strip()
                if len(text) < 30:
                    continue

                source_name = article.get("source", {}).get("name", "")
                published = article.get("publishedAt", "")

                yield {
                    "url": url,
                    "title": title,
                    "text": text,
                    "source_type": "news_article",
                    "platform": "news",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "source": source_name,
                        "published_at": published,
                        "provider": "gnews",
                        "query": query,
                    },
                }

            await asyncio.sleep(0.3)

        except Exception as exc:
            logger.warning("NewsCollector: GNews error for '%s': %s", query, exc)

    async def _collect_rss(
        self, queries: list[str], seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Collect from major news RSS feeds, filtered by query relevance."""
        try:
            import feedparser
        except ImportError:
            logger.warning("NewsCollector: feedparser not installed, skipping RSS")
            return

        query_tokens = {t.lower() for q in queries for t in q.split() if len(t) > 3}

        for feed_name, feed_url in _NEWS_RSS_FEEDS:
            try:
                feed = await asyncio.get_event_loop().run_in_executor(
                    None, lambda u=feed_url: feedparser.parse(u)
                )

                for entry in feed.entries[:15]:
                    url = entry.get("link", "")
                    if not url or url in seen_urls:
                        continue

                    title = entry.get("title", "") or ""
                    summary = entry.get("summary", "") or entry.get("description", "") or ""
                    text = f"{title}\n\n{summary}".strip()

                    # Client-side relevance filter
                    text_lower = text.lower()
                    if query_tokens and not any(t in text_lower for t in query_tokens):
                        continue

                    if len(text) < 30:
                        continue

                    seen_urls.add(url)
                    published = entry.get("published", "") or entry.get("updated", "")

                    # Enrich with full article text via Camofox for paywalled sources
                    camofox = _camofox()
                    domain  = url.split("/")[2] if "/" in url else ""
                    if camofox.available and any(d in domain for d in _PAYWALLED_NEWS):
                        try:
                            page = await camofox.fetch_page(url, wait_seconds=3.0)
                            full = page.get("text", "")
                            if full and len(full) > len(text):
                                text  = full
                                title = page.get("title", "") or title
                                logger.debug("NewsCollector: Camofox enriched %s", url)
                        except Exception as cf_exc:
                            logger.debug("NewsCollector: Camofox skip %s: %s", url, cf_exc)

                    yield {
                        "url": url,
                        "title": title,
                        "text": text,
                        "source_type": "news_article",
                        "platform": "news",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": feed_name,
                            "published": published,
                            "provider": "rss",
                            "via_camofox": camofox.available and any(d in domain for d in _PAYWALLED_NEWS),
                        },
                    }

                await asyncio.sleep(0.2)

            except Exception as exc:
                logger.debug(
                    "NewsCollector: RSS feed '%s' error: %s", feed_name, exc
                )
