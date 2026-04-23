"""ACM Digital Library platform handler."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from .base_platform import BasePlatformHandler

logger = logging.getLogger("aria")


class ACMHandler(BasePlatformHandler):
    """Handler for ACM Digital Library (institutional access)."""

    BASE_URL = "https://dl.acm.org"

    def __init__(self) -> None:
        super().__init__()
        self._cookies: dict = {}
        self._headers: dict = {
            "User-Agent": "Mozilla/5.0 (compatible; ARIA Research Collector/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        }

    async def authenticate(self, credentials: dict) -> bool:
        """Set session cookies for institutional access.

        Args:
            credentials: Dict with optional 'session_cookie' key.

        Returns:
            True (ACM uses institutional network access, not credential auth).
        """
        if "session_cookie" in credentials:
            self._cookies = {"JSESSIONID": credentials["session_cookie"]}
        self._authenticated = True
        logger.debug("ACMHandler: authentication configured (institutional access)")
        return True

    async def fetch(self, url: str) -> Optional[str]:
        """Fetch content from ACM Digital Library.

        Args:
            url: ACM article URL.

        Returns:
            HTML content of the page, or None if fetch fails.
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
                    return resp.text
                logger.debug("ACMHandler: HTTP %d for %s", resp.status_code, url)
        except Exception as exc:
            logger.debug("ACMHandler fetch error for %s: %s", url, exc)
        return None
