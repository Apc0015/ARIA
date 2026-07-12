"""Sources listing endpoint — returns all source IDs with their group classification."""

from __future__ import annotations

from fastapi import APIRouter

from aria.engine.orchestrator.collection import _COLLECTOR_REGISTRY

router = APIRouter()

# Authoritative group classification for all registered sources.
# "advanced" sources are hidden in the UI by default (niche tools).
_SOURCE_GROUP: dict[str, str] = {
    # Specialized — advanced
    "jobs_boards": "advanced",
}

_SOURCE_CATEGORY: dict[str, str] = {
    **dict.fromkeys(
        [
            "web",
            "reddit",
            "hackernews",
            "medium",
            "devto",
            "substack",
            "rss",
            "wikipedia",
            "pdf",
            "github",
            "government",
            "notion",
            "wikidata",
            "stackoverflow",
            "news",
            "multilingual",
        ],
        "web",
    ),
    **dict.fromkeys(
        [
            "arxiv",
            "pubmed",
            "semantic_scholar",
            "zotero",
            "crossref",
            "core_ac",
            "europe_pmc",
            "ssrn",
            "base_search",
            "academic",
            "academic_platforms",
            "open_alex",
        ],
        "academic",
    ),
    **dict.fromkeys(["twitter", "slack", "mastodon"], "social"),
    **dict.fromkeys(["youtube", "vimeo", "podcast"], "media"),
    **dict.fromkeys(
        [
            "jobs_boards",
            "internet_archive",
            "propublica",
            "world_bank",
            "un_data",
            "who",
            "imf",
            "fred",
            "gdelt",
            "clinical_trials",
            "sec_edgar",
            "eurostat",
            "intl_gov",
        ],
        "data",
    ),
}

_SOURCE_NAMES: dict[str, str] = {
    "web": "Web Search",
    "reddit": "Reddit",
    "hackernews": "Hacker News",
    "medium": "Medium",
    "devto": "Dev.to",
    "substack": "Substack",
    "rss": "RSS Feeds",
    "wikipedia": "Wikipedia",
    "pdf": "PDF",
    "github": "GitHub",
    "government": "Government",
    "notion": "Notion",
    "stackoverflow": "Stack Overflow",
    "news": "News",
    "multilingual": "Multilingual",
    "arxiv": "arXiv",
    "pubmed": "PubMed",
    "semantic_scholar": "Semantic Scholar",
    "zotero": "Zotero",
    "academic": "Academic",
    "academic_platforms": "Academic Platforms",
    "open_alex": "OpenAlex",
    "twitter": "Twitter / X",
    "slack": "Slack",
    "youtube": "YouTube",
    "vimeo": "Vimeo",
    "podcast": "Podcast",
    "crossref": "CrossRef",
    "core_ac": "CORE",
    "europe_pmc": "Europe PMC",
    "ssrn": "SSRN",
    "base_search": "BASE Search",
    "wikidata": "Wikidata",
    "internet_archive": "Internet Archive",
    "propublica": "ProPublica",
    "mastodon": "Mastodon",
    "jobs_boards": "Jobs Boards",
    "world_bank": "World Bank",
    "un_data": "UN Data",
    "who": "WHO",
    "imf": "IMF",
    "fred": "FRED",
    "gdelt": "GDELT",
    "clinical_trials": "ClinicalTrials",
    "sec_edgar": "SEC EDGAR",
    "eurostat": "Eurostat",
    "intl_gov": "International Government",
}

# All source IDs come from the executable collector registry. Do not advertise
# sources unless the backend can import and dispatch them.
_ALL_SOURCES = list(_COLLECTOR_REGISTRY.keys())


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
                "category": _SOURCE_CATEGORY.get(source_id, "web"),
                "name": _SOURCE_NAMES.get(source_id, source_id),
            }
            for source_id in _ALL_SOURCES
        ],
        "total": len(_ALL_SOURCES),
        "standard": sum(
            1
            for source_id in _ALL_SOURCES
            if _SOURCE_GROUP.get(source_id, "standard") == "standard"
        ),
        "advanced": sum(
            1
            for source_id in _ALL_SOURCES
            if _SOURCE_GROUP.get(source_id, "standard") == "advanced"
        ),
    }
