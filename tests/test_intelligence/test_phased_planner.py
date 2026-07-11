"""Tests for aria.engine.intelligence.phased_planner (pure logic, no LLM)."""

from __future__ import annotations

from datetime import datetime

import pytest

from aria.engine.intelligence.phased_planner import (
    _dedupe,
    _is_health_topic,
    brief_to_flat_queries,
    build_phases,
)
from aria.engine.intelligence.research_brief import ResearchBrief, ResearchPhase


# ---------------------------------------------------------------------------
# _dedupe
# ---------------------------------------------------------------------------

def test_dedupe_removes_duplicates():
    result = _dedupe(["quantum computing", "Quantum Computing", "quantum computing"])
    assert result == ["quantum computing"]


def test_dedupe_preserves_order():
    queries = ["alpha", "beta", "gamma"]
    assert _dedupe(queries) == queries


def test_dedupe_strips_whitespace():
    # _dedupe strips each item before adding; "  query  " and "query" are the same after strip
    result = _dedupe(["  query  ", "query"])
    assert result == ["query"]  # stripped form kept, duplicate dropped


def test_dedupe_empty():
    assert _dedupe([]) == []


def test_dedupe_filters_empty_strings():
    result = _dedupe(["valid", "", "  ", "also valid"])
    assert "" not in result
    assert "  " not in result


# ---------------------------------------------------------------------------
# _is_health_topic
# ---------------------------------------------------------------------------

def test_is_health_topic_true_cases():
    assert _is_health_topic("depression treatment") is True
    assert _is_health_topic("cancer therapy") is True
    assert _is_health_topic("diabetes medicine") is True
    assert _is_health_topic("vaccine effectiveness") is True


def test_is_health_topic_false_cases():
    assert _is_health_topic("quantum computing") is False
    assert _is_health_topic("climate policy") is False
    assert _is_health_topic("machine learning") is False


def test_is_health_topic_case_insensitive():
    assert _is_health_topic("DEPRESSION") is True
    assert _is_health_topic("Health Systems") is True


# ---------------------------------------------------------------------------
# build_phases
# ---------------------------------------------------------------------------

def _make_brief(topic: str = "quantum computing", **kwargs) -> ResearchBrief:
    return ResearchBrief(original_topic=topic, resolved_topic=topic, **kwargs)


def test_build_phases_returns_four_phases():
    brief = _make_brief()
    phases = build_phases(brief)
    assert len(phases) == 4


def test_build_phases_correct_names():
    phases = build_phases(_make_brief())
    names = [p.name for p in phases]
    assert names == ["landscape", "deep_dive", "critical", "latest"]


def test_build_phases_landscape_has_source_types():
    phases = build_phases(_make_brief())
    landscape = phases[0]
    assert len(landscape.source_types) > 0
    assert "web" in landscape.source_types or "wikipedia" in landscape.source_types


def test_build_phases_deep_dive_has_more_docs():
    phases = build_phases(_make_brief())
    landscape = next(p for p in phases if p.name == "landscape")
    deep_dive = next(p for p in phases if p.name == "deep_dive")
    assert deep_dive.max_docs >= landscape.max_docs


def test_build_phases_skip_sources_respected():
    brief = _make_brief(skip_sources=["reddit"])
    phases = build_phases(brief)
    for phase in phases:
        assert "reddit" not in phase.source_types


def test_build_phases_must_have_sources_added():
    brief = _make_brief(must_have_sources=["zotero"])
    phases = build_phases(brief)
    for phase in phases:
        assert "zotero" in phase.source_types


def test_build_phases_queries_are_nonempty():
    phases = build_phases(_make_brief("climate change"))
    for phase in phases:
        assert len(phase.queries) > 0
        for q in phase.queries:
            assert isinstance(q, str)
            assert len(q.strip()) > 0


def test_build_phases_latest_includes_current_year():
    year = datetime.now().year
    phases = build_phases(_make_brief("AI safety"))
    latest = next(p for p in phases if p.name == "latest")
    joined = " ".join(latest.queries)
    assert str(year) in joined


def test_build_phases_critical_has_depends_on_deep_dive():
    phases = build_phases(_make_brief())
    critical = next(p for p in phases if p.name == "critical")
    assert critical.depends_on == "deep_dive"


def test_build_phases_academic_audience_adds_academic_source():
    brief = _make_brief(audience="academic")
    phases = build_phases(brief)
    landscape = phases[0]
    assert "academic" in landscape.source_types


def test_build_phases_with_key_questions():
    brief = _make_brief(
        topic="depression",
        key_questions=["What causes depression?", "How is it treated?"],
    )
    phases = build_phases(brief)
    deep_dive = next(p for p in phases if p.name == "deep_dive")
    # Key questions should influence deep-dive queries
    assert len(deep_dive.queries) > 0


def test_build_phases_health_topic_critical_queries():
    phases = build_phases(_make_brief("cancer treatment"))
    critical = next(p for p in phases if p.name == "critical")
    joined = " ".join(critical.queries)
    assert "side effects" in joined or "dangers" in joined


# ---------------------------------------------------------------------------
# brief_to_flat_queries
# ---------------------------------------------------------------------------

def test_brief_to_flat_queries_deduplicates():
    phase1 = ResearchPhase("a", "goal", ["shared query", "unique a"], ["web"])
    phase2 = ResearchPhase("b", "goal", ["shared query", "unique b"], ["academic"])
    brief = ResearchBrief(original_topic="test", phases=[phase1, phase2])
    queries = brief_to_flat_queries(brief)
    assert queries.count("shared query") == 1


def test_brief_to_flat_queries_respects_max_total():
    phase = ResearchPhase("a", "g", [f"query {i}" for i in range(50)], ["web"])
    brief = ResearchBrief(original_topic="test", phases=[phase])
    queries = brief_to_flat_queries(brief, max_total=10)
    assert len(queries) <= 10


def test_brief_to_flat_queries_empty_phases():
    brief = ResearchBrief(original_topic="test")
    assert brief_to_flat_queries(brief) == []


def test_brief_to_flat_queries_uses_build_phases_output():
    brief = _make_brief("machine learning")
    brief.phases = build_phases(brief)
    queries = brief_to_flat_queries(brief)
    assert len(queries) > 0
    assert len(queries) <= 30
