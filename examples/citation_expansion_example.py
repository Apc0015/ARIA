#!/usr/bin/env python
"""Example: Using the Citation Graph Agent for deep literature exploration."""

import asyncio
import json
from aria.orchestrator.citation_expansion import CitationPipeline, CitationExpansionConfig


async def example_basic():
    """Basic citation expansion example."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Citation Expansion")
    print("=" * 60)

    # Mock documents from initial collection
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
            [2] Cho et al. (2014). "Learning Phrase Representations using RNN Encoder-Decoder
                for Statistical Machine Translation". EMNLP.
            [3] Krizhevsky et al. (2012). "ImageNet Classification with Deep Convolutional
                Neural Networks". NIPS.
            [4] Hochreiter & Schmidhuber (1997). "Long Short-Term Memory". Neural Computation.
            """,
        },
        {
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "url": "https://arxiv.org/abs/1810.04805",
            "source_type": "academic_paper",
            "platform": "arxiv",
            "text": """
            Abstract: We introduce BERT, a new method of pre-training...

            References
            [1] Vaswani et al. (2017). "Attention Is All You Need". arXiv:1706.03762
            [2] Devlin et al. (2019). "BERT: Pre-training of Deep Bidirectional
                Transformers for Language Understanding". NAACL.
            [3] Peters et al. (2018). "Deep contextualized word representations". NAACL.
            """,
        },
    ]

    # Configure citation expansion
    config = CitationExpansionConfig(
        enabled=True,
        max_depth=1,
        max_citations_per_paper=10,
        max_concurrent_fetches=3,
    )

    # Run expansion
    pipeline = CitationPipeline(config)
    result = await pipeline.run_expansion_phase(sample_docs, "example_001")

    print("\n📊 Results:")
    print(f"  Initial documents: {result['stats']['initial_count']}")
    print(f"  Academic papers: {result['stats']['academic_count']}")
    print(f"  Cited papers found: {result['stats']['cited_papers_found']}")
    print(f"  Expansion ratio: {result['stats']['expansion_ratio']:.2f}x")

    if result["new_documents"]:
        print("\n🔗 Sample cited papers:")
        for i, doc in enumerate(result["new_documents"][:3], 1):
            print(f"\n  {i}. {doc.get('title', 'Unknown')}")
            print(f"     Authors: {', '.join(doc.get('authors', [])[:2])}")
            print(f"     Year: {doc.get('year', 'N/A')}")
            print(f"     DOI: {doc.get('doi', 'N/A')}")
            print(f"     Influence: {doc.get('influence_score', 0):.2f}")


async def example_deep_search():
    """Deep search with multi-level citation expansion."""
    print("\n" + "=" * 60)
    print("Example 2: Deep Multi-Level Citation Search")
    print("=" * 60)

    sample_docs = [
        {
            "title": "The Transformer Architecture",
            "url": "https://arxiv.org/abs/1706.03762",
            "source_type": "academic_paper",
            "platform": "arxiv",
            "text": """
            We propose a new simple network architecture based on attention mechanisms...

            References
            [1] Bahdanau et al. (2015). "Neural Machine Translation...". ICLR.
            [2] Sutskever et al. (2014). "Sequence to Sequence...". NIPS.
            [3] Hochreiter & Schmidhuber (1997). "LSTM". Neural Computation.
            """,
        }
    ]

    # Configure for deep search
    config = CitationExpansionConfig(
        enabled=True,
        max_depth=2,  # Go 2 levels deep
        max_citations_per_paper=15,
        max_concurrent_fetches=5,
        only_academic=True,
    )

    pipeline = CitationPipeline(config)
    result = await pipeline.run_expansion_phase(sample_docs, "deep_search_001")

    print("\n📊 Deep Search Results:")
    print(f"  Initial: {result['stats']['initial_count']}")
    print(f"  Expansion: {result['stats']['cited_papers_found']} new papers")
    print(f"  Total literature graph: {result['stats']['initial_count'] + result['stats']['cited_papers_found']}")

    # Sort by influence
    if result["new_documents"]:
        top_papers = sorted(
            result["new_documents"], key=lambda x: x.get("influence_score", 0), reverse=True
        )[:5]

        print("\n⭐ Top 5 Most Cited Papers:")
        for i, paper in enumerate(top_papers, 1):
            print(f"  {i}. {paper.get('title', 'Unknown')} ({paper.get('year', '?')})")
            print(f"     Influence: {paper.get('influence_score', 0):.2f}")


async def example_filtering():
    """Filter and process expanded citations."""
    print("\n" + "=" * 60)
    print("Example 3: Citation Filtering & Analysis")
    print("=" * 60)

    sample_docs = [
        {
            "title": "GPT-3: Language Models are Few-Shot Learners",
            "url": "https://arxiv.org/abs/2005.14165",
            "source_type": "academic_paper",
            "platform": "arxiv",
            "text": """
            Recent work has shown that scaling up language models greatly improves
            performance on most NLP tasks and few-shot learning.

            References
            [1] Brown et al. (2020). "Language Models are Few-Shot...". arXiv:2005.14165
            [2] Vaswani et al. (2017). "Attention Is All You Need". arXiv:1706.03762
            [3] Devlin et al. (2018). "BERT: Pre-training...". arXiv:1810.04805
            """,
        }
    ]

    config = CitationExpansionConfig(enabled=True, max_depth=1, max_citations_per_paper=20)

    pipeline = CitationPipeline(config)
    result = await pipeline.run_expansion_phase(sample_docs, "filtering_001")

    # Filter by influence
    all_papers = sample_docs + result["new_documents"]
    high_influence = [p for p in all_papers if p.get("influence_score", 0) > 0.6]
    recent = [p for p in all_papers if int(p.get("year", 0)) >= 2017]

    print(f"\n📚 Total papers: {len(all_papers)}")
    print(f"   High influence (>0.6): {len(high_influence)}")
    print(f"   Published ≥2017: {len(recent)}")

    print("\n🎯 Foundational papers (2015-2017):")
    foundational = [
        p
        for p in all_papers
        if 2015 <= int(p.get("year", 0)) <= 2017 and p.get("influence_score", 0) > 0.5
    ]
    for paper in foundational:
        print(f"  • {paper.get('title', 'Unknown')} ({paper.get('year')})")


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Citation Graph Agent - Examples")
    print("=" * 60)

    # Run examples
    await example_basic()
    await example_deep_search()
    await example_filtering()

    print("\n" + "=" * 60)
    print("✅ Examples complete!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
