"""Phased Planner — converts a ResearchBrief into 4 ordered collection phases."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aria.engine.intelligence.research_brief import ResearchBrief, ResearchPhase

# Source type mappings per phase
_LANDSCAPE_SOURCES = ["web", "wikipedia", "news"]
_DEEP_DIVE_SOURCES = ["academic", "arxiv", "pubmed", "semantic_scholar", "zotero"]
_CRITICAL_SOURCES = ["news", "web", "academic", "government"]
_LATEST_SOURCES = ["arxiv", "news", "academic"]

# Sources that prefer academic content
_ACADEMIC_TOPICS = {"medicine", "biology", "chemistry", "physics", "psychology",
                    "neuroscience", "climate", "economics", "engineering"}


def build_phases(brief: ResearchBrief) -> list[ResearchPhase]:
    """Convert a ResearchBrief into 4 ordered ResearchPhases."""
    year = datetime.now().year
    t = brief.resolved_topic or brief.original_topic
    focus = brief.focus
    questions = brief.key_questions
    entities = brief.entities

    phases = [
        _phase_landscape(t, focus, entities, brief),
        _phase_deep_dive(t, focus, questions, entities, brief),
        _phase_critical(t, focus, brief),
        _phase_latest(t, focus, year, brief),
    ]

    # Apply source strategy from brief
    for phase in phases:
        phase.source_types = [
            s for s in phase.source_types if s not in brief.skip_sources
        ]
        for must in brief.must_have_sources:
            if must not in phase.source_types:
                phase.source_types.append(must)

    return phases


def _phase_landscape(
    topic: str, focus: str, entities: list[str], brief: ResearchBrief
) -> ResearchPhase:
    base = focus or topic
    queries = [
        f"{topic} overview",
        f"what is {topic}",
        f"{topic} explained",
        f"{base} introduction",
    ]
    if entities:
        queries.append(f"{entities[0]} {topic}" if entities else topic)

    return ResearchPhase(
        name="landscape",
        goal=f"Understand the big picture of '{topic}'",
        queries=_dedupe(queries)[:6],
        source_types=_landscape_sources(brief),
        max_docs=50,
    )


def _phase_deep_dive(
    topic: str, focus: str, questions: list[str], entities: list[str], brief: ResearchBrief
) -> ResearchPhase:
    queries: list[str] = []

    # One query per key question
    for q in questions[:8]:
        # Convert question to search query
        q_query = q.replace("?", "").replace("What are", "").replace("How does", "").strip()
        queries.append(q_query)

    # Entity-based queries
    for entity in entities[:3]:
        queries.append(f"{entity} {focus or topic}")

    # Focus-specific
    if focus:
        queries.extend([
            f"{topic} {focus} research",
            f"{topic} {focus} study",
            f"{focus} {topic} evidence",
        ])
    else:
        queries.extend([
            f"{topic} research paper",
            f"{topic} case study",
            f"{topic} evidence",
        ])

    sources = _deep_sources(brief)

    return ResearchPhase(
        name="deep_dive",
        goal=f"Answer the {len(questions)} key research questions about '{topic}'",
        queries=_dedupe(queries)[:15],
        source_types=sources,
        max_docs=150,
        depends_on="landscape",
    )


def _phase_critical(
    topic: str, focus: str, brief: ResearchBrief
) -> ResearchPhase:
    base = focus or topic
    queries = [
        f"{topic} limitations problems",
        f"{topic} criticism risks",
        f"{base} failure cases",
        f"{topic} controversy debate",
        f"{topic} side effects dangers" if _is_health_topic(topic) else f"{topic} drawbacks",
        f"{topic} what doesn't work",
    ]

    # Excluded angles become negative queries
    for excluded in brief.excluded_angles:
        queries = [q for q in queries if excluded.lower() not in q.lower()]

    return ResearchPhase(
        name="critical",
        goal=f"Find counter-arguments, risks, and failures related to '{topic}'",
        queries=_dedupe(queries)[:8],
        source_types=_CRITICAL_SOURCES,
        max_docs=50,
        depends_on="deep_dive",
    )


def _phase_latest(
    topic: str, focus: str, year: int, brief: ResearchBrief
) -> ResearchPhase:
    base = focus or topic
    prev_year = year - 1
    queries = [
        f"{topic} {year}",
        f"{topic} latest {year}",
        f"{base} breakthrough {year}",
        f"{topic} new research {prev_year} {year}",
        f"{topic} recent developments",
        f"{base} update {year}",
    ]

    # Time range adjustments
    if brief.time_range == "latest":
        queries = [q for q in queries if str(year) in q or "recent" in q or "latest" in q]
    elif brief.time_range == "5years":
        queries.append(f"{topic} {year - 5} to {year}")

    return ResearchPhase(
        name="latest",
        goal=f"Find newest {year} developments on '{topic}'",
        queries=_dedupe(queries)[:8],
        source_types=_LATEST_SOURCES,
        max_docs=50,
        depends_on="critical",
    )


def _landscape_sources(brief: ResearchBrief) -> list[str]:
    sources = list(_LANDSCAPE_SOURCES)
    if brief.audience in ("professional", "academic"):
        sources = ["academic"] + sources
    return sources


def _deep_sources(brief: ResearchBrief) -> list[str]:
    sources = list(_DEEP_DIVE_SOURCES)
    if brief.audience == "general":
        sources = ["web", "wikipedia"] + sources
    if "zotero" in brief.must_have_sources:
        if "zotero" not in sources:
            sources.insert(0, "zotero")
    return sources


def _is_health_topic(topic: str) -> bool:
    health_keywords = {"depression", "anxiety", "cancer", "diabetes", "drug", "therapy",
                       "treatment", "medicine", "medical", "disease", "health", "vaccine"}
    return any(kw in topic.lower() for kw in health_keywords)


def _dedupe(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for q in queries:
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            result.append(q)
    return result


def brief_to_flat_queries(brief: ResearchBrief, max_total: int = 30) -> list[str]:
    """Flatten all phase queries into a single deduplicated list (fallback use)."""
    all_queries: list[str] = []
    for phase in brief.phases:
        all_queries.extend(phase.queries)
    return _dedupe(all_queries)[:max_total]
