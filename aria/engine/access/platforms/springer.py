"""Springer Nature platform handler."""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import quote

import httpx

from .base_platform import BasePlatformHandler

logger = logging.getLogger("aria")


class SpringerHandler(BasePlatformHandler):
    """Handler for Springer Nature API."""

    API_BASE = "https://api.springernature.com"

    def __init__(self) -> None:
        super().__init__()
        self._api_key: Optional[str] = None

    async def authenticate(self, credentials: dict) -> bool:
        """Store Springer Nature API key.

        Args:
            credentials: Dict with 'api_key'.

        Returns:
            True if api_key provided.
        """
        self._api_key = credentials.get("api_key")
        if self._api_key:
            self._authenticated = True
            logger.debug("SpringerHandler: authenticated with API key")
            return True
        logger.warning("SpringerHandler: no api_key in credentials")
        return False

    async def fetch(self, url: str) -> Optional[str]:
        """Fetch article metadata/content from Springer API.

        Args:
            url: Article URL or DOI URL.

        Returns:
            JSON response text, or None if unavailable.
        """
        if not self._api_key:
            return None
        try:
            doi = None
            if "doi.org/" in url:
                doi = url.split("doi.org/", 1)[1]
            elif "link.springer.com/article/" in url:
                doi = url.split("link.springer.com/article/", 1)[1].split("?")[0]

            if doi:
                api_url = f"{self.API_BASE}/meta/v2/json"
                params = {"api_key": self._api_key, "q": f"doi:{quote(doi, safe='')}"}
            else:
                # Try openaccess endpoint
                api_url = f"{self.API_BASE}/openaccess/json"
                params = {"api_key": self._api_key, "q": url}

            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(api_url, params=params)
                if resp.status_code == 200:
                    return resp.text
                logger.debug("SpringerHandler: HTTP %d for %s", resp.status_code, api_url)
        except Exception as exc:
            logger.debug("SpringerHandler fetch error for %s: %s", url, exc)
        return None
