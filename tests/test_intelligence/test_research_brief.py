"""Tests for ResearchBrief and ResearchPhase dataclasses."""

from __future__ import annotations

from aria.engine.intelligence.research_brief import ResearchBrief, ResearchPhase


# ---------------------------------------------------------------------------
# ResearchPhase
# ---------------------------------------------------------------------------

def test_research_phase_defaults():
    phase = ResearchPhase(
        name="landscape",
        goal="understand the topic",
        queries=["overview", "introduction"],
        source_types=["web", "wikipedia"],
    )
    assert phase.max_docs == 50
    assert phase.depends_on is None


def test_research_phase_stores_values():
    phase = ResearchPhase(
        name="deep_dive",
        goal="deep analysis",
        queries=["research paper X", "X study"],
        source_types=["academic"],
        max_docs=150,
        depends_on="landscape",
    )
    assert phase.name == "deep_dive"
    assert phase.max_docs == 150
    assert phase.depends_on == "landscape"


# ---------------------------------------------------------------------------
# ResearchBrief
# ---------------------------------------------------------------------------

def test_research_brief_defaults():
    brief = ResearchBrief(original_topic="climate change")
    assert brief.resolved_topic == ""
    assert brief.audience == "general"
    assert brief.purpose == "informational"
    assert brief.depth == "medium"
    assert brief.time_range == "all"
    assert brief.geography == "global"
    assert brief.key_questions == []
    assert brief.phases == []


def test_research_brief_to_dict_structure():
    brief = ResearchBrief(
        original_topic="depression",
        resolved_topic="clinical depression",
        audience="professional",
        purpose="clinical",
        key_questions=["What are the causes?", "What are the treatments?"],
        entities=["SSRIs", "CBT"],
        must_have_sources=["academic"],
        skip_sources=["reddit"],
    )
    d = brief.to_dict()
    assert d["original_topic"] == "depression"
    assert d["resolved_topic"] == "clinical depression"
    assert d["context"]["audience"] == "professional"
    assert "What are the causes?" in d["key_questions"]
    assert "academic" in d["must_have_sources"]
    assert "reddit" in d["skip_sources"]


def test_research_brief_to_dict_with_phases():
    phase = ResearchPhase(
        name="landscape",
        goal="overview",
        queries=["depression overview"],
        source_types=["web"],
    )
    brief = ResearchBrief(original_topic="depression", phases=[phase])
    d = brief.to_dict()
    assert len(d["phases"]) == 1
    assert d["phases"][0]["name"] == "landscape"
    assert d["phases"][0]["queries"] == ["depression overview"]


def test_research_brief_to_dict_empty_phases():
    brief = ResearchBrief(original_topic="test")
    d = brief.to_dict()
    assert d["phases"] == []
