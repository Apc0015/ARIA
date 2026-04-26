"""Test citation expansion integration with ARIA orchestrator."""

import asyncio
from aria.orchestrator.citation_expansion import CitationPipeline, CitationExpansionConfig


async def test_citation_pipeline():
    """Test citation pipeline with sample documents."""
    # Sample academic papers
    sample_docs = [
        {
            "title": "Attention Is All You Need",
            "url": "https://arxiv.org/abs/1706.03762",
            "source_type": "academic_paper",
            "platform": "arxiv",
            "text": """
            Abstract: The dominant sequence transduction models...

            References
            [1] Bahdanau et al. (2015). "Neural Machine Translation by Jointly Learning
                to Align and Translate". ICLR.
            [2] Hochreiter & Schmidhuber (1997). "Long Short-Term Memory". Neural Computation.
            """,
        },
    ]

    config = CitationExpansionConfig(
        enabled=True,
        max_depth=1,
        max_citations_per_paper=5,
        max_concurrent_fetches=2,
    )

    pipeline = CitationPipeline(config)
    result = await pipeline.run_expansion_phase(sample_docs, "test_001")

    print(f"✓ Pipeline execution complete")
    print(f"  Initial docs: {result['stats']['initial_count']}")
    print(f"  Cited papers found: {result['stats']['cited_papers_found']}")
    print(f"  Expansion ratio: {result['stats']['expansion_ratio']:.2f}x")

    return result


if __name__ == "__main__":
    result = asyncio.run(test_citation_pipeline())
    print(f"\n✓ Integration test passed")
