"""Sources listing endpoint — returns all source IDs with their group classification."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

# Authoritative group classification for all registered sources.
# "advanced" sources are hidden in the UI by default (OSINT, niche tools).
_SOURCE_GROUP: dict[str, str] = {
    # ProPublica — standard but optional (needs key for Congress API)
    # (not in advanced group — no key still works for nonprofits)

    # OSINT — advanced
    "shodan":          "advanced",
    "censys":          "advanced",
    "virustotal":      "advanced",
    "haveibeenpwned":  "advanced",
    "whoxy":           "advanced",
    "hunter":          "advanced",
    "social_searcher": "advanced",
    # Specialized — advanced
    "jobs_boards":     "advanced",
}

# All known source IDs (standard group unless overridden above)
_ALL_SOURCES = [
    # Web
    "web", "reddit", "hackernews", "medium", "devto", "substack", "rss",
    "wikipedia", "pdf", "github", "government", "notion",
    # Academic
    "arxiv", "pubmed", "semantic_scholar", "zotero",
    # Social
    "twitter", "slack",
    # Media
    "youtube", "vimeo", "podcast",
    # Data
    "jobs_boards", "internet_archive",
    # New academic
    "crossref", "core_ac", "europe_pmc", "ssrn", "base_search",
    # New knowledge
    "wikidata",
    # New specialized
    "propublica",
    # New social
    "mastodon",
    # OSINT
    "shodan", "censys", "virustotal", "haveibeenpwned", "whoxy", "hunter",
    "social_searcher",
]


@router.get("/api/sources")
async def list_sources():
    """List all available source IDs with their group classification.

    Returns:
        JSON with a list of sources, each containing id and group fields.
    """
    return {
        "sources": [
            {
                "id": source_id,
                "group": _SOURCE_GROUP.get(source_id, "standard"),
            }
            for source_id in _ALL_SOURCES
        ]
    }
