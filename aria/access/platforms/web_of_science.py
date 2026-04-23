"""Web of Science platform handler — Clarivate Web of Science API v2."""

from __future__ import annotations

import logging
import os
from typing import Optional
from urllib.parse import quote

import httpx

from aria.engine.access.platforms.base_platform import BasePlatformHandler

logger = logging.getLogger("aria")

_WOS_API_BASE = "https://api.clarivate.com/apis/wos-starter/v1"
_WOS_EXPANDED_BASE = "https://api.clarivate.com/api/wos"


class WebOfScienceHandler(BasePlatformHandler):
    """Handler for Web of Science via Clarivate API.

    Supports two Clarivate APIs:
    - WOS Starter API (free tier, limited fields) — default
    - WOS Expanded API (paid, full metadata) — used if WOS_EXPANDED=true

    Requires WOS_API_KEY environment variable.
    Get an API key at: https://developer.clarivate.com/
    """

    platform_key = "web_of_science"
    base_url = _WOS_API_BASE

    def __init__(self) -> None:
        super().__init__()
        self._api_key: Optional[str] = None
        self._expanded: bool = os.getenv("WOS_EXPANDED", "").lower() in ("1", "true", "yes")

    async def authenticate(self, credentials: dict) -> bool:
        """Store Web of Science API key.

        Args:
            credentials: Dict with 'api_key'. Falls back to WOS_API_KEY env var.

        Returns:
            True if an API key is available.
        """
        self._api_key = (
            credentials.get("api_key")
            or credentials.get("wos_api_key")
            or os.getenv("WOS_API_KEY", "")
        )
        if self._api_key:
            self._authenticated = True
            logger.debug("WebOfScienceHandler: authenticated with API key")
            return True
        logger.warning(
            "WebOfScienceHandler: no api_key provided — set WOS_API_KEY env var"
        )
        return False

    async def fetch(self, url: str) -> Optional[str]:
        """Fetch article metadata from Web of Science by URL or UID.

        Extracts WOS UID or DOI from the URL and queries the API.

        Args:
            url: WOS article URL (e.g. https://www.webofscience.com/wos/woscc/full-record/WOS:000...)
                 or a DOI URL.

        Returns:
            JSON response text with article metadata, or None if unavailable.
        """
        if not self._api_key:
            return None

        uid = self._extract_uid(url)
        doi = self._extract_doi(url)

        if uid:
            return await self._fetch_by_uid(uid)
        if doi:
            return await self._fetch_by_doi(doi)

        logger.debug("WebOfScienceHandler: cannot extract UID or DOI from URL: %s", url)
        return None

    async def search(self, query: str, max_records: int = 10) -> Optional[str]:
        """Search Web of Science for articles matching a query.

        Args:
            query: Search string (supports WOS query syntax, e.g. 'TS=machine learning').
                   Plain text queries are automatically wrapped as TS={query}.
            max_records: Maximum number of records to return.

        Returns:
            JSON response text, or None if the request fails.
        """
        if not self._api_key:
            return None

        # Wrap plain-text queries as topic search
        wos_query = query if "=" in query else f"TS=({query})"

        headers = {
            "X-ApiKey": self._api_key,
            "Accept": "application/json",
        }

        if self._expanded:
            # WOS Expanded API
            params = {
                "databaseId": "WOS",
                "usrQuery": wos_query,
                "count": min(max_records, 100),
                "firstRecord": 1,
            }
            endpoint = f"{_WOS_EXPANDED_BASE}/query/batch"
        else:
            # WOS Starter API
            params = {
                "db": "WOS",
                "q": wos_query,
                "limit": min(max_records, 10),
                "page": 1,
            }
            endpoint = f"{_WOS_API_BASE}/documents"

        try:
            async with httpx.AsyncClient(timeout=20, headers=headers) as client:
                resp = await client.get(endpoint, params=params)

            if resp.status_code == 401:
                logger.warning("WebOfScienceHandler: invalid API key (401)")
                self._authenticated = False
                return None
            if resp.status_code == 403:
                logger.warning(
                    "WebOfScienceHandler: access forbidden (403) — "
                    "check subscription tier or API key permissions"
                )
                return None
            if resp.status_code != 200:
                logger.debug(
                    "WebOfScienceHandler: search HTTP %s for query '%s'",
                    resp.status_code,
                    query[:60],
                )
                return None

            return resp.text

        except Exception as exc:
            logger.warning(
                "WebOfScienceHandler: search error for '%s': %s", query[:60], exc
            )
            return None

    async def _fetch_by_uid(self, uid: str) -> Optional[str]:
        """Fetch a specific record by WOS UID."""
        headers = {"X-ApiKey": self._api_key, "Accept": "application/json"}
        endpoint = f"{_WOS_API_BASE}/documents/{quote(uid, safe='')}"
        try:
            async with httpx.AsyncClient(timeout=20, headers=headers) as client:
                resp = await client.get(endpoint)
            if resp.status_code == 200:
                return resp.text
            logger.debug("WebOfScienceHandler: UID fetch HTTP %s", resp.status_code)
            return None
        except Exception as exc:
            logger.debug("WebOfScienceHandler: UID fetch error: %s", exc)
            return None

    async def _fetch_by_doi(self, doi: str) -> Optional[str]:
        """Search by DOI using the WOS Starter API."""
        return await self.search(f"DO=({doi})", max_records=1)

    @staticmethod
    def _extract_uid(url: str) -> Optional[str]:
        """Extract WOS UID (e.g. WOS:000123456789) from a WOS URL."""
        if "WOS:" in url:
            # e.g. .../full-record/WOS:000123456789012
            parts = url.split("WOS:")
            if len(parts) > 1:
                uid_part = parts[1].split("/")[0].split("?")[0].strip()
                if uid_part:
                    return f"WOS:{uid_part}"
        return None

    @staticmethod
    def _extract_doi(url: str) -> Optional[str]:
        """Extract DOI from a doi.org or direct DOI URL."""
        if "doi.org/" in url:
            return url.split("doi.org/", 1)[1].split("?")[0].strip()
        return None
