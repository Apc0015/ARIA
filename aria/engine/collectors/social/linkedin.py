"""LinkedIn collector — Camofox auth (preferred) → Playwright → public fallback."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

from .base import BaseCollector
from ..utils.camofox import get_client as _camofox

logger = logging.getLogger("aria")

# LinkedIn content search URL (requires cookies to return useful results)
_LI_SEARCH_URL = "https://www.linkedin.com/search/results/content/?keywords={query}&origin=GLOBAL_SEARCH_HEADER"
# LinkedIn Pulse public articles (accessible without auth)
_LI_PULSE_PATTERN = "linkedin.com/pulse"


class LinkedInCollector(BaseCollector):
    """Collects LinkedIn posts and articles.

    Auth flow:
    1. If LINKEDIN_EMAIL + LINKEDIN_PASSWORD are set:
       a. Load saved Playwright session cookies (if any) from SessionManager
       b. If no saved session: trigger Playwright login via SessionManager
       c. Use cookies to scrape linkedin.com/search
       d. On block (403 / redirect to login): fall back to public with warning
    2. No credentials: DuckDuckGo site:linkedin.com/pulse fallback
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        email = os.getenv("LINKEDIN_EMAIL", "")
        password = os.getenv("LINKEDIN_PASSWORD", "")
        camofox = _camofox()

        if email and password and camofox.available:
            # Preferred: Camofox anti-detection browser — survives LinkedIn bot checks
            logger.info("LinkedInCollector: using Camofox auth path")
            async for doc in self._collect_via_camofox(queries, email, password, camofox):
                yield doc
        elif email and password:
            # Fallback: Playwright session manager
            async for doc in self._collect_authenticated(queries, email, password):
                yield doc
        else:
            async for doc in self._collect_public(queries):
                yield doc

    # ------------------------------------------------------------------
    # Camofox auth path (preferred when CAMOFOX_URL set)
    # ------------------------------------------------------------------

    async def _collect_via_camofox(
        self, queries: list[str], email: str, password: str, camofox: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Login via Camofox browser tab, then search LinkedIn."""
        seen_urls: set[str] = set()
        count = 0

        try:
            async with camofox.tab(user_id="aria-linkedin", initial_url="https://www.linkedin.com/login") as tab:
                await tab.wait(ms=2000)
                snap = await tab.snapshot()

                # Find email/password fields by ref and fill
                # Camofox snapshot format: [textbox e1] Email or phone [textbox e2] Password
                email_ref = _find_ref(snap, "email") or "e1"
                pass_ref  = _find_ref(snap, "password") or "e2"

                await tab.type(email_ref, email)
                await tab.type(pass_ref, password, press_enter=True)
                await tab.wait(ms=3000)

                snap_after = await tab.snapshot()
                if "feed" not in snap_after.lower() and "home" not in snap_after.lower():
                    logger.warning("LinkedInCollector Camofox: login may have failed — snap: %s", snap_after[:200])
                    async for doc in self._collect_public(queries):
                        yield doc
                    return

                logger.info("LinkedInCollector Camofox: logged in successfully")

                for query in queries:
                    if count >= self._max_results:
                        break
                    await tab.search(query, engine="linkedin")
                    links = await tab.links()

                    for link in links:
                        if count >= self._max_results:
                            break
                        href = link.get("href", "")
                        text = link.get("text", "")
                        if not href or "linkedin.com" not in href:
                            continue
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)
                        if len(text) < 15:
                            continue

                        yield {
                            "url": href,
                            "title": text[:200],
                            "text": text,
                            "source_type": "opinion_essay",
                            "platform": "linkedin",
                            "language": "en",
                            "word_count": len(text.split()),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "metadata": {"query": query, "collection_method": "camofox_auth"},
                        }
                        count += 1

                    await asyncio.sleep(1.0)

        except Exception as exc:
            logger.warning("LinkedInCollector Camofox: error: %s — falling back to public", exc)
            async for doc in self._collect_public(queries):
                yield doc

    # ------------------------------------------------------------------
    # Authenticated path
    # ------------------------------------------------------------------

    async def _collect_authenticated(
        self, queries: list[str], email: str, password: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Use Playwright-backed session cookies to scrape LinkedIn search."""
        import httpx

        try:
            from aria.engine.access.session_manager import get_session_manager
        except ImportError:
            logger.warning("LinkedInCollector: session_manager unavailable, using public")
            async for doc in self._collect_public(queries):
                yield doc
            return

        sm = get_session_manager()

        # Ensure we have a valid session
        if not sm.has_session("linkedin"):
            logger.info("LinkedInCollector: no saved session — attempting Playwright login")
            result = await sm.login("linkedin", {"email": email, "password": password})
            if not result.get("success"):
                logger.warning(
                    "LinkedInCollector: login failed (%s) — falling back to public",
                    result.get("message", "unknown error"),
                )
                async for doc in self._collect_public(queries):
                    yield doc
                return
            logger.info(
                "LinkedInCollector: %s", result.get("message", "authenticated")
            )

        cookies = sm.get_cookies_dict("linkedin")
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        seen_urls: set[str] = set()
        count = 0
        session_valid = True

        for query in queries:
            if count >= self._max_results or not session_valid:
                break
            try:
                url = _LI_SEARCH_URL.format(query=query.replace(" ", "%20"))
                async with httpx.AsyncClient(
                    cookies=cookies,
                    headers=headers,
                    timeout=20,
                    follow_redirects=True,
                ) as client:
                    resp = await client.get(url)

                # Detect session expiry / block
                if resp.status_code == 403 or "linkedin.com/login" in str(resp.url):
                    logger.warning(
                        "LinkedInCollector: session expired or blocked — "
                        "clearing session, falling back to public"
                    )
                    sm.clear_session("linkedin")
                    session_valid = False
                    break

                if resp.status_code != 200:
                    logger.debug(
                        "LinkedInCollector: HTTP %s for '%s'", resp.status_code, query
                    )
                    continue

                # Parse results from HTML
                docs = _parse_linkedin_html(resp.text, query)
                for doc in docs:
                    if count >= self._max_results:
                        break
                    if doc["url"] in seen_urls:
                        continue
                    seen_urls.add(doc["url"])
                    yield doc
                    count += 1

                await asyncio.sleep(1.5)  # LinkedIn rate-limiting is aggressive

            except Exception as exc:
                logger.warning(
                    "LinkedInCollector: authenticated scrape error for '%s': %s", query, exc
                )

        # Fall back to public for remaining quota if session failed
        if not session_valid and count < self._max_results:
            async for doc in self._collect_public(queries):
                if count >= self._max_results:
                    break
                if doc["url"] not in seen_urls:
                    seen_urls.add(doc["url"])
                    yield doc
                    count += 1

    # ------------------------------------------------------------------
    # Public fallback
    # ------------------------------------------------------------------

    async def _collect_public(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Search LinkedIn Pulse articles via DuckDuckGo (no auth needed)."""
        seen_urls: set[str] = set()
        count = 0

        for query in queries:
            if count >= self._max_results:
                break
            try:
                search_query = f"site:linkedin.com/pulse {query}"
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS

                results: list[dict] = []
                with DDGS() as ddgs:
                    for r in ddgs.text(search_query, max_results=5):
                        results.append(r)

                for result in results:
                    if count >= self._max_results:
                        break
                    url = result.get("href", "")
                    if not url or "linkedin.com" not in url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = result.get("title", "")
                    body = result.get("body", "")
                    text = f"{title}\n\n{body}".strip()
                    if len(text) < 30:
                        continue

                    yield {
                        "url": url,
                        "title": title,
                        "text": text,
                        "source_type": "opinion_essay",
                        "platform": "linkedin",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "query": query,
                            "collection_method": "public_search",
                        },
                    }
                    count += 1

                await asyncio.sleep(0.5)

            except Exception as exc:
                logger.warning(
                    "LinkedInCollector (public): error for '%s': %s", query, exc
                )


def _find_ref(snapshot: str, keyword: str) -> str | None:
    """Extract element ref (e.g. 'e1') for a field matching keyword in snapshot."""
    import re
    pattern = rf"\[(?:textbox|input)\s+(e\d+)\][^\[]*{re.escape(keyword)}"
    m = re.search(pattern, snapshot, re.IGNORECASE)
    if m:
        return m.group(1)
    # Also try reversed order: keyword before ref
    pattern2 = rf"{re.escape(keyword)}[^\[]*\[(e\d+)\]"
    m2 = re.search(pattern2, snapshot, re.IGNORECASE)
    return m2.group(1) if m2 else None


def _parse_linkedin_html(html: str, query: str) -> list[dict]:
    """Parse LinkedIn search result HTML into document dicts.

    LinkedIn renders search results as JSON-LD or HTML cards.
    We extract what we can without a full JS engine.
    """
    docs: list[dict] = []
    try:
        from bs4 import BeautifulSoup
        import json as _json

        soup = BeautifulSoup(html, "html.parser")

        # Try JSON-LD structured data first
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = _json.loads(script.string or "")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    url = item.get("url", "")
                    name = item.get("name", "") or item.get("headline", "")
                    description = item.get("description", "") or item.get("articleBody", "")
                    if not url or not name:
                        continue
                    text = f"{name}\n\n{description}".strip()
                    if len(text) < 30:
                        continue
                    docs.append({
                        "url": url,
                        "title": name,
                        "text": text[:4000],
                        "source_type": "opinion_essay",
                        "platform": "linkedin",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "query": query,
                            "collection_method": "authenticated_jsonld",
                        },
                    })
            except Exception:
                pass

        # Fallback: extract article cards from HTML
        if not docs:
            for card in soup.select(".search-result__info, .entity-result__content, article"):
                title_el = card.find(["h3", "h2", "a"])
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                link = title_el.get("href", "") if title_el.name == "a" else ""
                if not link:
                    link_el = card.find("a", href=True)
                    link = link_el["href"] if link_el else ""
                snippet_el = card.find(class_=lambda c: c and "snippet" in c.lower())
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                text = f"{title}\n\n{snippet}".strip()
                if not link or len(text) < 20:
                    continue
                docs.append({
                    "url": link if link.startswith("http") else f"https://www.linkedin.com{link}",
                    "title": title,
                    "text": text,
                    "source_type": "opinion_essay",
                    "platform": "linkedin",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "query": query,
                        "collection_method": "authenticated_html",
                    },
                })

    except Exception as exc:
        logger.debug("LinkedInCollector: HTML parse error: %s", exc)

    return docs
