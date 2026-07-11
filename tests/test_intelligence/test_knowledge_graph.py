"""Tests for KnowledgeGraph (pure state/merge logic, no LLM required)."""

from __future__ import annotations

import pytest

from aria.engine.intelligence.knowledge_graph import KnowledgeGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(title="Test Doc", url="https://example.com", platform="web",
              source_type="article", relevance_score=0.8, text="Some content here."):
    return {
        "title": title,
        "url": url,
        "platform": platform,
        "source_type": source_type,
        "relevance_score": relevance_score,
        "text": text,
    }


def _make_extraction(people=None, orgs=None, technologies=None, concepts=None,
                     claims=None, relationships=None, url="https://example.com"):
    return {
        "entities": {
            "people": people or [],
            "organizations": orgs or [],
            "technologies": technologies or [],
            "concepts": concepts or [],
            "locations": [],
        },
        "claims": claims or [],
        "relationships": relationships or [],
        "sentiment_on_topic": "neutral",
        "key_findings": [],
        "_source_url": url,
        "_source_title": "Test Doc",
        "_platform": "web",
    }


# ---------------------------------------------------------------------------
# KnowledgeGraph construction
# ---------------------------------------------------------------------------

def test_knowledge_graph_init_empty():
    kg = KnowledgeGraph()
    assert kg._entities == {}
    assert kg._claims == []
    assert kg._contradictions == []


def test_merge_entities_adds_entity():
    kg = KnowledgeGraph()
    doc = _make_doc()
    extraction = _make_extraction(people=["Alan Turing"], url=doc["url"])
    kg._merge_entities(extraction, doc)
    assert "alan turing" in kg._entities
    assert kg._entities["alan turing"]["name"] == "Alan Turing"
    assert kg._entities["alan turing"]["type"] == "people"


def test_merge_entities_tracks_mention_count():
    kg = KnowledgeGraph()
    doc1 = _make_doc(url="https://a.com")
    doc2 = _make_doc(url="https://b.com")
    kg._merge_entities(_make_extraction(people=["Alan Turing"], url="https://a.com"), doc1)
    kg._merge_entities(_make_extraction(people=["Alan Turing"], url="https://b.com"), doc2)
    assert kg._entities["alan turing"]["mention_count"] == 2


def test_merge_entities_multiple_types():
    kg = KnowledgeGraph()
    doc = _make_doc()
    extraction = _make_extraction(
        people=["Elon Musk"],
        orgs=["Tesla"],
        technologies=["Electric Vehicle"],
        concepts=["Sustainability"],
    )
    kg._merge_entities(extraction, doc)
    assert "elon musk" in kg._entities
    assert "tesla" in kg._entities
    assert "electric vehicle" in kg._entities
    assert "sustainability" in kg._entities


def test_merge_entities_skips_empty_names():
    kg = KnowledgeGraph()
    doc = _make_doc()
    extraction = _make_extraction(people=["", "  ", "Valid Name"])
    kg._merge_entities(extraction, doc)
    assert "" not in kg._entities
    assert "  " not in kg._entities
    assert "valid name" in kg._entities


def test_merge_entities_accumulates_claims():
    kg = KnowledgeGraph()
    doc = _make_doc()
    extraction = _make_extraction(claims=[
        {"claim": "X causes Y", "confidence": "high", "subject": "X"},
        {"claim": "Y prevents Z", "confidence": "medium", "subject": "Y"},
    ])
    kg._merge_entities(extraction, doc)
    assert len(kg._claims) == 2


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------

def test_to_dict_structure():
    kg = KnowledgeGraph()
    d = kg.to_dict()
    assert "top_entities" in d
    assert "total_entities" in d
    assert "total_claims" in d
    assert "contradictions" in d
    assert "has_contradictions" in d


def test_to_dict_empty_graph():
    kg = KnowledgeGraph()
    d = kg.to_dict()
    assert d["top_entities"] == []
    assert d["total_entities"] == 0
    assert d["total_claims"] == 0
    assert d["contradictions"] == []
    assert d["has_contradictions"] is False


def test_to_dict_counts_entities():
    kg = KnowledgeGraph()
    doc = _make_doc()
    kg._merge_entities(_make_extraction(people=["Alice", "Bob"], orgs=["Acme"]), doc)
    d = kg.to_dict()
    assert d["total_entities"] == 3


def test_to_dict_top_entities_sorted_by_mention():
    kg = KnowledgeGraph()
    for i in range(3):
        doc = _make_doc(url=f"https://src{i}.com")
        kg._merge_entities(_make_extraction(people=["Popular"], url=f"https://src{i}.com"), doc)
    doc2 = _make_doc(url="https://once.com")
    kg._merge_entities(_make_extraction(people=["Rare"], url="https://once.com"), doc2)

    d = kg.to_dict()
    top = d["top_entities"]
    assert top[0]["name"] == "Popular"


# ---------------------------------------------------------------------------
# get_top_entities / get_contradictions
# ---------------------------------------------------------------------------

def test_get_top_entities_empty():
    kg = KnowledgeGraph()
    assert kg.get_top_entities() == []


def test_get_top_entities_respects_n():
    kg = KnowledgeGraph()
    doc = _make_doc()
    kg._merge_entities(
        _make_extraction(people=["A", "B", "C", "D", "E"]), doc
    )
    assert len(kg.get_top_entities(n=3)) == 3


def test_get_contradictions_empty():
    kg = KnowledgeGraph()
    assert kg.get_contradictions() == []


# ---------------------------------------------------------------------------
# summary (string output)
# ---------------------------------------------------------------------------

def test_summary_returns_string():
    kg = KnowledgeGraph()
    s = kg.summary()
    assert isinstance(s, str)
    assert "Entities" in s
    assert "Claims" in s


def test_summary_reflects_state():
    kg = KnowledgeGraph()
    doc = _make_doc()
    kg._merge_entities(_make_extraction(people=["Marie Curie"]), doc)
    s = kg.summary()
    assert "Marie Curie" in s


# ---------------------------------------------------------------------------
# build_from_documents — no-LLM path (graceful degradation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_from_documents_empty_list():
    kg = KnowledgeGraph()
    await kg.build_from_documents([], topic="test")
    assert kg._entities == {}
    assert kg._claims == []


@pytest.mark.asyncio
async def test_build_from_documents_short_text_skipped():
    # Text < 100 chars is skipped by _extract_from_doc, no LLM needed
    kg = KnowledgeGraph()
    docs = [_make_doc(text="Too short.")]
    await kg.build_from_documents(docs, topic="test")
    assert isinstance(kg._entities, dict)
