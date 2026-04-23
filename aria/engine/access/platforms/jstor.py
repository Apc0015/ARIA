"""JSTOR platform handler."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from .base_platform import BasePlatformHandler

logger = logging.getLogger("aria")


class JSTORHandler(BasePlatformHandler):
    """Handler for JSTOR (institutional or Constellate API access)."""

    BASE_URL = "https://www.jstor.org"
    CONSTELLATE_BASE = "https://constellate.org/api"

    def __init__(self) -> None:
        super().__init__()
        self._cookies: dict = {}
        self._api_key: Optional[str] = None
        self._headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ARIA Research Collector/1.0)",
        }

    async def authenticate(self, credentials: dict) -> bool:
        """Configure JSTOR access credentials.

        Args:
            credentials: Dict with optional 'session_cookie' and/or 'api_key'.

        Returns:
            True always (JSTOR may require institutional access).
        """
        if "session_cookie" in credentials:
            self._cookies = {"JSESSID": credentials["session_cookie"]}
        if "api_key" in credentials:
            self._api_key = credentials["api_key"]
        self._authenticated = True
        logger.debug("JSTORHandler: authentication configured")
        return True

    async def fetch(self, url: str) -> Optional[str]:
        """Fetch content from JSTOR.

        Args:
            url: JSTOR article URL.

        Returns:
            HTML content, or None if fetch fails or access denied.
        """
        try:
            async with httpx.AsyncClient(
                cookies=self._cookies,
                headers=self._headers,
                timeout=20,
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    # JSTOR often returns paywall page; check for content
                    text = resp.text
                    if "login" in resp.url.path.lower() or "signin" in resp.url.path.lower():
                        logger.debug("JSTORHandler: redirected to login for %s", url)
                        return None
                    return text
                logger.debug("JSTORHandler: HTTP %d for %s", resp.status_code, url)
        except Exception as exc:
            logger.debug("JSTORHandler fetch error for %s: %s", url, exc)
        return None
