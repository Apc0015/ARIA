"""Citation expansion phase - runs after initial collection.

Processes collected academic papers to extract and fetch their citations,
creating a deeper literature graph for more comprehensive research.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from aria.sources.academic.citations import CitationGraphCollector
from aria.sources.base import CollectorConfig


@dataclass
class CitationExpansionConfig:
    """Configuration for citation expansion phase."""

    enabled: bool = True
    max_depth: int = 2  # How many levels deep to follow citations
    max_citations_per_paper: int = 20
    max_concurrent_fetches: int = 5  # API rate limiting
    only_academic: bool = True  # Only expand citations from academic sources


class CitationExpander:
    """Orchestrates citation expansion phase."""

    def __init__(self, config: CitationExpansionConfig | None = None):
        """Initialize citation expander.

        Args:
            config: Citation expansion configuration
        """
        self.config = config or CitationExpansionConfig()

    async def expand_collection(
        self, collected_docs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Expand collection with cited papers.

        Args:
            collected_docs: Documents from initial collection phase

        Returns:
            List of new documents from citations
        """
        if not self.config.enabled or not collected_docs:
            return []

        # Filter to academic papers only if configured
        academic_docs = collected_docs
        if self.config.only_academic:
            academic_docs = [
                d for d in collected_docs if d.get("source_type") == "academic_paper"
            ]

        if not academic_docs:
            return []

        # Create collector with config
        collector_config = CollectorConfig(
            name="citation_graph",
            enabled=True,
            max_results=100,
            extra={
                "max_depth": self.config.max_depth,
                "max_citations_per_paper": self.config.max_citations_per_paper,
            },
        )

        collector = CitationGraphCollector(collector_config)

        # Collect citations asynchronously
        cited_papers = []
        async for paper in collector.collect(academic_docs, depth=0):
            cited_papers.append(paper)

            # Rate limiting
            if len(cited_papers) % self.config.max_concurrent_fetches == 0:
                await asyncio.sleep(0.1)

        return cited_papers

    def score_by_influence(
        self, papers: list[dict[str, Any]], citation_count: dict[str, int]
    ) -> list[dict[str, Any]]:
        """Score papers by citation influence.

        Args:
            papers: Papers to score
            citation_count: Map of paper DOI/URL to citation count

        Returns:
            Papers with updated influence_score
        """
        for paper in papers:
            doi = paper.get("doi") or paper.get("url", "")
            count = citation_count.get(doi, 0)

            # Influence score: 0.0–1.0 based on citation count
            # Logarithmic scale (1 cite = 0.2, 10 cites = 0.5, 100 cites = 0.8)
            influence = min(0.9, (count ** 0.4) / 10)
            paper["influence_score"] = influence

        return sorted(papers, key=lambda p: p.get("influence_score", 0), reverse=True)


class CitationPipeline:
    """Full pipeline: collection → citation expansion → cleaning."""

    def __init__(self, citation_config: CitationExpansionConfig | None = None):
        """Initialize pipeline.

        Args:
            citation_config: Citation expansion configuration
        """
        self.expander = CitationExpander(citation_config)

    async def run_expansion_phase(
        self, initial_docs: list[dict[str, Any]], run_id: str
    ) -> dict[str, Any]:
        """Run citation expansion phase.

        Args:
            initial_docs: Documents from collection phase
            run_id: Identifier for this run

        Returns:
            {
                'new_documents': list of cited papers,
                'stats': expansion statistics
            }
        """
        print(f"[Citation Expansion] Starting for {run_id}")
        print(f"[Citation Expansion] Input: {len(initial_docs)} documents")

        # Count academic papers
        academic_count = sum(
            1 for d in initial_docs if d.get("source_type") == "academic_paper"
        )
        print(f"[Citation Expansion] Academic papers: {academic_count}")

        # Run expansion
        new_docs = await self.expander.expand_collection(initial_docs)
        print(f"[Citation Expansion] Found {len(new_docs)} cited papers")

        return {
            "new_documents": new_docs,
            "stats": {
                "initial_count": len(initial_docs),
                "academic_count": academic_count,
                "cited_papers_found": len(new_docs),
                "expansion_ratio": (
                    len(new_docs) / academic_count if academic_count > 0 else 0
                ),
            },
        }


# Example usage:
#
# async def main():
#     config = CitationExpansionConfig(
#         enabled=True,
#         max_depth=2,
#         max_citations_per_paper=15,
#     )
#     pipeline = CitationPipeline(config)
#
#     # After initial collection
#     result = await pipeline.run_expansion_phase(initial_documents, "run_001")
#
#     # Merge results
#     all_docs = initial_documents + result["new_documents"]
#     print(f"Total docs: {len(all_docs)}")
#     print(result["stats"])
