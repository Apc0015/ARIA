"""Citation Intelligence — extract, resolve, and follow reference chains."""

from aria.engine.citation.extractor import CitationExtractor, extract_citations
from aria.engine.citation.resolver import CitationResolver
from aria.engine.citation.agent import CitationAgent

__all__ = ["CitationExtractor", "extract_citations", "CitationResolver", "CitationAgent"]
