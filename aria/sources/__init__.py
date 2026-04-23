"""
Collection sources and agents.

Organized by domain:
- web: General web search and discovery
- academic: Scholarly sources (arXiv, PubMed, etc.)
- media: Video, podcast, and multimedia sources
- social: Social media and Reddit
- llm: LLM ensemble sources
- knowledge: Zotero, Notion, other knowledge bases
"""

from aria.sources.base import BaseCollector
from aria.sources.registry import SourceRegistry

__all__ = [
    "BaseCollector",
    "SourceRegistry",
]
