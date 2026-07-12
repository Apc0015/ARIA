"""Web link crawler — follows outbound links from full-page scraped docs (depth-1).

Only processes docs that already have full-page content (word_count > 100).
Bare DDGS snippets are skipped.

Link extraction priority:
  1. Markdown links  [text](https://...)  — produced by Jina AI Reader
  2. Raw https:// URLs in plain text

Filtering:
  - Must be absolute http(s) URLs
  - Skip social/search/tracker domains
  - Skip fragment-only anchors (#section)
  - Deduplicate across all source docs in the run
  - Cap: max_per_doc links followed per source page, max_total across whole run
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from .search import _make_doc, _scrape, _MAX_CONCURRENT

logger = logging.getLogger("aria")

# ── Patterns ─────────────────────────────────────────────────────────────────

_MD_LINK_RE  = re.compile(r'\[([^\]]{0,120})\]\((https?://[^)\s]{10,})\)')
_RAW_URL_RE  = re.compile(r'(?<![(\["])(https?://[^\s<>"\')\]]{10,})', re.IGNORECASE)

# Domains we never want to crawl (social, search, CDN, tracking)
_SKIP_DOMAINS: frozenset[str] = frozenset({
    "twitter.com", "x.com", "facebook.com", "instagram.com",
    "linkedin.com", "youtube.com", "tiktok.com", "pinterest.com",
    "reddit.com",          # dedicated collector
    "google.com", "bing.com", "duckduckgo.com", "yahoo.com",
    "amazon.com", "ebay.com",
    "doi.org",             # handled by CitationAgent
    "arxiv.org",           # handled by CitationAgent
    "pubmed.ncbi.nlm.nih.gov",  # handled by CitationAgent
    "cdn.", "fonts.", "static.", "assets.",
    "javascript:", "mailto:", "tel:",
})

_SKIP_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".pdf",   # PDFCollector handles these
    ".zip", ".tar", ".gz", ".mp4", ".mp3", ".wav",
    ".css", ".js", ".woff", ".woff2",
})

# Path segments that indicate boilerplate/legal pages (not research content)
_SKIP_PATH_SEGMENTS = frozenset({
    "privacy", "privacy-policy", "terms", "terms-of-service", "terms-of-use",
    "cookie", "cookies", "legal", "disclaimer", "gdpr", "dmca",
    "login", "signin", "signup", "register", "subscribe", "newsletter",
    "cart", "checkout", "shop",
    "contact", "about-us", "careers", "jobs",
    "advertise", "advertising",
})


def _extract_links(doc: dict[str, Any], max_candidates: int = 10) -> list[str]:
    """Pull outbound URLs from a doc's full-page Markdown text."""
    from aria.utils.url import get_url_domain, normalize_url

    text = doc.get("text", "") or ""
    src  = doc.get("url", "") or ""

    raw: list[str] = []

    # Markdown links (Jina output) — higher quality, usually navigation-free
    for _label, url in _MD_LINK_RE.findall(text):
        raw.append(url)

    # Fallback: bare URLs in text
    for url in _RAW_URL_RE.findall(text):
        raw.append(url)

    seen: set[str] = set()
    good: list[str] = []

    # Base URL of the source doc (no fragment, no query)
    src_base = normalize_url(src)

    for url in raw:
        # Clean trailing punctuation Jina sometimes leaves
        url = url.rstrip(".,;)")
        # Must be absolute
        if not url.startswith(("http://", "https://")):
            continue
        url_no_frag = normalize_url(url)
        if not url_no_frag:
            continue
        # Drop same-page anchors (same base URL, different fragment)
        if url_no_frag == src_base or url_no_frag == src.rstrip("/"):
            continue
        # Skip known-bad domains
        domain = get_url_domain(url_no_frag)
        if not domain:
            continue
        if domain in _SKIP_DOMAINS:
            continue
        if any(domain.startswith(skip.rstrip(".")) for skip in _SKIP_DOMAINS if skip.endswith(".")):
            continue
        # Skip binary/media extensions
        path_lower = url_no_frag.lower()
        if any(path_lower.endswith(ext) for ext in _SKIP_EXTENSIONS):
            continue
        # Skip boilerplate path segments (check each segment for any skip keyword)
        path_parts = [p for p in path_lower.split("/") if p]
        if any(skip in part.replace("-", "_")
               for part in path_parts
               for skip in _SKIP_PATH_SEGMENTS):
            continue
        # Use de-fragmented URL for dedup and crawling
        url = url_no_frag
        if url in seen:
            continue
        seen.add(url)
        good.append(url)
        if len(good) >= max_candidates:
            break

    return good


async def crawl_links(
    docs: list[dict[str, Any]],
    max_per_doc: int = 2,
    max_total: int = 20,
    seen_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Follow outbound links from scraped pages and return new documents.

    Args:
        docs:         Source documents (from collection phase).
        max_per_doc:  Max links to follow per source document.
        max_total:    Hard cap on total links followed in this call.
        seen_urls:    Already-collected URLs to skip (updated in-place).

    Returns:
        List of new documents (``source_type='web_link_follow'``).
        Empty list if no useful links found.
    """
    from aria.utils.url import normalize_url

    if seen_urls is None:
        seen_urls = set()
        for d in docs:
            n = normalize_url(d.get("url", ""))
            if n:
                seen_urls.add(n)

    sem = asyncio.Semaphore(_MAX_CONCURRENT)
    stubs: list[dict[str, Any]] = []

    for doc in docs:
        # Only follow links from full-page docs — snippets have no meaningful links
        if (doc.get("word_count") or 0) < 100:
            continue

        candidates = _extract_links(doc, max_candidates=max_per_doc * 3)
        added = 0
        for url in candidates:
            if len(stubs) >= max_total:
                break
            if url in seen_urls:
                continue
            seen_urls.add(url)
            stubs.append(_make_doc(
                url=url,
                title="",
                text="",
                source_type="web_link_follow",
                platform="link_crawler",
                metadata={
                    "source_doc": doc.get("url", ""),
                    "crawl_depth": 1,
                },
            ))
            added += 1
            if added >= max_per_doc:
                break

    if not stubs:
        logger.debug("WebLinkCrawler: no eligible links found in %d docs", len(docs))
        return []

    logger.info("WebLinkCrawler: scraping %d outbound links", len(stubs))
    enriched = await asyncio.gather(*[_scrape(s, sem) for s in stubs])

    # Drop pages that yielded no content after scraping
    result = [d for d in enriched if (d.get("word_count") or 0) > 50]
    logger.info(
        "WebLinkCrawler: %d/%d links returned content",
        len(result), len(stubs),
    )
    return result
