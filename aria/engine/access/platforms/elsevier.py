"""Elsevier ScienceDirect platform handler."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from .base_platform import BasePlatformHandler

logger = logging.getLogger("aria")


class ElsevierHandler(BasePlatformHandler):
    """Handler for Elsevier ScienceDirect API."""

    API_BASE = "https://api.elsevier.com/content"

    def __init__(self) -> None:
        super().__init__()
        self._api_key: Optional[str] = None
        self._inst_token: Optional[str] = None

    async def authenticate(self, credentials: dict) -> bool:
        """Store Elsevier API credentials.

        Args:
            credentials: Dict with 'api_key' and optional 'inst_token'.

        Returns:
            True if api_key is provided.
        """
        self._api_key = credentials.get("api_key")
        self._inst_token = credentials.get("inst_token")
        if self._api_key:
            self._authenticated = True
            logger.debug("ElsevierHandler: authenticated with API key")
            return True
        logger.warning("ElsevierHandler: no api_key in credentials")
        return False

    async def fetch(self, url: str) -> Optional[str]:
        """Fetch article content from Elsevier API.

        Supports article DOI URLs and direct API URLs.

        Args:
            url: Article URL or DOI URL.

        Returns:
            Article full text XML/JSON, or None if unavailable.
        """
        if not self._api_key:
            return None
        try:
            headers = {
                "X-ELS-APIKey": self._api_key,
                "Accept": "application/json",
            }
            if self._inst_token:
                headers["X-ELS-Insttoken"] = self._inst_token

            # Try to extract DOI from URL
            doi = None
            if "doi.org/" in url:
                doi = url.split("doi.org/", 1)[1]
            elif "sciencedirect.com/science/article/pii/" in url:
                pii = url.split("pii/", 1)[1].split("?")[0].split("/")[0]
                api_url = f"{self.API_BASE}/article/pii/{pii}"
            else:
                api_url = url

            if doi:
                api_url = f"{self.API_BASE}/article/doi/{doi}"

            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(api_url, headers=headers)
                if resp.status_code == 200:
                    return resp.text
                logger.debug("ElsevierHandler: HTTP %d for %s", resp.status_code, api_url)
        except Exception as exc:
            logger.debug("ElsevierHandler fetch error for %s: %s", url, exc)
        return None
