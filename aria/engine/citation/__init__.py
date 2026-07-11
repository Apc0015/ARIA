"""Citation Intelligence — extract, resolve, and follow reference chains."""

from aria.engine.citation.extractor import CitationExtractor, extract_citations
from aria.engine.citation.resolver import CitationResolver
from aria.engine.citation.agent import CitationAgent
from aria.engine.citation.ref_parser import ReferenceParser, RefRecord
from aria.engine.citation.seed import SeedFetcher, SeedResult, CorpusRecord, fetch_seed

__all__ = [
    "CitationExtractor",
    "extract_citations",
    "CitationResolver",
    "CitationAgent",
    "ReferenceParser",
    "RefRecord",
    "SeedFetcher",
    "SeedResult",
    "CorpusRecord",
    "fetch_seed",
]
