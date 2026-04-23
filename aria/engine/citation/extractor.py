"""Citation extractor — pulls DOIs, URLs, and academic references from documents."""

from __future__ import annotations

import re
from typing import Any

# DOI pattern: 10.xxxx/...
_DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>]+", re.IGNORECASE)
# arXiv IDs: 1234.56789 or arXiv:1234.56789
_ARXIV_RE = re.compile(r"(?:arXiv:)?(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
# PMIDs: PMID: 12345678
_PMID_RE = re.compile(r"PMID[:\s]+(\d{6,9})", re.IGNORECASE)
# URLs (basic)
_URL_RE = re.compile(r"https?://[^\s\"'<>]{10,}", re.IGNORECASE)
# Academic reference pattern: Author et al., Year
_REF_RE = re.compile(
    r"([A-Z][a-z]+ et al\.,?\s+\d{4}|[A-Z][a-z]+,?\s+[A-Z]\.\s*(?:et al\.)?\s*\(\d{4}\))",
    re.MULTILINE,
)


def extract_citations(doc: dict[str, Any]) -> dict[str, list[str]]:
    """Extract all citation types from a document dict.

    Returns:
        Dict with keys: dois, arxiv_ids, pmids, urls, references
    """
    text = doc.get("text", "") or ""
    url = doc.get("url", "") or ""

    dois = list(set(_DOI_RE.findall(text)))
    arxiv_ids = list(set(_ARXIV_RE.findall(text)))
    pmids = list(set(_PMID_RE.findall(text)))

    # Collect URLs that aren't the doc's own URL
    urls = [u for u in _URL_RE.findall(text) if u != url and len(u) < 300]
    urls = list(set(urls))[:20]

    references = list(set(_REF_RE.findall(text)))[:30]

    return {
        "dois": dois[:20],
        "arxiv_ids": arxiv_ids[:20],
        "pmids": pmids[:20],
        "urls": urls,
        "references": references,
    }


class CitationExtractor:
    """Extracts and normalises citations from a batch of documents."""

    def extract_batch(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Add citation fields to each document and return updated list."""
        result = []
        for doc in docs:
            citations = extract_citations(doc)
            updated = dict(doc)
            updated["citations"] = citations
            updated["citation_count"] = (
                len(citations["dois"])
                + len(citations["arxiv_ids"])
                + len(citations["pmids"])
            )
            result.append(updated)
        return result

    def collect_unique_dois(self, docs: list[dict[str, Any]]) -> list[str]:
        """Return all unique DOIs found across a batch."""
        seen: set[str] = set()
        dois: list[str] = []
        for doc in docs:
            for doi in doc.get("citations", {}).get("dois", []):
                if doi not in seen:
                    seen.add(doi)
                    dois.append(doi)
        return dois

    def collect_unique_arxiv(self, docs: list[dict[str, Any]]) -> list[str]:
        seen: set[str] = set()
        ids: list[str] = []
        for doc in docs:
            for aid in doc.get("citations", {}).get("arxiv_ids", []):
                if aid not in seen:
                    seen.add(aid)
                    ids.append(aid)
        return ids
