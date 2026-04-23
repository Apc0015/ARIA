"""IEEE Xplore platform handler."""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import quote

import httpx

from .base_platform import BasePlatformHandler

logger = logging.getLogger("aria")


class IEEEHandler(BasePlatformHandler):
    """Handler for IEEE Xplore API."""

    API_BASE = "https://ieeexploreapi.ieee.org/api/v1"

    def __init__(self) -> None:
        super().__init__()
        self._api_key: Optional[str] = None

    async def authenticate(self, credentials: dict) -> bool:
        """Store IEEE Xplore API key.

        Args:
            credentials: Dict with 'api_key'.

        Returns:
            True if api_key provided.
        """
        self._api_key = credentials.get("api_key")
        if self._api_key:
            self._authenticated = True
            logger.debug("IEEEHandler: authenticated with API key")
            return True
        logger.warning("IEEEHandler: no api_key in credentials")
        return False

    async def fetch(self, url: str) -> Optional[str]:
        """Fetch article metadata/abstract from IEEE Xplore.

        Args:
            url: IEEE article URL or DOI.

        Returns:
            JSON response text, or None if unavailable.
        """
        if not self._api_key:
            return None
        try:
            # Extract article number from URL if possible
            article_number = None
            if "document/" in url:
                parts = url.split("document/")
                if len(parts) > 1:
                    article_number = parts[1].strip("/").split("/")[0].split("?")[0]

            if article_number:
                api_url = f"{self.API_BASE}/articles/{article_number}"
                params = {"apikey": self._api_key}
            else:
                # Fall back to search by DOI
                doi = url.split("doi.org/", 1)[1] if "doi.org/" in url else url
                api_url = f"{self.API_BASE}/articles"
                params = {"apikey": self._api_key, "doi": doi}

            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(api_url, params=params)
                if resp.status_code == 200:
                    return resp.text
                logger.debug("IEEEHandler: HTTP %d for %s", resp.status_code, api_url)
        except Exception as exc:
            logger.debug("IEEEHandler fetch error for %s: %s", url, exc)
        return None
