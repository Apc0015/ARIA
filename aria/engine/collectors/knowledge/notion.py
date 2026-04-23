"""Notion collector using the Notion API v1 search endpoint."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

from .base import BaseCollector

logger = logging.getLogger("aria")

_SEARCH_URL = "https://api.notion.com/v1/search"
_NOTION_VERSION = "2022-06-28"


class NotionCollector(BaseCollector):
    """Searches Notion workspace pages and databases via the Notion API.

    Requires a NOTION_TOKEN (integration token).
    Get one from: https://www.notion.so/my-integrations
    The integration must be shared with the pages you want to search.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return bool(os.getenv("NOTION_TOKEN"))

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        import httpx

        token = os.getenv("NOTION_TOKEN")
        if not token:
            logger.info("NotionCollector: no NOTION_TOKEN set, skipping")
            return

        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }
        seen_ids: set[str] = set()
        count = 0

        for query in queries:
            if count >= self._max_results:
                break
            try:
                body = {
                    "query": query,
                    "page_size": 10,
                    "filter": {"value": "page", "property": "object"},
                }
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(_SEARCH_URL, headers=headers, json=body)
                    if resp.status_code == 401:
                        logger.warning("NotionCollector: invalid token (401)")
                        return
                    if resp.status_code != 200:
                        logger.debug("NotionCollector: HTTP %s for '%s'", resp.status_code, query)
                        continue

                    data = resp.json()
                    results = data.get("results", [])

                    for page in results:
                        if count >= self._max_results:
                            break

                        page_id = page.get("id", "")
                        if page_id in seen_ids:
                            continue
                        seen_ids.add(page_id)

                        # Extract title from page properties
                        props = page.get("properties", {})
                        title = _extract_title(props)
                        if not title:
                            continue

                        page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")
                        created = page.get("created_time", "")
                        last_edited = page.get("last_edited_time", "")

                        # Extract text content from page properties
                        text_parts = [title]
                        for key, prop in props.items():
                            if key == "title":
                                continue
                            extracted = _extract_prop_text(prop)
                            if extracted:
                                text_parts.append(f"{key}: {extracted}")

                        text = "\n".join(text_parts)
                        if len(text) < 10:
                            continue

                        count += 1
                        yield {
                            "url": page_url,
                            "title": title,
                            "text": text,
                            "source_type": "technical_doc",
                            "platform": "notion",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "query": query,
                                "page_id": page_id,
                                "created_time": created,
                                "last_edited_time": last_edited,
                                "object_type": page.get("object", "page"),
                            },
                        }

                await asyncio.sleep(0.3)
            except Exception as exc:
                logger.warning("NotionCollector: error for query '%s': %s", query, exc)


def _extract_title(props: dict) -> str:
    """Extract page title from Notion page properties."""
    for key in ("title", "Name", "Title", "Page"):
        prop = props.get(key, {})
        if prop.get("type") == "title":
            items = prop.get("title", [])
            return "".join(item.get("plain_text", "") for item in items).strip()
    # Fallback: find any title-type property
    for prop in props.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            items = prop.get("title", [])
            text = "".join(item.get("plain_text", "") for item in items).strip()
            if text:
                return text
    return ""


def _extract_prop_text(prop: dict) -> str:
    """Extract text value from a Notion property of any type."""
    ptype = prop.get("type", "")
    if ptype == "rich_text":
        items = prop.get("rich_text", [])
        return "".join(i.get("plain_text", "") for i in items).strip()
    if ptype == "select":
        sel = prop.get("select") or {}
        return sel.get("name", "")
    if ptype == "multi_select":
        items = prop.get("multi_select", [])
        return ", ".join(i.get("name", "") for i in items)
    if ptype == "number":
        val = prop.get("number")
        return str(val) if val is not None else ""
    if ptype == "url":
        return prop.get("url", "") or ""
    if ptype == "email":
        return prop.get("email", "") or ""
    if ptype == "date":
        d = prop.get("date") or {}
        return d.get("start", "")
    if ptype == "checkbox":
        return str(prop.get("checkbox", False))
    return ""
