"""Agent surfaces for ARIA."""

from aria.agents.academic import AcademicAgent
from aria.agents.base import BaseAgent
from aria.agents.github import GitHubAgent
from aria.agents.government import GovernmentAgent
from aria.agents.llm_ensemble import LLMEnsembleAgent
from aria.agents.multilingual import MultilingualAgent
from aria.agents.news import NewsAgent
from aria.agents.pdf import PDFAgent
from aria.agents.web import WebAgent
from aria.agents.youtube import YouTubeAgent

__all__ = [
    "AcademicAgent",
    "BaseAgent",
    "GitHubAgent",
    "GovernmentAgent",
    "LLMEnsembleAgent",
    "MultilingualAgent",
    "NewsAgent",
    "PDFAgent",
    "WebAgent",
    "YouTubeAgent",
]
