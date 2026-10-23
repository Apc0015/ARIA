"""Web scraper collector - fetches and parses full page content.

Uses Camofox anti-detection browser when CAMOFOX_URL is set, falling back
to plain aiohttp for unblocked sites (faster, no extra infra needed).
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import AsyncGenerator, Any, Optional
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

from .base import BaseCollector
from ...utils.camofox import get_client as _camofox

try:
    from crawl4ai import AsyncWebCrawler  # type: ignore
    _CRAWL4AI_AVAILABLE = True
except ImportError:
    _CRAWL4AI_AVAILABLE = False
    logging.getLogger("aria").info(
        "crawl4ai not installed — JS-heavy pages fall back to "
        "Playwright/Wayback. Enable with: pip install crawl4ai>=0.6.0"
    )

logger = logging.getLogger("aria")

# Domains known to block plain HTTP scrapers — route through Camofox
_BLOCKED_DOMAINS = {
    "bloomberg.com", "wsj.com", "ft.com", "nytimes.com",
    "washingtonpost.com", "thetimes.co.uk", "economist.com",
    "linkedin.com", "reuters.com", "apnews.com",
    "cloudflare.com",  # anything behind CF
}

_REMOVE_TAGS = {
    "script", "style", "nav", "header", "footer", "aside",
    "advertisement", "ads", "cookie", "banner", "popup",
    "noscript", "iframe", "form",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class WebScraperCollector(BaseCollector):
    """Fetches full page content from URLs using aiohttp + BeautifulSoup."""

    def __init__(
        self,
        timeout: int = 20,
        max_concurrent: int = 5,
        delay: float = 0.5,
    ) -> None:
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._max_concurrent = max_concurrent
        self._delay = delay
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Scrape URLs provided as queries.

        When queries are full URLs, fetches them directly.
        When queries are search terms, this collector is a no-op
        (use WebSearchCollector to discover URLs first).

        Args:
            queries: List of URLs to scrape.

        Yields:
            Document dicts with source_type='web_page'.
        """
        for url in queries:
            from aria.utils.url import is_safe_public_http_url

            if not is_safe_public_http_url(url):
                continue
            try:
                doc = await self.scrape_url(url)
                if doc:
                    yield doc
                await asyncio.sleep(self._delay)
            except Exception as exc:
                logger.warning("WebScraperCollector: error scraping %s: %s", url, exc)

    async def scrape_url(self, url: str) -> Optional[dict[str, Any]]:
        """Fetch and extract main text from a URL.

        Routes through Camofox when:
          - CAMOFOX_URL is set AND
          - domain is in _BLOCKED_DOMAINS OR plain fetch returns 403/429

        Args:
            url: Page URL to scrape.

        Returns:
            Document dict, or None on failure.
        """
        from aria.utils.robots import allowed_async
        from aria.utils.url import is_safe_public_http_destination

        if not await is_safe_public_http_destination(url):
            logger.warning("WebScraperCollector: blocked unsafe URL %s", url)
            return None
        if not await allowed_async(url):
            return None

        async with self._semaphore:
            domain = urlparse(url).netloc
            camofox = _camofox()

            # Camofox anti-detection browser for sites that block standard requests
            if camofox.available and any(d in domain for d in _BLOCKED_DOMAINS):
                doc = await self._scrape_via_camofox(url, domain, camofox)
                if doc:
                    return doc
                # fall through to plain aiohttp

            # Plain aiohttp: fast path for cooperative sites
            doc = await self._scrape_plain(url, domain)
            if doc:
                return doc

            # Jina AI Reader: proxy-based extraction bypasses JS blocks, no key needed
            doc = await self._scrape_jina(url, domain)
            if doc:
                return doc

            # crawl4ai: full JS rendering with Markdown output (install crawl4ai to enable)
            if _CRAWL4AI_AVAILABLE:
                doc = await self._scrape_crawl4ai(url, domain)
                if doc:
                    return doc

            # Retry Camofox as last resort for non-blocked domains that failed all other paths
            if camofox.available and not any(d in domain for d in _BLOCKED_DOMAINS):
                logger.debug("WebScraper: trying Camofox as last resort for %s", url)
                return await self._scrape_via_camofox(url, domain, camofox)

            return None

    async def _scrape_plain(self, url: str, domain: str) -> Optional[dict[str, Any]]:
        """Fetch via plain aiohttp."""
        try:
            connector = aiohttp.TCPConnector()
            async with aiohttp.ClientSession(
                headers=_HEADERS,
                connector=connector,
                timeout=self._timeout,
            ) as session:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status in (403, 429, 503):
                        logger.debug("WebScraper: HTTP %d (likely blocked) for %s", resp.status, url)
                        return None
                    if resp.status != 200:
                        return None
                    content_type = resp.content_type or ""
                    is_text = "text" in content_type or "html" in content_type
                    if not is_text:
                        # Office / PDF / EPUB / JSON → try MarkItDown conversion
                        from aria.engine.utils.markitdown_adapter import convert_bytes, is_supported
                        fname = url.rsplit("/", 1)[-1] or "document"
                        if not is_supported(fname):
                            # Synthesise extension from content-type
                            _CT_EXT = {
                                "application/pdf": ".pdf",
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                                "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
                                "application/msword": ".doc",
                                "application/vnd.ms-excel": ".xls",
                                "application/vnd.ms-powerpoint": ".ppt",
                                "application/epub+zip": ".epub",
                            }
                            ext = _CT_EXT.get(content_type.split(";", 1)[0].strip(), "")
                            if not ext:
                                return None
                            fname = f"{fname}{ext}"
                        data = await resp.read()
                        md_text = convert_bytes(data, fname)
                        if len(md_text.strip()) < 100:
                            return None
                        return _make_doc(url, fname, md_text, domain)
                    html = await resp.text(errors="replace")

            text, title = _extract_text(html)
            if not text or len(text.strip()) < 100:
                return None

            return _make_doc(url, title, text, domain)
        except asyncio.TimeoutError:
            logger.debug("WebScraper: timeout %s", url)
        except Exception as exc:
            logger.debug("WebScraper: error %s: %s", url, exc)
        return None

    async def _scrape_via_camofox(
        self, url: str, domain: str, camofox: Any
    ) -> Optional[dict[str, Any]]:
        """Fetch via Camofox anti-detection browser."""
        try:
            result = await camofox.fetch_page(url)
            text = result.get("text", "")
            title = result.get("title", "")
            if not text or len(text.strip()) < 80:
                return None
            logger.debug("WebScraper: Camofox OK for %s (%d chars)", url, len(text))
            return _make_doc(url, title, text, domain, via_camofox=True)
        except Exception as exc:
            logger.debug("WebScraper: Camofox error %s: %s", url, exc)
        return None

    async def _scrape_jina(self, url: str, domain: str) -> Optional[dict[str, Any]]:
        """Jina AI Reader: proxy-based extraction, no API key needed.

        Fetches https://r.jina.ai/{url} which returns clean Markdown.
        """
        try:
            jina_url = f"https://r.jina.ai/{url}"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    jina_url,
                    timeout=aiohttp.ClientTimeout(total=20),
                    headers={"User-Agent": "ARIA-Research-Bot/5.0"},
                ) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        if len(text) > 100:
                            logger.debug("WebScraper(jina): OK for %s (%d chars)", url, len(text))
                            return _make_doc(url, "", text, domain)
        except Exception as exc:
            logger.debug("WebScraper(jina): error for %s: %s", url, exc)
        return None

    async def _scrape_crawl4ai(self, url: str, domain: str) -> Optional[dict[str, Any]]:
        """crawl4ai: JS-aware crawling with Markdown output.

        Preferred over retry-Camofox when available; requires crawl4ai package.
        """
        if not _CRAWL4AI_AVAILABLE:
            return None
        try:
            async with AsyncWebCrawler() as crawler:  # type: ignore[name-defined]
                result = await crawler.arun(url=url)
                if result.success and result.markdown:
                    title = ""
                    if result.metadata:
                        title = result.metadata.get("title", "")
                    logger.debug("WebScraper(crawl4ai): OK for %s (%d chars)", url, len(result.markdown))
                    return _make_doc(url, title, result.markdown, domain)
        except Exception as exc:
            logger.debug("WebScraper(crawl4ai): error for %s: %s", url, exc)
        return None


