"""Citation Graph Agent - recursively collects papers from citation references.

Extracts citations from academic papers and fetches the cited documents,
enabling deep literature exploration and discovery of foundational papers.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

import aiohttp

from aria.sources.base import BaseCollector, CollectorConfig


@dataclass
class CitationRef:
    """Extracted citation reference."""

    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: str | None = None
    doi: str | None = None
    url: str | None = None
    venue: str | None = None  # Journal, conference, etc.
    raw_text: str = ""


class CitationExtractor:
    """Extracts citations from academic paper text."""

    # DOI regex pattern
    DOI_PATTERN = r"(?:https?://)?(?:dx\.)?doi\.org/([0-9.]+/[^\s\)\"<>]+)"

    # arXiv ID pattern
    ARXIV_PATTERN = r"arxiv\.org/abs/(\d{4}\.\d{4,5})"

    # URL pattern
    URL_PATTERN = r"https?://[^\s\)\"<>]+"

    @staticmethod
    def extract_dois(text: str) -> list[str]:
        """Extract DOI identifiers from text."""
        matches = re.findall(CitationExtractor.DOI_PATTERN, text, re.IGNORECASE)
        return [f"10.{match}" if not match.startswith("10.") else match for match in matches]

    @staticmethod
    def extract_arxiv_ids(text: str) -> list[str]:
        """Extract arXiv IDs from text."""
        return re.findall(CitationExtractor.ARXIV_PATTERN, text)

    @staticmethod
    def extract_urls(text: str) -> list[str]:
        """Extract URLs from text."""
        return re.findall(CitationExtractor.URL_PATTERN, text)

    @staticmethod
    def parse_references_section(text: str) -> list[CitationRef]:
        """Parse References/Bibliography section from paper text.

        Identifies common reference formats (APA, MLA, Chicago, IEEE).
        """
        citations = []

        # Split by common reference separators
        lines = re.split(r"\n\[?\d+\]?\s*", text)

        for line in lines:
            if len(line.strip()) < 20:  # Skip short fragments
                continue

            ref = CitationRef(raw_text=line.strip())

            # Extract DOI
            dois = CitationExtractor.extract_dois(line)
            if dois:
                ref.doi = dois[0]

            # Extract arXiv ID
            arxiv_ids = CitationExtractor.extract_arxiv_ids(line)
            if arxiv_ids:
                ref.url = f"https://arxiv.org/abs/{arxiv_ids[0]}"

            # Extract generic URLs
            urls = CitationExtractor.extract_urls(line)
            if urls and not ref.url:
                ref.url = urls[0]

            # Extract title (usually between quotes or at start)
            title_match = re.search(r'["\']([^"\']{20,200})["\']', line)
            if title_match:
                ref.title = title_match.group(1)
            else:
                # Use first substantial phrase
                words = [w for w in line.split() if len(w) > 3]
                if words:
                    ref.title = " ".join(words[:15])

            # Extract year (4 digits in parentheses or standalone)
            year_match = re.search(r"\((\d{4})\)|(?:^|\s)(\d{4})(?:\s|$)", line)
            if year_match:
                ref.year = year_match.group(1) or year_match.group(2)

            # Extract authors (names before year typically)
            authors_match = re.search(r"^([^,]+(?:,\s*[^,]+)*?)(?:\([0-9]{4}\)|[0-9]{4})", line)
            if authors_match:
                author_text = authors_match.group(1)
                authors = re.split(r",\s*(?:and\s+)?", author_text)
                ref.authors = [a.strip() for a in authors if a.strip()]

            if ref.title:
                citations.append(ref)

        return citations


class CitationFetcher:
    """Fetches cited papers from multiple sources."""

    UNPAYWALL_API = "https://api.unpaywall.org/v2"
    SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
    CROSSREF_API = "https://api.crossref.org/v1"

    def __init__(self, email: str | None = None):
        """Initialize fetcher.

        Args:
            email: Email for Unpaywall API (required by ToS)
        """
        self.email = email or "research@aria.local"
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def fetch_by_doi(self, doi: str) -> dict[str, Any] | None:
        """Fetch paper metadata by DOI."""
        if not self.session:
            return None

        try:
            # Try Crossref first (fastest)
            url = f"{self.CROSSREF_API}/works/{doi}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    msg = data.get("message", {})
                    return {
                        "title": msg.get("title", [""])[0] if isinstance(msg.get("title"), list) else msg.get("title"),
                        "doi": doi,
                        "year": msg.get("published-online", {}).get("date-parts", [[None]])[0][0],
                        "authors": [
                            f"{a.get('given', '')} {a.get('family', '')}"
                            for a in msg.get("author", [])[:5]
                        ],
                        "url": msg.get("URL"),
                        "source": "crossref",
                    }
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass

        return None

    async def fetch_by_arxiv(self, arxiv_id: str) -> dict[str, Any] | None:
        """Fetch paper metadata by arXiv ID."""
        if not self.session:
            return None

        try:
            url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}&start=0&max_results=1"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    # Parse XML response
                    title_match = re.search(r"<title>([^<]+)</title>", text)
                    authors = re.findall(r"<name>([^<]+)</name>", text)
                    published = re.search(r"<published>(\d{4})-", text)

                    return {
                        "title": title_match.group(1) if title_match else arxiv_id,
                        "arxiv_id": arxiv_id,
                        "url": f"https://arxiv.org/abs/{arxiv_id}",
                        "year": published.group(1) if published else None,
                        "authors": authors[:5],
                        "source": "arxiv",
                    }
        except Exception:
            pass

        return None

    async def fetch_by_title(self, title: str) -> dict[str, Any] | None:
        """Fetch paper metadata by title via Semantic Scholar."""
        if not self.session or not title:
            return None

        try:
            # Semantic Scholar search endpoint
            url = f"{self.SEMANTIC_SCHOLAR_API}/paper/search"
            params = {
                "query": title[:100],
                "limit": 1,
                "fields": "title,authors,year,url,doi",
            }
            async with self.session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    papers = data.get("data", [])
                    if papers:
                        paper = papers[0]
                        return {
                            "title": paper.get("title"),
                            "doi": paper.get("doi"),
                            "url": paper.get("url"),
                            "year": paper.get("year"),
                            "authors": [a.get("name", "") for a in paper.get("authors", [])[:5]],
                            "source": "semantic-scholar",
                        }
        except Exception:
            pass

        return None


class CitationGraphCollector(BaseCollector):
    """Recursively collects papers from citation networks.

    Extends initial collection by fetching papers cited in collected documents,
    enabling deep literature exploration.
    """

    def __init__(self, config: CollectorConfig):
        """Initialize citation graph collector.

        Args:
            config: Collector configuration with optional 'max_depth' and 'max_citations'
        """
        super().__init__(config)
        self.max_depth = config.extra.get("max_depth", 2) if config.extra else 2
        self.max_citations_per_paper = (
            config.extra.get("max_citations_per_paper", 20) if config.extra else 20
        )
        self.seen_dois = set()
        self.seen_urls = set()

    async def collect(
        self, documents: list[dict[str, Any]], depth: int = 0
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Collect cited papers from documents.

        Args:
            documents: List of document dicts with 'text' field
            depth: Current recursion depth

        Yields:
            Document dicts for cited papers
        """
        if depth >= self.max_depth:
            return

        extractor = CitationExtractor()
        async with CitationFetcher() as fetcher:
            for doc in documents:
                text = doc.get("text", "")
                if not text or len(text) < 500:
                    continue

                # Extract References section (rough heuristic)
                ref_match = re.search(
                    r"(?:references|bibliography|works cited)\s*\n(.*?)(?:\n\n|$)",
                    text,
                    re.IGNORECASE | re.DOTALL,
                )
                ref_text = ref_match.group(1) if ref_match else text[-2000:]  # Last 2000 chars

                # Parse citations
                citations = extractor.parse_references_section(ref_text)
                citations = citations[: self.max_citations_per_paper]

                # Fetch cited papers concurrently
                tasks = []
                for citation in citations:
                    tasks.append(self._fetch_citation(fetcher, citation, depth))

                results = await asyncio.gather(*tasks, return_exceptions=True)

                next_depth_docs = []
                for result in results:
                    if isinstance(result, dict):
                        yield result
                        next_depth_docs.append(result)

                # Recurse into cited papers if more depth remains
                if next_depth_docs and depth + 1 < self.max_depth:
                    async for deeper in self.collect(next_depth_docs, depth=depth + 1):
                        yield deeper

    async def _fetch_citation(
        self, fetcher: CitationFetcher, citation: CitationRef, depth: int
    ) -> dict[str, Any] | None:
        """Fetch a single citation."""
        # Try DOI first
        if citation.doi and citation.doi not in self.seen_dois:
            self.seen_dois.add(citation.doi)
            result = await fetcher.fetch_by_doi(citation.doi)
            if result:
                return self._format_result(result, citation, depth)

        # Try arXiv
        if citation.url and "arxiv.org" in citation.url:
            arxiv_match = re.search(r"(\d{4}\.\d{4,5})", citation.url)
            if arxiv_match:
                arxiv_id = arxiv_match.group(1)
                result = await fetcher.fetch_by_arxiv(arxiv_id)
                if result:
                    return self._format_result(result, citation, depth)

        # Try by title
        if citation.title and citation.title not in self.seen_urls:
            self.seen_urls.add(citation.title)
            result = await fetcher.fetch_by_title(citation.title)
            if result:
                return self._format_result(result, citation, depth)

        return None

    @staticmethod
    def _format_result(
        data: dict[str, Any], citation: CitationRef, depth: int
    ) -> dict[str, Any]:
        """Format fetched data as ARIA document."""
        return {
            "title": data.get("title") or citation.title,
            "url": data.get("url") or citation.url or "unknown",
            "source_type": "academic_paper",
            "platform": f"citations_depth_{depth}",
            "authors": data.get("authors", citation.authors),
            "year": data.get("year") or citation.year,
            "doi": data.get("doi") or citation.doi,
            "text": "",  # Will be populated by cleaner if needed
            "citation_source": True,
            "influence_score": 0.5,  # Default, can be updated with citation count
        }


# Register the collector if registry is available
try:
    from aria.sources.registry import SourceRegistry
    SourceRegistry.register("citation_graph", CitationGraphCollector)
except ImportError:
    pass
