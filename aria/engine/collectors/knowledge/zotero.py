"""Zotero collector — reads items from local Zotero (via connector) or Zotero cloud API."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

from .base import BaseCollector

logger = logging.getLogger("aria")

_LOCAL_API = "http://localhost:23119/api/users/0/items"
_CLOUD_API = "https://api.zotero.org/{library_type}s/{library_id}/items"

# Map Zotero item types to ARIA source_type values
_TYPE_MAP: dict[str, str] = {
    "journalArticle": "research_paper",
    "conferencePaper": "research_paper",
    "preprint": "research_paper",
    "thesis": "research_paper",
    "book": "book",
    "bookSection": "book",
    "report": "technical_doc",
    "webpage": "web_page",
    "blogPost": "web_post",
    "videoRecording": "video_transcript",
    "podcast": "video_transcript",
    "document": "technical_doc",
    "presentation": "technical_doc",
}


class ZoteroCollector(BaseCollector):
    """Collects items from a Zotero library (local connector or cloud API).

    Local mode: connects to the Zotero connector running on localhost:23119.
    Cloud mode: connects to api.zotero.org using a user/group library ID and API key.

    Args:
        mode: ``'local'`` or ``'cloud'``.
        library_id: Zotero user/group ID (required for cloud mode).
        api_key: Zotero API key (required for cloud mode).
        collection_key: Optional collection key to filter items.
        library_type: ``'user'`` or ``'group'`` (cloud mode only).
        max_items: Maximum number of items to fetch per query.
    """

    def __init__(
        self,
        mode: str = "local",
        library_id: str | None = None,
        api_key: str | None = None,
        collection_key: str | None = None,
        library_type: str = "user",
        max_items: int = 500,
    ) -> None:
        self._mode = mode
        self._library_id = library_id or os.getenv("ZOTERO_LIBRARY_ID", "")
        self._api_key = api_key or os.getenv("ZOTERO_API_KEY", "")
        self._collection_key = collection_key
        self._library_type = library_type
        self._max_items = max_items

    async def validate(self) -> bool:
        if self._mode == "local":
            # Check if local Zotero connector is reachable
            try:
                import httpx
                async with httpx.AsyncClient(timeout=3) as client:
                    resp = await client.get(_LOCAL_API + "?limit=1")
                    return resp.status_code == 200
            except Exception:
                return False
        else:
            return bool(self._library_id and self._api_key)

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Fetch items from the Zotero library and yield matching documents.

        Args:
            queries: Search query strings for filtering items.

        Yields:
            Document dicts with platform='zotero', source_type varies by item type.
        """
        import httpx

        query_tokens = {t.lower() for q in queries for t in q.split() if len(t) > 2}

        try:
            items = await self._fetch_all_items()
        except Exception as exc:
            logger.warning("ZoteroCollector: failed to fetch items: %s", exc)
            return

        count = 0
        for item in items:
            if count >= self._max_items:
                break
            try:
                data = item.get("data", item)
                item_type = data.get("itemType", "document")
                if item_type == "attachment":
                    # Download + convert the attachment to Markdown via MarkItDown
                    doc = await self._attachment_to_doc(data, query_tokens)
                else:
                    doc = self._item_to_doc(item, query_tokens)
                if doc:
                    count += 1
                    yield doc
            except Exception as exc:
                logger.debug("ZoteroCollector: item conversion error: %s", exc)

    async def _fetch_all_items(self) -> list[dict]:
        """Fetch all items from local or cloud Zotero."""
        import httpx

        items: list[dict] = []
        limit = 100
        start = 0

        if self._mode == "local":
            base_url = _LOCAL_API
            headers: dict[str, str] = {}
        else:
            if not self._library_id:
                logger.warning("ZoteroCollector: library_id required for cloud mode")
                return []
            base_url = _CLOUD_API.format(
                library_type=self._library_type, library_id=self._library_id
            )
            headers = {"Zotero-API-Key": self._api_key, "Zotero-API-Version": "3"}
            if self._collection_key:
                base_url = base_url.replace(
                    "/items", f"/collections/{self._collection_key}/items"
                )

        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            while True:
                url = f"{base_url}?limit={limit}&start={start}&format=json"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.debug(
                            "ZoteroCollector: HTTP %s fetching items", resp.status_code
                        )
                        break
                    batch = resp.json()
                    if not batch:
                        break
                    items.extend(batch)
                    if len(batch) < limit:
                        break
                    start += limit
                    await asyncio.sleep(0.2)
                except Exception as exc:
                    logger.warning("ZoteroCollector: fetch page error: %s", exc)
                    break

        return items

    async def _attachment_to_doc(
        self, data: dict, query_tokens: set[str]
    ) -> dict[str, Any] | None:
        """Download an attachment, convert via MarkItDown, yield as ARIA doc.

        Only runs in cloud mode (local API file download requires Zotero user
        auth cookies, not an API key). Skips non-supported MIME types.
        """
        if self._mode != "cloud" or not self._api_key or not self._library_id:
            return None

        from aria.engine.utils.markitdown_adapter import convert_bytes, is_supported

        filename = data.get("filename") or data.get("title") or ""
        content_type = (data.get("contentType") or "").lower()
        # Map MIME type to extension when filename lacks one
        if "." not in filename:
            mime_to_ext = {
                "application/pdf": ".pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
                "application/msword": ".doc",
                "application/vnd.ms-excel": ".xls",
                "application/vnd.ms-powerpoint": ".ppt",
                "text/html": ".html",
                "text/plain": ".txt",
                "application/epub+zip": ".epub",
            }
            ext = mime_to_ext.get(content_type, "")
            if ext:
                filename = (filename or "attachment") + ext
        if not is_supported(filename):
            return None

        key = data.get("key", "")
        if not key:
            return None
        file_url = _CLOUD_API.format(
            library_type=self._library_type, library_id=self._library_id
        ).replace("/items", f"/items/{key}/file")

        import httpx
        try:
            async with httpx.AsyncClient(
                timeout=60,
                headers={"Zotero-API-Key": self._api_key, "Zotero-API-Version": "3"},
                follow_redirects=True,
            ) as client:
                resp = await client.get(file_url)
            if resp.status_code != 200:
                logger.debug("ZoteroCollector: attachment %s HTTP %s", key, resp.status_code)
                return None
            body_bytes = resp.content
        except Exception as exc:
            logger.debug("ZoteroCollector: attachment fetch failed for %s: %s", key, exc)
            return None

        markdown = convert_bytes(body_bytes, filename)
        if len(markdown) < 50:
            return None

        title = data.get("title") or filename
        # Relevance filter against queries
        if query_tokens:
            text_lower = markdown.lower()
            if not any(t in text_lower for t in query_tokens):
                return None

        return {
            "url": data.get("url") or f"zotero://select/library/items/{key}",
            "title": title,
            "text": markdown,
            "source_type": "technical_doc",
            "platform": "zotero",
            "language": "en",
            "word_count": len(markdown.split()),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "item_type": "attachment",
                "zotero_key": key,
                "content_type": content_type,
                "filename": filename,
                "parent_item": data.get("parentItem", ""),
                "converted_by": "markitdown",
            },
        }

    def _item_to_doc(
        self, item: dict, query_tokens: set[str]
    ) -> dict[str, Any] | None:
        """Convert a Zotero item dict to an ARIA document."""
        data = item.get("data", item)  # local API wraps in 'data', cloud doesn't always
        item_type = data.get("itemType", "document")

        # Skip notes (attachments handled by _attachment_to_doc)
        if item_type in ("attachment", "note"):
            return None

        title = data.get("title", "")
        if not title:
            return None

        abstract = data.get("abstractNote", "") or data.get("abstract", "")
        url = data.get("url", "") or data.get("DOI", "")
        if data.get("DOI") and not url.startswith("http"):
            url = f"https://doi.org/{data['DOI']}"

        # Build text from available fields
        parts = [title]
        if abstract:
            parts.append(abstract)
        # Authors
        creators = data.get("creators", [])
        if creators:
            author_strs = []
            for c in creators[:5]:
                name = (
                    f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
                    or c.get("name", "")
                )
                if name:
                    author_strs.append(name)
            if author_strs:
                parts.append(f"Authors: {', '.join(author_strs)}")

        text = "\n\n".join(parts).strip()
        if len(text) < 10:
            return None

        # Relevance filter if queries given
        if query_tokens:
            text_lower = text.lower()
            if not any(t in text_lower for t in query_tokens):
                return None

        source_type = _TYPE_MAP.get(item_type, "technical_doc")
        publication = (
            data.get("publicationTitle", "")
            or data.get("bookTitle", "")
            or data.get("publisher", "")
        )

        return {
            "url": url or f"zotero://select/library/items/{data.get('key', '')}",
            "title": title,
            "text": text,
            "source_type": source_type,
            "platform": "zotero",
            "language": data.get("language", "en") or "en",
            "word_count": len(text.split()),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "item_type": item_type,
                "zotero_key": data.get("key", ""),
                "doi": data.get("DOI", ""),
                "date": data.get("date", ""),
                "publication": publication,
                "tags": [t.get("tag", "") for t in data.get("tags", [])],
                "collections": data.get("collections", []),
            },
        }
