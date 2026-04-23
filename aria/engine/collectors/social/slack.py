"""Slack collector using the Slack Web API (search.messages endpoint)."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

from .base import BaseCollector

logger = logging.getLogger("aria")

_SEARCH_URL = "https://slack.com/api/search.messages"


class SlackCollector(BaseCollector):
    """Searches Slack workspace messages via the Slack Web API.

    Requires a SLACK_TOKEN with search:read scope.
    Get a token from: https://api.slack.com/apps → OAuth & Permissions
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return bool(os.getenv("SLACK_TOKEN"))

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        import httpx

        token = os.getenv("SLACK_TOKEN")
        if not token:
            logger.info("SlackCollector: no SLACK_TOKEN set, skipping")
            return

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        seen_ids: set[str] = set()
        count = 0

        for query in queries:
            if count >= self._max_results:
                break
            try:
                params = {"query": query, "count": 20, "sort": "score"}
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(_SEARCH_URL, headers=headers, params=params)
                    if resp.status_code == 401:
                        logger.warning("SlackCollector: invalid token (401)")
                        return
                    if resp.status_code != 200:
                        logger.debug("SlackCollector: HTTP %s for '%s'", resp.status_code, query)
                        continue

                    data = resp.json()
                    if not data.get("ok"):
                        error = data.get("error", "unknown")
                        logger.warning("SlackCollector: API error: %s", error)
                        if error in ("not_authed", "invalid_auth", "account_inactive"):
                            return
                        continue

                    messages = data.get("messages", {}).get("matches", [])
                    for msg in messages:
                        if count >= self._max_results:
                            break

                        msg_ts = msg.get("ts", "")
                        channel_id = msg.get("channel", {}).get("id", "")
                        uid = f"{channel_id}:{msg_ts}"
                        if uid in seen_ids:
                            continue
                        seen_ids.add(uid)

                        text = msg.get("text", "")
                        if not text or len(text) < 20:
                            continue

                        channel_name = msg.get("channel", {}).get("name", "unknown")
                        username = msg.get("username", "") or msg.get("user", "")
                        permalink = msg.get("permalink", "")

                        count += 1
                        yield {
                            "url": permalink,
                            "title": f"Slack #{channel_name}: {text[:80]}",
                            "text": text,
                            "source_type": "forum_post",
                            "platform": "slack",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "query": query,
                                "channel": channel_name,
                                "channel_id": channel_id,
                                "username": username,
                                "timestamp": msg_ts,
                            },
                        }

                await asyncio.sleep(0.5)
            except Exception as exc:
                logger.warning("SlackCollector: error for query '%s': %s", query, exc)
