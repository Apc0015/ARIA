"""Twitter/X collector using the Twitter API v2 (requires TWITTER_BEARER_TOKEN)."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from urllib.parse import quote

from .base import BaseCollector

logger = logging.getLogger("aria")

_SEARCH_URL = (
    "https://api.twitter.com/2/tweets/search/recent"
    "?query={query}&max_results=10"
    "&tweet.fields=created_at,author_id,public_metrics,lang,text"
    "&expansions=author_id"
    "&user.fields=name,username"
)


class TwitterCollector(BaseCollector):
    """Collects recent tweets via the Twitter API v2.

    Requires the TWITTER_BEARER_TOKEN environment variable.
    Silently skips if the token is not set.
    """

    async def validate(self) -> bool:
        return bool(os.getenv("TWITTER_BEARER_TOKEN"))

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Search Twitter for recent tweets matching queries.

        Args:
            queries: Search query strings.

        Yields:
            Document dicts with platform='twitter', source_type='social_media'.
        """
        import httpx

        token = os.getenv("TWITTER_BEARER_TOKEN")
        if not token:
            logger.info("TwitterCollector: no TWITTER_BEARER_TOKEN set, skipping")
            return

        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "ARIA Research Collector/1.0",
        }
        seen_ids: set[str] = set()

        for query in queries:
            try:
                # Twitter API requires excluding retweets for cleaner results
                api_query = f"{query} -is:retweet lang:en"
                url = _SEARCH_URL.format(query=quote(api_query))

                async with httpx.AsyncClient(timeout=15, headers=headers) as client:
                    resp = await client.get(url)
                    if resp.status_code == 401:
                        logger.warning(
                            "TwitterCollector: invalid bearer token (401)"
                        )
                        return
                    if resp.status_code == 429:
                        logger.info("TwitterCollector: rate limited, stopping")
                        return
                    if resp.status_code != 200:
                        logger.debug(
                            "TwitterCollector: HTTP %s for query '%s'",
                            resp.status_code,
                            query,
                        )
                        continue

                    data = resp.json()
                    tweets = data.get("data", [])
                    users = {
                        u["id"]: u
                        for u in data.get("includes", {}).get("users", [])
                    }

                    for tweet in tweets:
                        tweet_id = tweet.get("id", "")
                        if tweet_id in seen_ids:
                            continue
                        seen_ids.add(tweet_id)

                        text = tweet.get("text", "")
                        if not text or len(text) < 10:
                            continue

                        author_id = tweet.get("author_id", "")
                        author = users.get(author_id, {})
                        username = author.get("username", "")
                        tweet_url = (
                            f"https://twitter.com/{username}/status/{tweet_id}"
                            if username
                            else f"https://twitter.com/i/web/status/{tweet_id}"
                        )

                        metrics = tweet.get("public_metrics", {})

                        yield {
                            "url": tweet_url,
                            "title": text[:100],
                            "text": text,
                            "source_type": "social_media",
                            "platform": "twitter",
                            "language": tweet.get("lang", "en"),
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "query": query,
                                "tweet_id": tweet_id,
                                "author_id": author_id,
                                "username": username,
                                "display_name": author.get("name", ""),
                                "created_at": tweet.get("created_at", ""),
                                "retweet_count": metrics.get("retweet_count", 0),
                                "like_count": metrics.get("like_count", 0),
                                "reply_count": metrics.get("reply_count", 0),
                            },
                        }

                await asyncio.sleep(1.0)  # Twitter rate limits are strict
            except Exception as exc:
                logger.warning(
                    "TwitterCollector: error for query '%s': %s", query, exc
                )