def _make_doc(
    url: str,
    title: str,
    text: str,
    domain: str,
    via_camofox: bool = False,
) -> dict[str, Any]:
    return {
        "url": url,
        "title": title,
        "text": text,
        "source_type": "web_page",
        "platform": domain,
        "language": "en",
        "word_count": len(text.split()),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {"domain": domain, "via_camofox": via_camofox},
    }


def _extract_text(html: str) -> tuple[str, str]:
    """Parse HTML and extract main text content and title.

    Returns:
        Tuple of (main_text, title).
    """
    soup = BeautifulSoup(html, "lxml")

    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
    og_title = soup.find("meta", {"property": "og:title"})
    if og_title and og_title.get("content"):
        title = og_title["content"]

    # Remove noise tags
    for tag_name in _REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Try to find main content area
    main = (
        soup.find("article")
        or soup.find("main")
        or soup.find(id=re.compile(r"content|main|article", re.I))
        or soup.find(class_=re.compile(r"content|main|article|post-body|entry", re.I))
        or soup.find("body")
    )

    if not main:
        main = soup

    # Extract paragraphs
    paragraphs = []
    for elem in main.find_all(["p", "h1", "h2", "h3", "h4", "li", "blockquote"]):
        text = elem.get_text(separator=" ", strip=True)
        if len(text) > 30:
            paragraphs.append(text)

    if not paragraphs:
        paragraphs = [main.get_text(separator="\n", strip=True)]

    text = "\n\n".join(paragraphs)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip(), title
