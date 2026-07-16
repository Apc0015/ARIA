"""Run topics must be human-readable — never the run-id hash or YAML junk.

Covers the dashboard fix: the runs list surfaced raw hashes as titles for
historical runs, and malformed pastes leaked YAML fragments as topics.
"""

from __future__ import annotations

from aria.api.routes.runs import _clean_topic
from aria.api.run_manager import RunManager


# ---------------------------------------------------------------------------
# _clean_topic
# ---------------------------------------------------------------------------

def test_real_topic_passes_through():
    assert (
        _clean_topic("AI policy adoption in US county governments", "abc123")
        == "AI policy adoption in US county governments"
    )


def test_run_id_hash_rejected():
    assert _clean_topic("279dcb341f4b", "279dcb341f4b") is None


def test_yaml_fragments_rejected():
    assert _clean_topic("mission:", "abc") is None
    assert _clean_topic("{", "abc") is None
    assert _clean_topic("collection:", "abc") is None


def test_placeholder_and_empty_rejected():
    assert _clean_topic("", "abc") is None
    assert _clean_topic(None, "abc") is None
    assert _clean_topic("research", "abc") is None
    assert _clean_topic("Hydrated from persisted run files", "abc") is None


def test_topic_without_a_word_rejected():
    assert _clean_topic("12 34", "abc") is None
    assert _clean_topic("---", "abc") is None


# ---------------------------------------------------------------------------
# RunManager._recover_topic — read the digest the engine wrote
# ---------------------------------------------------------------------------

def test_recover_topic_from_research_digest(tmp_path):
    run_dir = tmp_path / "deadbeef"
    (run_dir / "exports").mkdir(parents=True)
    (run_dir / "exports" / "research_digest.md").write_text(
        "# Research Digest: quantum error correction\n\n*Generated: ...*\n",
        encoding="utf-8",
    )
    assert RunManager._recover_topic(run_dir, []) == "quantum error correction"


def test_recover_topic_from_mission_yaml(tmp_path):
    run_dir = tmp_path / "cafe1234"
    run_dir.mkdir()
    (run_dir / "mission.yaml").write_text(
        "collection:\n  topic: renewable grid storage\n", encoding="utf-8"
    )
    assert RunManager._recover_topic(run_dir, []) == "renewable grid storage"


def test_recover_topic_returns_empty_when_nothing_known(tmp_path):
    run_dir = tmp_path / "0f0f0f0f"
    run_dir.mkdir()
    assert RunManager._recover_topic(run_dir, []) == ""
