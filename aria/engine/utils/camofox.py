"""Camofox anti-detection browser client.

Wraps the Camofox REST API (https://github.com/jo-inc/camofox-browser).
Falls back gracefully when CAMOFOX_URL is not set — callers always check
`client.available` before using.

Environment variables:
    CAMOFOX_URL      Base URL of running Camofox server, e.g. http://localhost:3000
    CAMOFOX_API_KEY  Bearer token (optional, only if server requires auth)
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any

import httpx

logger = logging.getLogger("aria.camofox")

_DEFAULT_USER_ID = "aria-collector"

# Search macro map — Camofox built-in shortcuts
_SEARCH_MACROS: dict[str, str] = {
    "google":    "@google_search",
    "youtube":   "@youtube_search",
    "reddit":    "@reddit_search",
    "wikipedia": "@wikipedia_search",
    "linkedin":  "@linkedin_search",
    "twitter":   "@twitter_search",
    "amazon":    "@amazon_search",
}


class CamofoxClient:
    """Async client for the Camofox anti-detection browser REST API.

    Usage (one-shot page fetch)::

        client = CamofoxClient()
        if client.available:
            result = await client.fetch_page("https://example.com")
            text  = result["text"]
            links = result["links"]

    Usage (persistent tab for auth flows)::

        async with client.tab(user_id="aria-linkedin") as tab:
            await tab.navigate("https://linkedin.com/login")
            await tab.type("e1", "user@example.com")
            await tab.type("e2", "password")
            await tab.click("e3")           # submit
            snapshot = await tab.snapshot()
    """

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("CAMOFOX_URL", "")).rstrip("/")
        self.api_key  = api_key  or os.getenv("CAMOFOX_API_KEY", "")
        self.timeout  = timeout
        self.available = bool(self.base_url)

    # ── Internal ────────────────────────────────────────────────

    @property
    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, headers=self._headers)

    # ── Health ───────────────────────────────────────────────────

    async def health(self) -> bool:
        """Return True if Camofox server is reachable."""
        if not self.available:
            return False
        try:
            async with self._client() as c:
                r = await c.get(f"{self.base_url}/health")
                return r.status_code == 200
        except Exception:
            return False

    # ── One-shot page fetch ──────────────────────────────────────

    async def fetch_page(
        self,
        url: str,
        user_id: str = _DEFAULT_USER_ID,
        wait_seconds: float = 2.5,
    ) -> dict[str, Any]:
        """Fetch a page through Camofox and return text + links.

        Creates a tab, waits for JS to render, extracts accessibility
        snapshot and all links, then closes the tab.

        Returns:
            {
                "url":      str,
                "title":    str,
                "text":     str,   # accessibility snapshot (~90% smaller than HTML)
                "links":    list[dict],   # [{text, href}, ...]
                "snapshot": str,   # raw Camofox snapshot string
            }

        Raises:
            RuntimeError: if Camofox not configured or tab creation fails.
            httpx.HTTPError: on network failure.
        """
        if not self.available:
            raise RuntimeError("Camofox not configured — set CAMOFOX_URL env var")

        session_key = str(uuid.uuid4())
        tab_id: str | None = None

        async with self._client() as c:
            # Create tab
            resp = await c.post(
                f"{self.base_url}/tabs",
                json={"userId": user_id, "sessionKey": session_key, "url": url},
            )
            resp.raise_for_status()
            tab_id = resp.json().get("id") or resp.json().get("tabId")
            if not tab_id:
                raise RuntimeError(f"Camofox: no tab ID in response: {resp.text}")

            logger.debug("Camofox tab %s → %s", tab_id, url)

            try:
                # Wait for JS rendering
                await asyncio.sleep(wait_seconds)

                # Accessibility snapshot
                snap_r = await c.get(
                    f"{self.base_url}/tabs/{tab_id}/snapshot",
                    params={"userId": user_id},
                )
                snap_data = snap_r.json() if snap_r.status_code == 200 else {}
                snapshot  = snap_data.get("snapshot", "")
                title     = snap_data.get("title", "")

                # Links
                links_r = await c.get(
                    f"{self.base_url}/tabs/{tab_id}/links",
                    params={"userId": user_id},
                )
                links = links_r.json().get("links", []) if links_r.status_code == 200 else []

                return {
                    "url":      url,
                    "title":    title,
                    "text":     snapshot,
                    "links":    links,
                    "snapshot": snapshot,
                }

            finally:
                if tab_id:
                    try:
                        await c.delete(
                            f"{self.base_url}/tabs/{tab_id}",
                            params={"userId": user_id},
                        )
                    except Exception:
                        pass  # best-effort cleanup

    # ── Search via macro ─────────────────────────────────────────

    async def search(
        self,
        query: str,
        engine: str = "google",
        user_id: str = _DEFAULT_USER_ID,
        max_links: int = 20,
    ) -> list[dict[str, str]]:
        """Run a search macro and return result links.

        Args:
            query:  Search query string.
            engine: One of google / youtube / reddit / wikipedia / linkedin /
                    twitter / amazon.  Defaults to google.
            user_id: Camofox session user ID.
            max_links: Max links to return from SERP.

        Returns:
            List of {"text": ..., "href": ...} dicts.
        """
        if not self.available:
            raise RuntimeError("Camofox not configured")

        macro = _SEARCH_MACROS.get(engine, "@google_search")
        session_key = str(uuid.uuid4())
        tab_id: str | None = None

        async with self._client() as c:
            # Create tab
            resp = await c.post(
                f"{self.base_url}/tabs",
                json={"userId": user_id, "sessionKey": session_key, "url": "about:blank"},
            )
            resp.raise_for_status()
            tab_id = resp.json().get("id") or resp.json().get("tabId")

            try:
                # Navigate with macro
                await c.post(
                    f"{self.base_url}/tabs/{tab_id}/navigate",
                    json={"userId": user_id, "macro": macro, "query": query},
                )
                await asyncio.sleep(2.5)

                # Extract links
                links_r = await c.get(
                    f"{self.base_url}/tabs/{tab_id}/links",
                    params={"userId": user_id},
                )
                links = links_r.json().get("links", []) if links_r.status_code == 200 else []
                return links[:max_links]

            finally:
                if tab_id:
                    try:
                        await c.delete(
                            f"{self.base_url}/tabs/{tab_id}",
                            params={"userId": user_id},
                        )
                    except Exception:
                        pass

    # ── YouTube transcript ───────────────────────────────────────

    async def youtube_transcript(
        self,
        url: str,
        languages: list[str] | None = None,
    ) -> dict[str, Any]:
        """Extract YouTube transcript via Camofox yt-dlp integration.

        Returns:
            {"transcript": str, "video_title": str, "total_words": int}
        """
        if not self.available:
            raise RuntimeError("Camofox not configured")

        async with self._client() as c:
            resp = await c.post(
                f"{self.base_url}/youtube/transcript",
                json={"url": url, "languages": languages or ["en"]},
            )
            resp.raise_for_status()
            return resp.json()

    # ── Persistent tab context manager ───────────────────────────

    def tab(
        self,
        user_id: str = _DEFAULT_USER_ID,
        initial_url: str = "about:blank",
    ) -> "_TabContext":
        """Return an async context manager for a persistent Camofox tab.

        Usage::
            async with client.tab(user_id="aria-linkedin") as tab:
                await tab.navigate("https://linkedin.com/login")
                await tab.type("e1", email)
                await tab.click("e3")
                snap = await tab.snapshot()
        """
        return _TabContext(self, user_id=user_id, initial_url=initial_url)


# ── Persistent tab helper ────────────────────────────────────────────────────

class _TabContext:
    """Async context manager wrapping a live Camofox browser tab."""

    def __init__(
        self,
        client: CamofoxClient,
        user_id: str,
        initial_url: str,
    ) -> None:
        self._client    = client
        self._user_id   = user_id
        self._url       = initial_url
        self._tab_id: str | None = None
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "_TabContext":
        self._http = httpx.AsyncClient(
            timeout=self._client.timeout,
            headers=self._client._headers,
        )
        resp = await self._http.post(
            f"{self._client.base_url}/tabs",
            json={
                "userId":     self._user_id,
                "sessionKey": str(uuid.uuid4()),
                "url":        self._url,
            },
        )
        resp.raise_for_status()
        self._tab_id = resp.json().get("id") or resp.json().get("tabId")
        await asyncio.sleep(1.5)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._tab_id and self._http:
            try:
                await self._http.delete(
                    f"{self._client.base_url}/tabs/{self._tab_id}",
                    params={"userId": self._user_id},
                )
            except Exception:
                pass
        if self._http:
            await self._http.aclose()

    def _base(self) -> str:
        return f"{self._client.base_url}/tabs/{self._tab_id}"

    async def navigate(self, url: str) -> None:
        """Navigate tab to URL."""
        await self._http.post(  # type: ignore[union-attr]
            f"{self._base()}/navigate",
            json={"userId": self._user_id, "url": url},
        )
        await asyncio.sleep(2.0)

    async def search(self, query: str, engine: str = "google") -> None:
        """Navigate using a search macro."""
        macro = _SEARCH_MACROS.get(engine, "@google_search")
        await self._http.post(  # type: ignore[union-attr]
            f"{self._base()}/navigate",
            json={"userId": self._user_id, "macro": macro, "query": query},
        )
        await asyncio.sleep(2.5)

    async def click(self, ref: str) -> None:
        await self._http.post(  # type: ignore[union-attr]
            f"{self._base()}/click",
            json={"userId": self._user_id, "ref": ref},
        )
        await asyncio.sleep(0.8)

    async def type(self, ref: str, text: str, press_enter: bool = False) -> None:
        await self._http.post(  # type: ignore[union-attr]
            f"{self._base()}/type",
            json={"userId": self._user_id, "ref": ref, "text": text, "pressEnter": press_enter},
        )
        await asyncio.sleep(0.4)

    async def snapshot(self) -> str:
        """Return accessibility snapshot string."""
        r = await self._http.get(  # type: ignore[union-attr]
            f"{self._base()}/snapshot",
            params={"userId": self._user_id},
        )
        return r.json().get("snapshot", "") if r.status_code == 200 else ""

    async def links(self) -> list[dict[str, str]]:
        """Return all links on current page."""
        r = await self._http.get(  # type: ignore[union-attr]
            f"{self._base()}/links",
            params={"userId": self._user_id},
        )
        return r.json().get("links", []) if r.status_code == 200 else []

    async def wait(self, selector: str = "", ms: int = 1000) -> None:
        payload: dict[str, Any] = {"userId": self._user_id}
        if selector:
            payload["selector"] = selector
        else:
            payload["timeout"] = ms
        await self._http.post(f"{self._base()}/wait", json=payload)  # type: ignore[union-attr]


# ── Module-level singleton (shared across collectors) ────────────────────────

_shared: CamofoxClient | None = None


def get_client() -> CamofoxClient:
    """Return the shared module-level CamofoxClient instance."""
    global _shared
    if _shared is None:
        _shared = CamofoxClient()
    return _shared
