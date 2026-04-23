"""Academic platform collector — IEEE Xplore, Elsevier, Springer, JSTOR, ACM."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from urllib.parse import quote

import httpx

from .base import BaseCollector
from aria.engine.access.paywall_resolver import PaywallResolver

logger = logging.getLogger("aria")

_IEEE_SEARCH = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
_ELSEVIER_SEARCH = "https://api.elsevier.com/content/search/sciencedirect"
_SPRINGER_SEARCH = "https://api.springernature.com/meta/v2/json"


class AcademicPlatformsCollector(BaseCollector):
    """Collects academic papers from subscription-based platforms.

    Activated by environment variables:
    - IEEE_API_KEY       → IEEE Xplore API
    - ELSEVIER_API_KEY   → Elsevier ScienceDirect API
    - SPRINGER_API_KEY   → Springer Nature API
    - JSTOR_SESSION_COOKIE  → JSTOR (search via DDG + fetch with cookie)
    - ACM_SESSION_COOKIE    → ACM DL (search via DDG + fetch with cookie)

    PaywallResolver is used to find open-access versions of any located DOIs.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results
        self._ieee_key = os.getenv("IEEE_API_KEY", "")
        self._elsevier_key = os.getenv("ELSEVIER_API_KEY", "")
        self._springer_key = os.getenv("SPRINGER_API_KEY", "")
        self._jstor_cookie = os.getenv("JSTOR_SESSION_COOKIE", "")
        self._acm_cookie = os.getenv("ACM_SESSION_COOKIE", "")
        self._resolver = PaywallResolver()

    async def validate(self) -> bool:
        has_any = any([
            self._ieee_key,
            self._elsevier_key,
            self._springer_key,
            self._jstor_cookie,
            self._acm_cookie,
        ])
        if not has_any:
            logger.info(
                "AcademicPlatformsCollector: no credentials set — "
                "set IEEE_API_KEY, ELSEVIER_API_KEY, SPRINGER_API_KEY, "
                "JSTOR_SESSION_COOKIE, or ACM_SESSION_COOKIE"
            )
        return has_any

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Collect academic papers from all configured platforms.

        Args:
            queries: Research query strings.

        Yields:
            Document dicts with source_type='academic_paper',
            platform='academic_platforms'.
        """
        seen_urls: set[str] = set()
        count = 0

        for query in queries[:4]:
            if count >= self._max_results:
                break

            if self._ieee_key:
                async for doc in self._search_ieee(query, seen_urls):
                    if count >= self._max_results:
                        break
                    yield doc
                    count += 1

            if self._elsevier_key and count < self._max_results:
                async for doc in self._search_elsevier(query, seen_urls):
                    if count >= self._max_results:
                        break
                    yield doc
                    count += 1

            if self._springer_key and count < self._max_results:
                async for doc in self._search_springer(query, seen_urls):
                    if count >= self._max_results:
                        break
                    yield doc
                    count += 1

            if self._jstor_cookie and count < self._max_results:
                async for doc in self._search_jstor(query, seen_urls):
                    if count >= self._max_results:
                        break
                    yield doc
                    count += 1

            if self._acm_cookie and count < self._max_results:
                async for doc in self._search_acm(query, seen_urls):
                    if count >= self._max_results:
                        break
                    yield doc
                    count += 1

    async def _search_ieee(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Search IEEE Xplore API."""
        try:
            params = {
                "querytext": query,
                "apikey": self._ieee_key,
                "max_records": 10,
                "sort_field": "article_number",
                "sort_order": "desc",
            }
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(_IEEE_SEARCH, params=params)

            if resp.status_code == 401:
                logger.warning("AcademicPlatformsCollector: IEEE API key invalid (401)")
                return
            if resp.status_code != 200:
                logger.debug("AcademicPlatformsCollector: IEEE HTTP %s", resp.status_code)
                return

            data = resp.json()
            articles = data.get("articles", [])

            for article in articles:
                doi = article.get("doi", "")
                article_url = article.get("html_url", "") or article.get("pdf_url", "")
                if not article_url:
                    article_number = article.get("article_number", "")
                    article_url = f"https://ieeexplore.ieee.org/document/{article_number}" if article_number else ""
                if not article_url or article_url in seen_urls:
                    continue
                seen_urls.add(article_url)

                title = article.get("title", "")
                abstract = article.get("abstract", "") or ""
                authors = ", ".join(
                    a.get("full_name", "") for a in article.get("authors", {}).get("authors", [])[:5]
                )
                publication = article.get("publication_title", "")
                pub_year = article.get("publication_year", "")

                text = f"{title}\n\nAuthors: {authors}\nPublication: {publication} ({pub_year})\n\n{abstract}"
                text = text.strip()
                if len(text) < 30:
                    continue

                # Try to find open-access version
                oa_url = None
                if doi:
                    try:
                        oa_url = await self._resolver.resolve(article_url, doi)
                    except Exception:
                        pass

                yield {
                    "url": oa_url or article_url,
                    "title": title,
                    "text": text,
                    "source_type": "academic_paper",
                    "platform": "academic_platforms",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "provider": "ieee",
                        "doi": doi,
                        "authors": authors,
                        "publication": publication,
                        "year": pub_year,
                        "open_access_url": oa_url,
                        "query": query,
                    },
                }

            await asyncio.sleep(0.5)

        except Exception as exc:
            logger.warning(
                "AcademicPlatformsCollector: IEEE error for '%s': %s", query, exc
            )

    async def _search_elsevier(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Search Elsevier ScienceDirect API."""
        try:
            headers = {
                "X-ELS-APIKey": self._elsevier_key,
                "Accept": "application/json",
            }
            params = {
                "query": query,
                "count": 10,
                "field": "dc:title,prism:doi,dc:description,prism:publicationName,prism:coverDate,dc:creator",
            }
            async with httpx.AsyncClient(timeout=20, headers=headers) as client:
                resp = await client.get(_ELSEVIER_SEARCH, params=params)

            if resp.status_code == 401:
                logger.warning(
                    "AcademicPlatformsCollector: Elsevier API key invalid (401)"
                )
                return
            if resp.status_code != 200:
                logger.debug(
                    "AcademicPlatformsCollector: Elsevier HTTP %s", resp.status_code
                )
                return

            data = resp.json()
            results = (
                data.get("search-results", {}).get("entry", [])
            )

            for entry in results:
                doi = entry.get("prism:doi", "")
                link_list = entry.get("link", [])
                article_url = ""
                for lnk in link_list:
                    if lnk.get("@ref") == "scidir":
                        article_url = lnk.get("@href", "")
                        break
                if not article_url and doi:
                    article_url = f"https://doi.org/{doi}"
                if not article_url or article_url in seen_urls:
                    continue
                seen_urls.add(article_url)

                title = entry.get("dc:title", "")
                abstract = entry.get("dc:description", "") or ""
                author = entry.get("dc:creator", "")
                journal = entry.get("prism:publicationName", "")
                pub_date = entry.get("prism:coverDate", "")

                text = f"{title}\n\nAuthor: {author}\nJournal: {journal} ({pub_date})\n\n{abstract}"
                text = text.strip()
                if len(text) < 30:
                    continue

                oa_url = None
                if doi:
                    try:
                        oa_url = await self._resolver.resolve(article_url, doi)
                    except Exception:
                        pass

                yield {
                    "url": oa_url or article_url,
                    "title": title,
                    "text": text,
                    "source_type": "academic_paper",
                    "platform": "academic_platforms",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "provider": "elsevier",
                        "doi": doi,
                        "author": author,
                        "journal": journal,
                        "published": pub_date,
                        "open_access_url": oa_url,
                        "query": query,
                    },
                }

            await asyncio.sleep(0.5)

        except Exception as exc:
            logger.warning(
                "AcademicPlatformsCollector: Elsevier error for '%s': %s", query, exc
            )

    async def _search_springer(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Search Springer Nature API."""
        try:
            params = {
                "q": query,
                "p": 10,
                "api_key": self._springer_key,
            }
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(_SPRINGER_SEARCH, params=params)

            if resp.status_code == 401:
                logger.warning(
                    "AcademicPlatformsCollector: Springer API key invalid (401)"
                )
                return
            if resp.status_code != 200:
                logger.debug(
                    "AcademicPlatformsCollector: Springer HTTP %s", resp.status_code
                )
                return

            data = resp.json()
            records = data.get("records", [])

            for record in records:
                doi = record.get("doi", "")
                url = record.get("url", [{}])[0].get("value", "") if record.get("url") else ""
                if not url and doi:
                    url = f"https://doi.org/{doi}"
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                title = record.get("title", "")
                abstract = record.get("abstract", "") or ""
                creators = record.get("creators", [])
                authors = ", ".join(
                    c.get("creator", "") for c in creators[:5] if c.get("creator")
                )
                pub_name = record.get("publicationName", "")
                pub_date = record.get("publicationDate", "")
                content_type = record.get("contentType", "")

                text = f"{title}\n\nAuthors: {authors}\nPublication: {pub_name} ({pub_date})\nType: {content_type}\n\n{abstract}"
                text = text.strip()
                if len(text) < 30:
                    continue

                oa_url = None
                if doi:
                    try:
                        oa_url = await self._resolver.resolve(url, doi)
                    except Exception:
                        pass

                yield {
                    "url": oa_url or url,
                    "title": title,
                    "text": text,
                    "source_type": "academic_paper",
                    "platform": "academic_platforms",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "provider": "springer",
                        "doi": doi,
                        "authors": authors,
                        "publication": pub_name,
                        "published": pub_date,
                        "open_access_url": oa_url,
                        "query": query,
                    },
                }

            await asyncio.sleep(0.5)

        except Exception as exc:
            logger.warning(
                "AcademicPlatformsCollector: Springer error for '%s': %s", query, exc
            )

    async def _search_jstor(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Search JSTOR via DuckDuckGo, then fetch with session cookie."""
        try:
            from aria.engine.access.platforms.jstor import JSTORHandler

            handler = JSTORHandler()
            await handler.authenticate({"session_cookie": self._jstor_cookie})

            search_query = f"site:jstor.org {query}"
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            results: list[dict] = []
            with DDGS() as ddgs:
                for r in ddgs.text(search_query, max_results=5):
                    results.append(r)

            for result in results:
                url = result.get("href", "")
                if not url or "jstor.org" not in url or url in seen_urls:
                    continue

                # Try to fetch full content with session cookie
                content = await handler.fetch(url)
                title = result.get("title", "")
                body = result.get("body", "")

                if content and len(content) > len(body):
                    # Parse basic text from HTML response
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(content, "html.parser")
                        # Remove script/style
                        for tag in soup(["script", "style", "nav", "header", "footer"]):
                            tag.decompose()
                        text = soup.get_text(" ", strip=True)[:4000]
                    except Exception:
                        text = body
                else:
                    text = f"{title}\n\n{body}".strip()

                if len(text) < 30:
                    continue
                seen_urls.add(url)

                yield {
                    "url": url,
                    "title": title,
                    "text": text,
                    "source_type": "academic_paper",
                    "platform": "academic_platforms",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "provider": "jstor",
                        "query": query,
                        "fetched_with_cookie": bool(content),
                    },
                }

            await asyncio.sleep(0.5)

        except Exception as exc:
            logger.warning(
                "AcademicPlatformsCollector: JSTOR error for '%s': %s", query, exc
            )

    async def _search_acm(
        self, query: str, seen_urls: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Search ACM DL via DuckDuckGo, then fetch with session cookie."""
        try:
            from aria.engine.access.platforms.acm import ACMHandler

            handler = ACMHandler()
            await handler.authenticate({"session_cookie": self._acm_cookie})

            search_query = f"site:dl.acm.org {query}"
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            results: list[dict] = []
            with DDGS() as ddgs:
                for r in ddgs.text(search_query, max_results=5):
                    results.append(r)

            for result in results:
                url = result.get("href", "")
                if not url or "dl.acm.org" not in url or url in seen_urls:
                    continue

                content = await handler.fetch(url)
                title = result.get("title", "")
                body = result.get("body", "")

                if content and len(content) > len(body):
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(content, "html.parser")
                        for tag in soup(["script", "style", "nav", "header", "footer"]):
                            tag.decompose()
                        # ACM abstracts are in .abstractSection
                        abstract_div = soup.find(class_="abstractSection")
                        if abstract_div:
                            text = f"{title}\n\n{abstract_div.get_text(' ', strip=True)}"
                        else:
                            text = soup.get_text(" ", strip=True)[:4000]
                    except Exception:
                        text = body
                else:
                    text = f"{title}\n\n{body}".strip()

                if len(text) < 30:
                    continue
                seen_urls.add(url)

                # Extract DOI from ACM URL if present (format: /doi/10.xxxxx/yyy)
                doi = ""
                if "/doi/" in url:
                    doi = url.split("/doi/", 1)[1].split("?")[0]

                oa_url = None
                if doi:
                    try:
                        oa_url = await self._resolver.resolve(url, doi)
                    except Exception:
                        pass

                yield {
                    "url": oa_url or url,
                    "title": title,
                    "text": text,
                    "source_type": "academic_paper",
                    "platform": "academic_platforms",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "provider": "acm",
                        "doi": doi,
                        "open_access_url": oa_url,
                        "query": query,
                        "fetched_with_cookie": bool(content),
                    },
                }

            await asyncio.sleep(0.5)

        except Exception as exc:
            logger.warning(
                "AcademicPlatformsCollector: ACM error for '%s': %s", query, exc
            )
