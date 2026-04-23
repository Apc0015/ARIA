"""Academic and scholarly sources."""

from aria.sources.academic.arxiv import ArxivCollector
from aria.sources.academic.pubmed import PubmedCollector
from aria.sources.academic.semantic_scholar import SemanticScholarCollector

__all__ = [
    "ArxivCollector",
    "PubmedCollector",
    "SemanticScholarCollector",
]
