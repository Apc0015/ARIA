"""Academic paper collector: arXiv, PubMed, and Semantic Scholar."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import AsyncGenerator, Any, Optional
from urllib.parse import quote

import httpx

from .base import BaseCollector

logger = logging.getLogger("aria")

_DEFAULT_TIMEOUT = 20
_DELAY = 0.5


async def _http_get_with_retry(
    url: str,
    timeout: int = _DEFAULT_TIMEOUT,
    max_attempts: int = 3,
    **kwargs: Any,
) -> "httpx.Response":
    """GET with exponential backoff on 429/5xx."""
    import random
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, **kwargs)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 5 * attempt))
                retry_after = min(retry_after, 30)
                logger.debug("HTTP 429 on %s — waiting %.1fs", url[:60], retry_after)
                await asyncio.sleep(retry_after)
                last_exc = Exception(f"HTTP 429")
                continue
            if resp.status_code >= 500:
                delay = min(2 ** attempt, 30)
                logger.debug("HTTP %d on %s — retry in %.1fs", resp.status_code, url[:60], delay)
                await asyncio.sleep(delay)
                last_exc = Exception(f"HTTP {resp.status_code}")
                continue
            return resp
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            delay = min(2 ** attempt, 30) * (0.8 + random.random() * 0.4)
            logger.debug("Network error on %s (attempt %d): %s — retry in %.1fs", url[:60], attempt, exc, delay)
            await asyncio.sleep(delay)
            last_exc = exc
    raise last_exc or Exception(f"All retries exhausted for {url}")


class AcademicCollector(BaseCollector):
    """Collects academic papers from arXiv, PubMed, and Semantic Scholar."""

    def __init__(
        self,
        max_per_source: int = 15,
        sources: Optional[list[str]] = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._max = max_per_source
        self._sources = sources or ["arxiv", "pubmed", "semantic_scholar"]
        self._timeout = timeout

    async def validate(self) -> bool:
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Collect academic papers for each query from all configured sources.

        Args:
            queries: Search queries.

        Yields:
            Document dicts with source_type='academic'.
        """
        seen_ids: set[str] = set()

        for query in queries:
            if "arxiv" in self._sources:
                async for doc in self._arxiv_search(query, seen_ids):
                    yield doc
                await asyncio.sleep(_DELAY)

            if "pubmed" in self._sources:
                async for doc in self._pubmed_search(query, seen_ids):
                    yield doc
                await asyncio.sleep(_DELAY)

            if "semantic_scholar" in self._sources:
                async for doc in self._semantic_scholar_search(query, seen_ids):
                    yield doc
                await asyncio.sleep(_DELAY)

    # ------------------------------------------------------------------
    # arXiv
    # ------------------------------------------------------------------

    async def _arxiv_search(
        self, query: str, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        url = (
            f"http://export.arxiv.org/api/query"
            f"?search_query=all:{quote(query)}&max_results={self._max}&sortBy=relevance"
        )
        try:
            resp = await _http_get_with_retry(url, timeout=self._timeout)
            if resp.status_code != 200:
                logger.debug("arXiv: HTTP %d", resp.status_code)
                return

            for entry in _parse_arxiv_atom(resp.text):
                uid = entry.get("arxiv_id", entry.get("url", ""))
                if uid in seen_ids:
                    continue
                seen_ids.add(uid)
                text = entry.get("abstract", "")
                yield {
                    "url": entry.get("url", ""),
                    "title": entry.get("title", ""),
                    "text": text,
                    "source_type": "academic",
                    "platform": "arxiv",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "query": query,
                        "arxiv_id": entry.get("arxiv_id"),
                        "authors": entry.get("authors", []),
                        "published": entry.get("published", ""),
                        "categories": entry.get("categories", []),
                        "pdf_url": entry.get("pdf_url", ""),
                    },
                }
        except Exception as exc:
            logger.warning("AcademicCollector arXiv error for '%s': %s", query, exc)

    # ------------------------------------------------------------------
    # PubMed
    # ------------------------------------------------------------------

    async def _pubmed_search(
        self, query: str, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            # Step 1: esearch to get PMIDs
            search_url = (
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
                f"?db=pubmed&term={quote(query)}&retmax={self._max}&retmode=json"
            )
            resp = await _http_get_with_retry(search_url, timeout=self._timeout)
            if resp.status_code != 200:
                return
            data = resp.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])

            if not pmids:
                return

            await asyncio.sleep(0.3)

            # Step 2: efetch to get abstracts
            fetch_url = (
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                f"?db=pubmed&id={','.join(pmids)}&retmode=xml&rettype=abstract"
            )
            resp = await _http_get_with_retry(fetch_url, timeout=self._timeout)
            if resp.status_code != 200:
                return
            articles = _parse_pubmed_xml(resp.text)

            for article in articles:
                uid = f"pubmed_{article.get('pmid', '')}"
                if uid in seen_ids:
                    continue
                seen_ids.add(uid)
                text = article.get("abstract", "")
                yield {
                    "url": article.get("url", ""),
                    "title": article.get("title", ""),
                    "text": text,
                    "source_type": "academic",
                    "platform": "pubmed",
                    "language": "en",
                    "word_count": len(text.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "query": query,
                        "pmid": article.get("pmid"),
                        "authors": article.get("authors", []),
                        "journal": article.get("journal", ""),
                        "published": article.get("published", ""),
                        "doi": article.get("doi", ""),
                    },
                }
        except Exception as exc:
            logger.warning("AcademicCollector PubMed error for '%s': %s", query, exc)

    # ------------------------------------------------------------------
    # Semantic Scholar
    # ------------------------------------------------------------------

    async def _semantic_scholar_search(
        self, query: str, seen_ids: set[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        url = (
            "https://api.semanticscholar.org/graph/v1/paper/search"
            f"?query={quote(query)}&limit={self._max}"
            "&fields=title,abstract,url,year,authors,externalIds,openAccessPdf"
        )
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.debug("Semantic Scholar: HTTP %d", resp.status_code)
                    return
                data = resp.json()
                papers = data.get("data", [])

            for paper in papers:
                paper_id = paper.get("paperId", "")
                uid = f"ss_{paper_id}"
                if uid in seen_ids:
                    continue
                seen_ids.add(uid)

                abstract = paper.get("abstract") or ""
                title = paper.get("title") or ""
                paper_url = paper.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}"

                # Prefer open access PDF URL
                oa = paper.get("openAccessPdf")
                if oa and oa.get("url"):
                    paper_url = oa["url"]

                authors = [a.get("name", "") for a in paper.get("authors", [])]

                yield {
                    "url": paper_url,
                    "title": title,
                    "text": abstract,
                    "source_type": "academic",
                    "platform": "semantic_scholar",
                    "language": "en",
                    "word_count": len(abstract.split()),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "query": query,
                        "paper_id": paper_id,
                        "authors": authors,
                        "year": paper.get("year"),
                        "doi": (paper.get("externalIds") or {}).get("DOI"),
                        "has_open_access": bool(oa and oa.get("url")),
                    },
                }
        except Exception as exc:
            logger.warning("AcademicCollector S2 error for '%s': %s", query, exc)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_arxiv_atom(xml_text: str) -> list[dict]:
    """Parse arXiv Atom feed XML."""
    try:
        import xml.etree.ElementTree as ET
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        root = ET.fromstring(xml_text)
        entries = []
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            title = title_el.text.strip() if title_el is not None and title_el.text else ""

            summary_el = entry.find("atom:summary", ns)
            abstract = summary_el.text.strip() if summary_el is not None and summary_el.text else ""

            id_el = entry.find("atom:id", ns)
            arxiv_url = id_el.text.strip() if id_el is not None and id_el.text else ""
            arxiv_id = arxiv_url.split("/abs/")[-1] if "/abs/" in arxiv_url else ""
            pdf_url = arxiv_url.replace("/abs/", "/pdf/") + ".pdf" if arxiv_id else ""

            published_el = entry.find("atom:published", ns)
            published = published_el.text.strip() if published_el is not None and published_el.text else ""

            authors = []
            for author_el in entry.findall("atom:author", ns):
                name_el = author_el.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text.strip())

            categories = []
            for cat_el in entry.findall("atom:category", ns):
                term = cat_el.get("term", "")
                if term:
                    categories.append(term)

            entries.append(
                {
                    "title": title,
                    "abstract": abstract,
                    "url": arxiv_url,
                    "arxiv_id": arxiv_id,
                    "pdf_url": pdf_url,
                    "published": published,
                    "authors": authors,
                    "categories": categories,
                }
            )
        return entries
    except Exception as exc:
        logger.debug("arXiv XML parse error: %s", exc)
        return []


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    """Parse PubMed efetch XML response."""
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_text)
        articles = []
        for article_el in root.iter("PubmedArticle"):
            # PMID
            pmid_el = article_el.find(".//PMID")
            pmid = pmid_el.text.strip() if pmid_el is not None and pmid_el.text else ""

            # Title
            title_el = article_el.find(".//ArticleTitle")
            title = (title_el.text or "").strip() if title_el is not None else ""

            # Abstract - may have multiple AbstractText elements
            abstract_parts = []
            for ab_el in article_el.findall(".//AbstractText"):
                label = ab_el.get("Label", "")
                text = ab_el.text or ""
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts).strip()

            # Authors
            authors = []
            for author_el in article_el.findall(".//Author"):
                last = (getattr(author_el.find("LastName"), "text", "") or "").strip()
                first = (getattr(author_el.find("ForeName"), "text", "") or "").strip()
                if last:
                    authors.append(f"{last} {first}".strip())

            # Journal
            journal_el = article_el.find(".//Journal/Title")
            journal = (journal_el.text or "").strip() if journal_el is not None else ""

            # DOI
            doi = ""
            for id_el in article_el.findall(".//ArticleId"):
                if id_el.get("IdType") == "doi":
                    doi = (id_el.text or "").strip()

            # Publication date
            pub_year_el = article_el.find(".//PubDate/Year")
            pub_year = (pub_year_el.text or "").strip() if pub_year_el is not None else ""

            pub_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            articles.append(
                {
                    "pmid": pmid,
                    "title": title,
                    "abstract": abstract,
                    "authors": authors,
                    "journal": journal,
                    "doi": doi,
                    "published": pub_year,
                    "url": pub_url,
                }
            )
        return articles
    except Exception as exc:
        logger.debug("PubMed XML parse error: %s", exc)
        return []
