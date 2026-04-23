"""Citation resolver — fetch metadata for DOIs, arXiv IDs, and PMIDs."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("aria")

_CROSSREF = "https://api.crossref.org/works"
_ARXIV_API = "http://export.arxiv.org/api/query"
_PUBMED_SUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1/paper"


class CitationResolver:
    """Resolves DOIs, arXiv IDs, and PMIDs to full document metadata."""

    def __init__(self, max_concurrent: int = 5) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def resolve_dois(self, dois: list[str]) -> list[dict[str, Any]]:
        """Resolve a list of DOIs via Crossref API."""
        tasks = [self._resolve_doi(doi) for doi in dois[:20]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]

    async def resolve_arxiv_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        """Resolve arXiv IDs via arXiv API."""
        if not ids:
            return []
        id_list = ",".join(ids[:20])
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    _ARXIV_API,
                    params={"id_list": id_list, "max_results": 20},
                )
                if resp.status_code != 200:
                    return []
                return self._parse_arxiv_feed(resp.text)
        except Exception as exc:
            logger.debug("CitationResolver: arXiv error: %s", exc)
            return []

    async def resolve_pmids(self, pmids: list[str]) -> list[dict[str, Any]]:
        """Resolve PubMed IDs via NCBI eutils."""
        if not pmids:
            return []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    _PUBMED_SUMMARY,
                    params={
                        "db": "pubmed",
                        "id": ",".join(pmids[:20]),
                        "retmode": "json",
                    },
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
                result = data.get("result", {})
                docs = []
                for pmid in pmids[:20]:
                    item = result.get(pmid, {})
                    if not item:
                        continue
                    title = item.get("title", "")
                    pub_date = item.get("pubdate", "")
                    source = item.get("source", "")
                    authors = ", ".join(
                        a.get("name", "") for a in item.get("authors", [])[:5]
                    )
                    text = f"{title}\nJournal: {source}\nDate: {pub_date}\nAuthors: {authors}".strip()
                    if len(text) < 20:
                        continue
                    docs.append({
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        "title": title,
                        "text": text,
                        "source_type": "academic_paper",
                        "platform": "pubmed",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {"source": "pubmed", "pmid": pmid},
                        "is_citation": True,
                    })
                return docs
        except Exception as exc:
            logger.debug("CitationResolver: PubMed error: %s", exc)
            return []

    async def _resolve_doi(self, doi: str) -> dict[str, Any] | None:
        async with self._semaphore:
            try:
                await asyncio.sleep(0.1)  # polite rate limiting
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        f"{_CROSSREF}/{doi}",
                        headers={"User-Agent": "ARIA/5.0 (mailto:aria@research.tool)"},
                    )
                    if resp.status_code == 404:
                        return None
                    if resp.status_code != 200:
                        return None

                    data = resp.json().get("message", {})
                    title_list = data.get("title", [])
                    title = title_list[0] if title_list else ""
                    if not title:
                        return None

                    authors_raw = data.get("author", [])[:5]
                    authors = ", ".join(
                        f"{a.get('given', '')} {a.get('family', '')}".strip()
                        for a in authors_raw
                    )

                    container = data.get("container-title", [])
                    journal = container[0] if container else ""
                    year_parts = data.get("published-print", {}).get("date-parts", [[]])
                    year = str(year_parts[0][0]) if year_parts and year_parts[0] else ""
                    abstract = data.get("abstract", "") or ""

                    text_parts = [title]
                    if authors:
                        text_parts.append(f"Authors: {authors}")
                    if journal:
                        text_parts.append(f"Journal: {journal}")
                    if year:
                        text_parts.append(f"Year: {year}")
                    if abstract:
                        # Strip HTML tags from abstract
                        import re
                        clean_abstract = re.sub(r"<[^>]+>", "", abstract)
                        text_parts.append(f"\n{clean_abstract[:600]}")

                    text = "\n".join(text_parts).strip()
                    oa_url = (
                        data.get("link", [{}])[0].get("URL", "")
                        if data.get("link")
                        else ""
                    )

                    return {
                        "url": oa_url or f"https://doi.org/{doi}",
                        "title": title,
                        "text": text,
                        "source_type": "academic_paper",
                        "platform": "crossref",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "source": "crossref",
                            "doi": doi,
                            "year": year,
                            "journal": journal,
                        },
                        "is_citation": True,
                    }

            except Exception as exc:
                logger.debug("CitationResolver: DOI %s error: %s", doi, exc)
                return None

    def _parse_arxiv_feed(self, xml_text: str) -> list[dict[str, Any]]:
        """Parse arXiv Atom feed (simple XML parsing without lxml dependency)."""
        import re
        docs = []
        entries = re.findall(r"<entry>(.*?)</entry>", xml_text, re.DOTALL)
        for entry in entries[:10]:
            def _tag(t: str) -> str:
                m = re.search(rf"<{t}[^>]*>(.*?)</{t}>", entry, re.DOTALL)
                return m.group(1).strip() if m else ""

            arxiv_id_raw = _tag("id")
            arxiv_id = arxiv_id_raw.rsplit("/", 1)[-1] if arxiv_id_raw else ""
            title = _tag("title").replace("\n", " ")
            summary = _tag("summary")[:600]
            published = _tag("published")[:10]
            authors_raw = re.findall(r"<name>(.*?)</name>", entry)
            authors = ", ".join(authors_raw[:5])

            if not title or not arxiv_id:
                continue

            text_parts = [title]
            if authors:
                text_parts.append(f"Authors: {authors}")
            text_parts.append(f"Published: {published}")
            if summary:
                text_parts.append(f"\n{summary}")

            text = "\n".join(text_parts).strip()
            docs.append({
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "title": title,
                "text": text,
                "source_type": "academic_paper",
                "platform": "arxiv",
                "language": "en",
                "word_count": len(text.split()),
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "source": "arxiv",
                    "arxiv_id": arxiv_id,
                    "published": published,
                },
                "is_citation": True,
            })
        return docs
