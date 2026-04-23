"""Stack Overflow collector using the Stack Exchange API v2.3."""

from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from urllib.parse import quote

from .base import BaseCollector

logger = logging.getLogger("aria")

_SEARCH_URL = (
    "https://api.stackexchange.com/2.3/search"
    "?order=desc&sort=relevance&intitle={query}&site=stackoverflow&pagesize=10"
    "&filter=withbody"
)
_ANSWERS_URL = (
    "https://api.stackexchange.com/2.3/questions/{qid}/answers"
    "?order=desc&sort=votes&site=stackoverflow&pagesize=3&filter=withbody"
)


class StackOverflowCollector(BaseCollector):
    """Collects questions and accepted answers from Stack Overflow."""

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Search Stack Overflow and yield question+answer documents.

        Args:
            queries: Search query strings.

        Yields:
            Document dicts with platform='stackoverflow', source_type='forum_post'.
        """
        import httpx

        seen_ids: set[int] = set()
        count = 0

        for query in queries:
            if count >= self._max_results:
                break
            try:
                search_url = _SEARCH_URL.format(query=quote(query))
                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.get(
                        search_url,
                        headers={"User-Agent": "ARIA Research Collector/1.0"},
                    )
                    if resp.status_code != 200:
                        logger.debug(
                            "StackOverflowCollector: HTTP %s for query '%s'",
                            resp.status_code,
                            query,
                        )
                        continue
                    data = resp.json()
                    items = data.get("items", [])

                    for item in items:
                        if count >= self._max_results:
                            break
                        qid = item.get("question_id")
                        if not qid or qid in seen_ids:
                            continue
                        seen_ids.add(qid)

                        doc = await self._build_doc(client, item, query)
                        if doc:
                            count += 1
                            yield doc
                        await asyncio.sleep(0.3)

            except Exception as exc:
                logger.warning(
                    "StackOverflowCollector: error for query '%s': %s", query, exc
                )

    async def _build_doc(
        self, client: Any, item: dict, query: str
    ) -> dict[str, Any] | None:
        """Build a document from a SO question, optionally fetching top answer."""
        try:
            qid = item.get("question_id")
            title = html.unescape(item.get("title", ""))
            q_body = _strip_html(item.get("body", ""))
            post_url = item.get("link", f"https://stackoverflow.com/q/{qid}")

            # Fetch top answer if question has answers
            answer_text = ""
            answer_count = item.get("answer_count", 0)
            is_answered = item.get("is_answered", False)

            if is_answered and answer_count > 0 and qid:
                answer_text = await self._fetch_top_answer(client, qid)

            text_parts = [title]
            if q_body:
                text_parts.append(q_body)
            if answer_text:
                text_parts.append(f"Answer: {answer_text}")

            text = "\n\n".join(text_parts).strip()
            if len(text) < 30:
                return None

            return {
                "url": post_url,
                "title": title,
                "text": text,
                "source_type": "forum_post",
                "platform": "stackoverflow",
                "language": "en",
                "word_count": len(text.split()),
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "query": query,
                    "question_id": qid,
                    "score": item.get("score", 0),
                    "answer_count": answer_count,
                    "is_answered": is_answered,
                    "tags": item.get("tags", []),
                    "view_count": item.get("view_count", 0),
                    "owner": (item.get("owner") or {}).get("display_name", ""),
                },
            }
        except Exception as exc:
            logger.debug(
                "StackOverflowCollector: doc build failed for qid %s: %s",
                item.get("question_id"),
                exc,
            )
            return None

    async def _fetch_top_answer(self, client: Any, qid: int) -> str:
        """Fetch the top-voted answer body for a question."""
        try:
            url = _ANSWERS_URL.format(qid=qid)
            resp = await client.get(
                url, headers={"User-Agent": "ARIA Research Collector/1.0"}
            )
            if resp.status_code != 200:
                return ""
            data = resp.json()
            items = data.get("items", [])
            if items:
                return _strip_html(items[0].get("body", ""))
        except Exception as exc:
            logger.debug(
                "StackOverflowCollector: answer fetch failed for qid %s: %s", qid, exc
            )
        return ""


def _strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    import re
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
