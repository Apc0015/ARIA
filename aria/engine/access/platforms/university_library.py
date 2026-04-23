"""University library EZproxy handler."""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import quote

import httpx

from .base_platform import BasePlatformHandler

logger = logging.getLogger("aria")


class UniversityProxyHandler(BasePlatformHandler):
    """Handler for university library EZproxy or similar institutional proxies.

    Rewrites URLs through the proxy to enable authenticated access to
    paywalled resources using institutional credentials.
    """

    def __init__(self) -> None:
        super().__init__()
        self._proxy_url: Optional[str] = None
        self._username: Optional[str] = None
        self._password: Optional[str] = None
        self._session_cookies: dict = {}

    async def authenticate(self, credentials: dict) -> bool:
        """Configure the proxy connection.

        Args:
            credentials: Dict with 'proxy_url', and optionally 'username' and 'password'.

        Returns:
            True if proxy_url is provided.
        """
        self._proxy_url = credentials.get("proxy_url", "").rstrip("/")
        self._username = credentials.get("username")
        self._password = credentials.get("password")

        if not self._proxy_url:
            logger.warning("UniversityProxyHandler: no proxy_url configured")
            return False

        # If credentials provided, attempt to establish authenticated session
        if self._username and self._password:
            try:
                await self._login()
            except Exception as exc:
                logger.debug("UniversityProxyHandler: login attempt failed: %s", exc)

        self._authenticated = bool(self._proxy_url)
        logger.debug("UniversityProxyHandler: proxy configured at %s", self._proxy_url)
        return self._authenticated

    async def _login(self) -> None:
        """Attempt to authenticate with the proxy."""
        login_url = f"{self._proxy_url}/login"
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.post(
                login_url,
                data={"user": self._username, "pass": self._password},
            )
            # Store any session cookies returned
            self._session_cookies = dict(resp.cookies)
            logger.debug("UniversityProxyHandler: login response HTTP %d", resp.status_code)

    def _proxify_url(self, url: str) -> str:
        """Rewrite a URL through the EZproxy."""
        if not self._proxy_url:
            return url
        # Standard EZproxy URL format
        return f"{self._proxy_url}/login?url={quote(url, safe='')}"

    async def fetch(self, url: str) -> Optional[str]:
        """Fetch URL content through the institutional proxy.

        Args:
            url: Original resource URL.

        Returns:
            Page content, or None if unavailable.
        """
        if not self._proxy_url:
            return None
        try:
            proxied_url = self._proxify_url(url)
            headers = {"User-Agent": "Mozilla/5.0 (compatible; ARIA Research Collector/1.0)"}
            async with httpx.AsyncClient(
                cookies=self._session_cookies,
                headers=headers,
                timeout=25,
                follow_redirects=True,
            ) as client:
                resp = await client.get(proxied_url)
                if resp.status_code == 200:
                    return resp.text
                logger.debug("UniversityProxyHandler: HTTP %d for %s", resp.status_code, proxied_url)
        except Exception as exc:
            logger.debug("UniversityProxyHandler fetch error for %s: %s", url, exc)
        return None
