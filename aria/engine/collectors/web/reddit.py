"""Reddit collector — public JSON API or PRAW (authenticated) when credentials are set."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

from .base import BaseCollector

logger = logging.getLogger("aria")


class RedditCollector(BaseCollector):
    """Collects posts from Reddit.

    - Without credentials: uses Reddit's public JSON API (no account needed)
    - With REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET + REDDIT_USERNAME + REDDIT_PASSWORD:
      uses PRAW (official Reddit API) for higher rate limits and more data
    """

    def __init__(self, max_results: int = 25) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True  # Public API always works

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        client_id = os.getenv("REDDIT_CLIENT_ID", "")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
        username = os.getenv("REDDIT_USERNAME", "")
        password = os.getenv("REDDIT_PASSWORD", "")

        if client_id and client_secret and username and password:
            async for doc in self._collect_praw(queries, client_id, client_secret, username, password):
                yield doc
        else:
            async for doc in self._collect_public(queries):
                yield doc

    async def _collect_praw(self, queries, client_id, client_secret, username, password):
        """Collect via PRAW (official Reddit API — authenticated)."""
        try:
            import praw
            loop = asyncio.get_event_loop()

            def _praw_search(query):
                reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    username=username,
                    password=password,
                    user_agent=f"ARIA Research Collector/1.0 by u/{username}",
                )
                results = []
                for post in reddit.subreddit("all").search(query, limit=10, sort="relevance", time_filter="year"):
                    results.append({
                        "id": post.id,
                        "title": post.title,
                        "selftext": post.selftext,
                        "url": f"https://reddit.com{post.permalink}",
                        "subreddit": post.subreddit.display_name,
                        "score": post.score,
                        "num_comments": post.num_comments,
                        "author": str(post.author) if post.author else "",
                    })
                return results

            seen_ids = set()
            now = datetime.now(timezone.utc).isoformat()
            count = 0

            for query in queries:
                if count >= self._max_results:
                    break
                try:
                    posts = await loop.run_in_executor(None, _praw_search, query)
                    for p in posts:
                        if count >= self._max_results:
                            break
                        if p["id"] in seen_ids:
                            continue
                        seen_ids.add(p["id"])
                        text = f"{p['title']}\n\n{p['selftext']}".strip()
                        if len(text) < 30:
                            continue
                        count += 1
                        yield {
                            "url": p["url"],
                            "title": p["title"],
                            "text": text,
                            "source_type": "forum_post",
                            "platform": "reddit",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": now,
                            "metadata": {
                                "query": query,
                                "subreddit": p["subreddit"],
                                "score": p["score"],
                                "num_comments": p["num_comments"],
                                "author": p["author"],
                                "method": "praw_authenticated",
                            },
                        }
                    await asyncio.sleep(1.0)
                except Exception as exc:
                    logger.warning("RedditCollector (PRAW): error for query '%s': %s", query, exc)

        except ImportError:
            logger.info("PRAW not installed, falling back to public API")
            async for doc in self._collect_public(queries):
                yield doc

    async def _collect_public(self, queries):
        """Collect via Reddit public JSON API (no auth needed)."""
        import httpx
        seen_urls = set()
        now = datetime.now(timezone.utc).isoformat()
        count = 0

        for query in queries:
            if count >= self._max_results:
                break
            try:
                url = f"https://www.reddit.com/search.json?q={query}&limit=25&sort=relevance"
                headers = {"User-Agent": "ARIA Research Collector/1.0"}
                async with httpx.AsyncClient(timeout=15, headers=headers) as client:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    posts = data.get("data", {}).get("children", [])
                    for post in posts:
                        if count >= self._max_results:
                            break
                        p = post.get("data", {})
                        post_url = f"https://reddit.com{p.get('permalink', '')}"
                        if post_url in seen_urls:
                            continue
                        seen_urls.add(post_url)
                        title = p.get("title", "")
                        body = p.get("selftext", "") or p.get("url", "")
                        text = f"{title}\n\n{body}".strip()
                        if len(text) < 30:
                            continue
                        count += 1
                        yield {
                            "url": post_url,
                            "title": title,
                            "text": text,
                            "source_type": "forum_post",
                            "platform": "reddit",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": now,
                            "metadata": {
                                "query": query,
                                "subreddit": p.get("subreddit", ""),
                                "score": p.get("score", 0),
                                "num_comments": p.get("num_comments", 0),
                                "author": p.get("author", ""),
                                "method": "public_api",
                            },
                        }
                await asyncio.sleep(0.5)
            except Exception as exc:
                logger.warning("RedditCollector (public): error for '%s': %s", query, exc)
