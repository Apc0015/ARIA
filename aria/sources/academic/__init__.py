"""Academic and scholarly sources."""

__all__ = []

# Gracefully skip imports if backend modules not available
try:
    from aria.sources.academic.arxiv import ArxivCollector
    __all__.append("ArxivCollector")
except (ImportError, ModuleNotFoundError):
    pass

try:
    from aria.sources.academic.pubmed import PubmedCollector
    __all__.append("PubmedCollector")
except (ImportError, ModuleNotFoundError):
    pass

try:
    from aria.sources.academic.semantic_scholar import SemanticScholarCollector
    __all__.append("SemanticScholarCollector")
except (ImportError, ModuleNotFoundError):
    pass

# Always available
try:
    from aria.sources.academic.citations import CitationGraphCollector
    __all__.append("CitationGraphCollector")
except (ImportError, ModuleNotFoundError):
    pass
