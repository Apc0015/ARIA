"""Seed paper fetcher — retrieves a Level 0 paper by DOI or URL.

Given a DOI or direct URL, this module:
1. Fetches the paper's landing page / full text (HTML or PDF)
2. Extracts metadata (title, authors, year, journal, abstract)
3. Extracts the full reference list as raw strings
4. Returns a SeedResult containing the Level 0 record + raw references

Usage::

    from aria.engine.citation.seed import SeedFetcher

    fetcher = SeedFetcher()
    result = await fetcher.fetch(doi="10.5787/52-3-1483")
    print(result.level0_record)
    print(result.raw_references)   # list of raw strings ready for ReferenceParser
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from aria.engine.citation.ref_parser import ReferenceParser, RefRecord

logger = logging.getLogger("aria")


def _crossref_user_agent() -> str:
    """Identify ARIA to Crossref, with a contact only when one is configured."""
    email = os.getenv("UNPAYWALL_EMAIL", "")
    return f"ARIA/5.0 (mailto:{email})" if email else "ARIA/5.0"

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class CorpusRecord:
    """A single paper record in the citation corpus."""
    level: int = 0
    doi: str = ""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: str = ""
    journal: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    abstract: str = ""
    full_text_available: bool = False
    full_text_path: str = ""
    access_status: str = "unknown"   # open_access | paywalled | unavailable | unknown
    doi_status: str = "unknown"      # verified | unverified | not_found | not_applicable
    url: str = ""
    ref_type: str = "journal_article"
    source_url: str = ""             # where we fetched this from
    parse_notes: list[str] = field(default_factory=list)
    raw_ref: str = ""                # original reference string (Level 1 only)
    authors_raw: str = ""            # Issue #9 fix — raw author string before parsing
    publisher: str = ""              # book publisher
    place: str = ""                  # publication place

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "doi": self.doi,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "journal": self.journal,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "abstract": self.abstract,
            "full_text_available": self.full_text_available,
            "full_text_path": self.full_text_path,
            "access_status": self.access_status,
            "doi_status": self.doi_status,
            "url": self.url,
            "ref_type": self.ref_type,
            "source_url": self.source_url,
            "authors_raw": self.authors_raw,
            "parse_notes": self.parse_notes,
            "raw_ref": self.raw_ref,
        }


@dataclass
class SeedResult:
    """Result of fetching a seed paper."""
    level0_record: CorpusRecord
    raw_references: list[str]          # raw strings, one per reference
    parsed_references: list[RefRecord]  # structured parsed references
    full_text: str = ""
    success: bool = True
    error: str = ""


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------

class SeedFetcher:
    """Fetch a seed paper and extract its metadata + reference list."""

    def __init__(self, timeout: int = 20) -> None:
        self._timeout = timeout
        self._parser = ReferenceParser()

    async def fetch(
        self,
        *,
        doi: str = "",
        url: str = "",
    ) -> SeedResult:
        """Fetch seed paper by DOI or URL.

        At least one of doi or url must be provided. If both given, doi takes
        precedence for metadata resolution; url is used for full-text fetch.
        """
        if not doi and not url:
            raise ValueError("Provide at least one of doi or url")

        record = CorpusRecord(level=0)
        if doi:
            record.doi = doi.strip()
            record.doi_status = "unverified"

        fetch_url = url or (f"https://doi.org/{doi}" if doi else "")
        record.source_url = fetch_url

        # Step 1: Resolve metadata via CrossRef
        if doi:
            await self._enrich_from_crossref(record, doi)

        # Step 2: Fetch full text / HTML
        full_text = ""
        raw_refs: list[str] = []

        html = await self._fetch_html(fetch_url)
        if html:
            full_text = self._extract_text_from_html(html)
            raw_refs = self._extract_references_from_html(html)
            record.full_text_available = bool(full_text)
            record.access_status = "open_access" if full_text else "unknown"

        # Step 3: Parse references
        parsed_refs = self._parser.parse_list(raw_refs) if raw_refs else []

        # Step 4: Fill in any missing metadata from text
        if not record.abstract and full_text:
            record.abstract = self._extract_abstract_from_text(full_text)

        return SeedResult(
            level0_record=record,
            raw_references=raw_refs,
            parsed_references=parsed_refs,
            full_text=full_text,
            success=True,
        )

    # ------------------------------------------------------------------
    # CrossRef metadata resolution
    # ------------------------------------------------------------------

    async def _enrich_from_crossref(self, record: CorpusRecord, doi: str) -> None:
        """Populate record fields from CrossRef API."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"https://api.crossref.org/works/{doi}",
                    headers={"User-Agent": _crossref_user_agent()},
                )
            if resp.status_code == 200:
                data = resp.json().get("message", {})
                record.title = (data.get("title") or [""])[0]
                record.doi_status = "verified"

                # Authors
                record.authors = [
                    f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
                    for a in data.get("author", [])
                ]

                # Journal
                containers = data.get("container-title", [])
                record.journal = containers[0] if containers else ""
                record.volume = data.get("volume", "")
                record.issue = data.get("issue", "")
                record.pages = data.get("page", "")

                # Year
                for date_key in ("published-print", "published-online", "issued"):
                    parts = data.get(date_key, {}).get("date-parts", [[]])
                    if parts and parts[0]:
                        record.year = str(parts[0][0])
                        break

                # Abstract
                abstract = data.get("abstract", "") or ""
                record.abstract = re.sub(r"<[^>]+>", "", abstract).strip()

                # Open access URL
                links = data.get("link", [])
                if links:
                    record.url = links[0].get("URL", "")

        except Exception as exc:
            logger.debug("SeedFetcher: CrossRef error for %s: %s", doi, exc)
            record.parse_notes.append(f"crossref_error:{exc}")

    # ------------------------------------------------------------------
    # HTML fetch + extraction
    # ------------------------------------------------------------------

    async def _fetch_html(self, url: str) -> str:
        """Fetch a URL and return the response text."""
        if not url:
            return ""
        from aria.utils.robots import allowed_async
        from aria.utils.url import ensure_public_http_request

        if not await allowed_async(url):
            logger.debug("SeedFetcher: robots.txt disallows %s", url)
            return ""
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                event_hooks={"request": [ensure_public_http_request]},
                headers={"User-Agent": "Mozilla/5.0 (compatible; ARIA/5.0; +https://aria.research)"},
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.text
                logger.debug("SeedFetcher: HTTP %s for %s", resp.status_code, url)
                return ""
        except Exception as exc:
            logger.debug("SeedFetcher: fetch error for %s: %s", url, exc)
            return ""

    def _extract_text_from_html(self, html: str) -> str:
        """Extract readable article text from HTML (no BeautifulSoup dependency)."""
        # Remove script and style blocks
        text = re.sub(r'<(?:script|style)[^>]*>.*?</(?:script|style)>', '', html,
                      flags=re.DOTALL | re.IGNORECASE)
        # Remove all remaining tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Decode common HTML entities
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>') \
                   .replace('&nbsp;', ' ').replace('&quot;', '"').replace('&#39;', "'")
        # Collapse whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    def _extract_references_from_html(self, html: str) -> list[str]:
        """Extract raw reference strings from HTML.

        Strategy:
        1. Look for SciELO-style [ [Links] ] separated references
        2. Fall back to blank-line separated blocks after 'References' heading
        """
        # SciELO pattern: references separated by [ [Links](javascript:...) ]
        links_split = re.split(
            r'\[\s*\[Links\]\(javascript:void\(0\);\)\s*\]',
            html
        )
        if len(links_split) > 5:
            # Extract text from each chunk
            refs = []
            for chunk in links_split[1:]:  # skip preamble
                # Take text up to next section break
                text = re.sub(r'<[^>]+>', ' ', chunk)
                text = re.sub(r'\s+', ' ', text).strip()
                text = text.split('[1]')[0].strip()  # stop at footnotes
                if text and len(text) > 30 and re.search(r'\b(?:19|20)\d{2}\b', text):
                    refs.append(text)
            if refs:
                logger.debug("SeedFetcher: extracted %d refs via SciELO pattern", len(refs))
                return refs

        # Fallback: find references section in plain text
        plain = re.sub(r'<[^>]+>', ' ', html)
        plain = re.sub(r'\s+', ' ', plain)
        for marker in ['References', 'REFERENCES', 'Bibliography', 'BIBLIOGRAPHY']:
            idx = plain.find(marker, 5000)
            if idx != -1:
                ref_block = plain[idx + len(marker):]
                # Split on lines that look like new references
                entries = re.split(r'(?=\b[A-Z][a-z]+,?\s+(?:[A-Z]\.?\s*)+(?:19|20)\d{2})', ref_block)
                refs = []
                for e in entries:
                    e = e.strip()
                    if len(e) > 40 and re.search(r'\b(?:19|20)\d{2}\b', e):
                        refs.append(e[:500])
                if refs:
                    logger.debug("SeedFetcher: extracted %d refs via text fallback", len(refs))
                    return refs

        return []

    def _extract_abstract_from_text(self, text: str) -> str:
        """Extract abstract from plain text."""
        for marker in ['Abstract', 'ABSTRACT', 'Summary', 'SUMMARY']:
            idx = text.find(marker)
            if idx != -1:
                snippet = text[idx + len(marker):idx + 2000]
                # Stop at next section heading (all-caps line or double newline)
                snippet = re.split(r'\n\n|\b(?:Introduction|INTRODUCTION|Keywords|KEYWORDS)\b', snippet)[0]
                abstract = snippet.strip().lstrip(':').strip()
                if len(abstract) > 50:
                    return abstract[:2000]
        return ""


# ---------------------------------------------------------------------------
# Convenience async runner
# ---------------------------------------------------------------------------

async def fetch_seed(*, doi: str = "", url: str = "") -> SeedResult:
    """Module-level convenience wrapper."""
    fetcher = SeedFetcher()
    return await fetcher.fetch(doi=doi, url=url)
