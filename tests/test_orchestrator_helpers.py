"""Tests for orchestrator helper functions and validate_credentials path."""

from __future__ import annotations

import json
import pytest

from aria.engine.orchestrator.core import (
    InfoCollectorOrchestrator,
    RunResult,
    _content_fingerprint,
    _count_by_platform,
    _flatten_plan_queries,
    _heuristic_plan,
)


# ---------------------------------------------------------------------------
# _content_fingerprint
# ---------------------------------------------------------------------------

def test_fingerprint_is_string():
    fp = _content_fingerprint("some text content here")
    assert isinstance(fp, str)
    assert len(fp) == 64  # sha256 hex


def test_fingerprint_same_text_same_hash():
    text = "identical content for both calls"
    assert _content_fingerprint(text) == _content_fingerprint(text)


def test_fingerprint_different_texts_different_hash():
    assert _content_fingerprint("text one") != _content_fingerprint("text two")


def test_fingerprint_uses_length_in_key():
    # Length is part of the combined key, so same first 500 chars but different length = different hash
    short = "A" * 10
    long = "A" * 600
    assert _content_fingerprint(short) != _content_fingerprint(long)


def test_fingerprint_sample_stripped_but_length_from_original():
    # strip() applies to the sample, but len() uses the original text —
    # so same stripped content with different original lengths → different fingerprints
    fp1 = _content_fingerprint("  text  ")
    fp2 = _content_fingerprint("text  ")
    assert fp1 != fp2  # different original lengths


# ---------------------------------------------------------------------------
# _count_by_platform
# ---------------------------------------------------------------------------

def test_count_by_platform_basic():
    docs = [
        {"platform": "web"},
        {"platform": "web"},
        {"platform": "reddit"},
    ]
    counts = _count_by_platform(docs)
    assert counts["web"] == 2
    assert counts["reddit"] == 1


def test_count_by_platform_unknown():
    docs = [{"title": "no platform"}]
    counts = _count_by_platform(docs)
    assert counts["unknown"] == 1


def test_count_by_platform_empty():
    assert _count_by_platform([]) == {}


# ---------------------------------------------------------------------------
# _heuristic_plan
# ---------------------------------------------------------------------------

def test_heuristic_plan_structure():
    plan = _heuristic_plan("machine learning", "understand state of the art")
    assert "sub_questions" in plan
    assert "queries" in plan
    assert "source_priorities" in plan
    assert "entity_seeds" in plan


def test_heuristic_plan_sub_questions_not_empty():
    plan = _heuristic_plan("AI safety", "")
    assert len(plan["sub_questions"]) > 0


def test_heuristic_plan_queries_has_categories():
    plan = _heuristic_plan("quantum computing", "")
    queries = plan["queries"]
    assert "general" in queries
    assert "academic" in queries
    assert "technical" in queries
    assert "news" in queries


def test_heuristic_plan_topic_in_queries():
    plan = _heuristic_plan("blockchain", "")
    all_queries = " ".join(q for qs in plan["queries"].values() for q in qs)
    assert "blockchain" in all_queries.lower()


def test_heuristic_plan_source_priorities_are_ints():
    plan = _heuristic_plan("anything", "")
    for source, priority in plan["source_priorities"].items():
        assert isinstance(priority, int), f"{source} priority is not int"


# ---------------------------------------------------------------------------
# _flatten_plan_queries
# ---------------------------------------------------------------------------

def test_flatten_plan_queries_returns_list():
    plan = _heuristic_plan("AI", "")
    queries = _flatten_plan_queries(plan)
    assert isinstance(queries, list)


def test_flatten_plan_queries_respects_max_total():
    plan = _heuristic_plan("AI", "")
    queries = _flatten_plan_queries(plan, max_total=3)
    assert len(queries) <= 3


def test_flatten_plan_queries_deduplicates():
    plan = {
        "queries": {
            "general": ["AI", "ai", "AI"],
            "academic": ["AI research"],
        }
    }
    queries = _flatten_plan_queries(plan)
    assert queries.count("AI") == 1


def test_flatten_plan_queries_strips_whitespace():
    plan = {"queries": {"general": ["  AI  ", "blockchain"]}}
    queries = _flatten_plan_queries(plan)
    assert "AI" in queries


def test_flatten_plan_queries_order_follows_categories():
    plan = {
        "queries": {
            "general": ["general_q"],
            "academic": ["academic_q"],
        }
    }
    queries = _flatten_plan_queries(plan)
    assert queries.index("general_q") < queries.index("academic_q")


def test_flatten_plan_missing_queries_key():
    plan = {"sub_questions": ["Q1"]}
    queries = _flatten_plan_queries(plan)
    assert queries == []


# ---------------------------------------------------------------------------
# RunResult
# ---------------------------------------------------------------------------

def test_run_result_defaults():
    rr = RunResult(run_id="abc123")
    assert rr.run_id == "abc123"
    assert rr.raw_documents == []
    assert rr.clean_documents == []
    assert rr.export_paths == {}
    assert rr.report_path == ""
    assert rr.knowledge_graph == {}
    assert rr.gap_analysis == {}
    assert rr.images == []
    assert rr.query_plan == {}


def test_run_result_with_stats():
    rr = RunResult(run_id="xyz", stats={"collected": 10, "cleaned": 8})
    assert rr.stats["collected"] == 10


# ---------------------------------------------------------------------------
# InfoCollectorOrchestrator.run — validate_credentials path (no network)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_validate_credentials_no_file(tmp_path):
    from aria.config import load_config
    cfg = load_config(output_dir=tmp_path)

    orch = InfoCollectorOrchestrator(config=cfg)
    mission = {"collection": {"topic": "test topic", "intent": "research"}}
    result = await orch.run(
        mission,
        validate_credentials=True,
        credentials_path=str(tmp_path / "nonexistent.json"),
    )
    assert isinstance(result, RunResult)
    assert result.stats.get("validated") is True


@pytest.mark.asyncio
async def test_orchestrator_validate_credentials_with_file(tmp_path):
    from aria.config import load_config
    cfg = load_config(output_dir=tmp_path)

    creds_path = tmp_path / "credentials.json"
    creds_path.write_text(json.dumps({"OPENAI_API_KEY": "sk-test"}))

    orch = InfoCollectorOrchestrator(config=cfg)
    mission = {"collection": {"topic": "test", "intent": ""}}
    result = await orch.run(
        mission,
        validate_credentials=True,
        credentials_path=str(creds_path),
    )
    assert result.stats.get("validated") is True
