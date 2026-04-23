"""Citation Agent — orchestrates citation extraction, resolution, and enrichment."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aria.engine.citation.extractor import CitationExtractor
from aria.engine.citation.resolver import CitationResolver

logger = logging.getLogger("aria")


class CitationAgent:
    """Follows citation chains from collected documents.

    Pipeline:
    1. Extract DOIs/arXiv IDs/PMIDs from collected docs
    2. Resolve citations via Crossref / arXiv / PubMed APIs
    3. Return resolved papers as new documents (marked is_citation=True)
    4. Optionally recurse to depth N
    """

    def __init__(self, max_depth: int = 2, max_citations: int = 50) -> None:
        self._max_depth = max_depth
        self._max_citations = max_citations
        self._extractor = CitationExtractor()
        self._resolver = CitationResolver(max_concurrent=5)

    async def enrich(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract citations from docs and fetch cited papers.

        Returns all original docs + resolved citation docs.
        """
        if not docs or self._max_depth == 0:
            return docs

        all_docs = list(docs)
        seen_urls: set[str] = {doc.get("url", "") for doc in docs}
        citation_docs: list[dict[str, Any]] = []

        current_batch = docs
        for depth in range(self._max_depth):
            if len(citation_docs) >= self._max_citations:
                break

            # Extract citations from current batch
            annotated = self._extractor.extract_batch(current_batch)
            dois = self._extractor.collect_unique_dois(annotated)
            arxiv_ids = self._extractor.collect_unique_arxiv(annotated)

            pmids: list[str] = []
            for doc in annotated:
                pmids.extend(doc.get("citations", {}).get("pmids", []))
            pmids = list(set(pmids))[:20]

            if not dois and not arxiv_ids and not pmids:
                break

            logger.debug(
                "CitationAgent depth=%d: %d DOIs, %d arXiv, %d PMIDs",
                depth + 1, len(dois), len(arxiv_ids), len(pmids),
            )

            # Resolve in parallel
            resolved: list[dict[str, Any]] = []
            tasks = []
            if dois:
                tasks.append(self._resolver.resolve_dois(dois[:20]))
            if arxiv_ids:
                tasks.append(self._resolver.resolve_arxiv_ids(arxiv_ids[:20]))
            if pmids:
                tasks.append(self._resolver.resolve_pmids(pmids[:20]))

            if tasks:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                for br in batch_results:
                    if isinstance(br, list):
                        resolved.extend(br)

            # Filter already-seen and add new ones
            new_docs: list[dict[str, Any]] = []
            for doc in resolved:
                url = doc.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    doc["citation_depth"] = depth + 1
                    new_docs.append(doc)
                    if len(citation_docs) + len(new_docs) >= self._max_citations:
                        break

            citation_docs.extend(new_docs)
            current_batch = new_docs  # recurse into newly found papers

            if not new_docs:
                break

            await asyncio.sleep(0.5)

        logger.debug(
            "CitationAgent: resolved %d citation documents across %d depth levels",
            len(citation_docs), self._max_depth,
        )

        return all_docs + citation_docs
