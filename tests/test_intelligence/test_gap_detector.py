"""Tests for aria.engine.intelligence.gap_detector (no LLM required)."""

from __future__ import annotations

import json
import pytest

from aria.engine.intelligence.gap_detector import (
    _empty_result,
    _parse_gap_response,
    _summarise_corpus,
    detect_gaps,
)


# ---------------------------------------------------------------------------
# _empty_result
# ---------------------------------------------------------------------------

def test_empty_result_structure():
    r = _empty_result()
    assert r["gaps"] == []
    assert r["has_gaps"] is False
    assert "follow_up_queries" in r
    assert "answered_questions" in r
    assert "missing_perspectives" in r
    assert "recommended_sources" in r


# ---------------------------------------------------------------------------
# _summarise_corpus
# ---------------------------------------------------------------------------

def test_summarise_corpus_platform_counts():
    docs = [
        {"platform": "web"},
        {"platform": "web"},
        {"platform": "reddit"},
    ]
    summary = _summarise_corpus(docs)
    assert summary["platforms"]["web"] == 2
    assert summary["platforms"]["reddit"] == 1


def test_summarise_corpus_missing_platform():
    docs = [{"title": "no platform field"}]
    summary = _summarise_corpus(docs)
    assert summary["platforms"]["unknown"] == 1


def test_summarise_corpus_source_types():
    docs = [
        {"source_type": "academic"},
        {"source_type": "academic"},
        {"source_type": "news"},
    ]
    summary = _summarise_corpus(docs)
    assert summary["source_types"]["academic"] == 2
    assert summary["source_types"]["news"] == 1


def test_summarise_corpus_empty():
    summary = _summarise_corpus([])
    assert summary["platforms"] == {}
    assert summary["source_types"] == {}


# ---------------------------------------------------------------------------
# _parse_gap_response
# ---------------------------------------------------------------------------

def test_parse_gap_response_valid_json():
    payload = {
        "answered_questions": ["What is X?"],
        "gaps": [
            {
                "question": "What are the risks?",
                "reason": "No docs covered risks",
                "follow_up_queries": ["X risks", "X dangers"],
            }
        ],
        "missing_perspectives": ["industry view"],
        "recommended_sources": ["academic"],
    }
    result = _parse_gap_response(json.dumps(payload))
    assert len(result["gaps"]) == 1
    assert result["gaps"][0]["question"] == "What are the risks?"


def test_parse_gap_response_json_embedded_in_text():
    text = 'Here is my analysis:\n```json\n' + json.dumps({
        "gaps": [{"question": "Q", "reason": "R", "follow_up_queries": []}],
        "answered_questions": [],
        "missing_perspectives": [],
        "recommended_sources": [],
    }) + '\n```'
    result = _parse_gap_response(text)
    assert len(result["gaps"]) == 1


def test_parse_gap_response_invalid_json_returns_empty():
    result = _parse_gap_response("not json at all")
    assert result == _empty_result()


def test_parse_gap_response_json_without_gaps_key_returns_empty():
    result = _parse_gap_response('{"something": "else"}')
    assert result == _empty_result()


# ---------------------------------------------------------------------------
# detect_gaps — no-LLM fast path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_gaps_empty_docs_returns_empty():
    result = await detect_gaps([], topic="quantum computing")
    assert result["has_gaps"] is False
    assert result["gaps"] == []
    assert result["follow_up_queries"] == []


@pytest.mark.asyncio
async def test_detect_gaps_returns_dict_with_required_keys():
    # With real docs but no LLM configured, should return graceful empty result
    docs = [
        {"title": "Intro to X", "platform": "web", "source_type": "article"},
        {"title": "X in practice", "platform": "academic", "source_type": "paper"},
    ]
    result = await detect_gaps(docs, topic="X", intent="understand X", sub_questions=["What is X?"])
    assert isinstance(result, dict)
    for key in ("gaps", "follow_up_queries", "has_gaps", "answered_questions"):
        assert key in result
