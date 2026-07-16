"""Health and info endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from aria.engine.ensemble.providers import STATIC_MODEL_CATALOG as PROVIDERS

router = APIRouter()

CONTENT_TYPES = [
    "academic_paper", "news_article", "forum_post", "social_media",
    "technical_doc", "video_transcript", "encyclopedia", "opinion_essay",
    "gov_policy", "data_report",
]


@router.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "5.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/info")
async def info():
    """Platform information."""
    return {
        "name": "ARIA",
        "title": "Agentic Research Intelligence Architecture",
        "version": "5.0.0",
        "description": "Fully automated research collection and intelligence platform",
        "agents": {
            "total": 37,
            "web": 16,
            "academic": 5,
            "data": 8,
            "social": 7,
            "media": 4,
            "personal": 5,
        },
        "features": [
            "Query expansion (1 topic -> 5-8 queries)",
            "Parallel collection (37+ collectors)",
            "Domain-based collection (12 domains)",
            "Country filter (44 countries, 6 regions)",
            "Citation Intelligence (DOI/arXiv/PMID, depth 1-3)",
            "LLM ensemble (OpenRouter, OpenAI, Anthropic, Ollama)",
            "Smart content detection (10 types)",
            "Multi-format export (6 formats)",
            "Relevance scoring (0-1)",
            "Knowledge graph + gap analysis",
        ],
        "llm_providers": list(PROVIDERS.keys()),
        "content_types": CONTENT_TYPES,
        "export_formats": ["json", "csv", "markdown", "html"],
    }
