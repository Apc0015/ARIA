"""Tests for aria.config — Config model and load_config."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from aria.config import Config, load_config


def test_config_defaults():
    cfg = Config()
    assert cfg.api_port == 8765
    assert cfg.api_host == "0.0.0.0"
    assert cfg.shared_memory_backend == "dict"
    assert cfg.kb_enabled is True
    assert cfg.gap_detection_enabled is True
    assert cfg.knowledge_graph_enabled is True
    assert cfg.semantic_dedup_enabled is False  # opt-in; default False
    assert cfg.smart_query_planning is True
    assert cfg.image_extraction_enabled is True
    assert cfg.streaming_clean is False


def test_config_custom_paths(tmp_path):
    cfg = Config(
        raw_data_dir=tmp_path / "raw",
        clean_data_dir=tmp_path / "clean",
        export_dir=tmp_path / "exports",
        runs_dir=tmp_path / "runs",
    )
    assert cfg.raw_data_dir == tmp_path / "raw"
    assert cfg.runs_dir == tmp_path / "runs"


def test_ensure_directories_creates_paths(tmp_path):
    cfg = Config(
        raw_data_dir=tmp_path / "raw",
        clean_data_dir=tmp_path / "clean",
        export_dir=tmp_path / "exports",
        runs_dir=tmp_path / "runs",
        session_cache_dir=tmp_path / "sessions",
    )
    cfg.ensure_directories()
    assert (tmp_path / "raw").exists()
    assert (tmp_path / "clean").exists()
    assert (tmp_path / "exports").exists()
    assert (tmp_path / "runs").exists()
    assert (tmp_path / "sessions").exists()


def test_ensure_directories_idempotent(tmp_path):
    cfg = Config(
        raw_data_dir=tmp_path / "raw",
        clean_data_dir=tmp_path / "clean",
        export_dir=tmp_path / "exports",
        runs_dir=tmp_path / "runs",
        session_cache_dir=tmp_path / "sessions",
    )
    cfg.ensure_directories()
    cfg.ensure_directories()  # must not raise


def test_load_config_returns_config_instance(tmp_path):
    cfg = load_config(output_dir=tmp_path)
    assert isinstance(cfg, Config)


def test_load_config_uses_output_dir(tmp_path):
    cfg = load_config(output_dir=tmp_path)
    assert cfg.raw_data_dir == tmp_path / "raw"
    assert cfg.clean_data_dir == tmp_path / "clean"
    assert cfg.export_dir == tmp_path / "exports"
    assert cfg.runs_dir == tmp_path / "runs"


def test_load_config_creates_directories(tmp_path):
    load_config(output_dir=tmp_path)
    assert (tmp_path / "raw").exists()
    assert (tmp_path / "clean").exists()


def test_load_config_reads_env_vars(tmp_path, monkeypatch):
    monkeypatch.setenv("ARIA_API_PORT", "9999")
    monkeypatch.setenv("ARIA_API_HOST", "127.0.0.1")
    monkeypatch.setenv("SHARED_MEMORY_BACKEND", "redis")
    monkeypatch.setenv("ARIA_KB_ENABLED", "false")
    monkeypatch.setenv("ARIA_GAP_DETECTION", "false")
    monkeypatch.setenv("ARIA_STREAMING_CLEAN", "true")

    cfg = load_config(output_dir=tmp_path)
    assert cfg.api_port == 9999
    assert cfg.api_host == "127.0.0.1"
    assert cfg.shared_memory_backend == "redis"
    assert cfg.kb_enabled is False
    assert cfg.gap_detection_enabled is False
    assert cfg.streaming_clean is True


def test_load_config_no_output_dir_uses_defaults():
    cfg = load_config()
    assert isinstance(cfg, Config)
    assert cfg.api_port == int(os.getenv("ARIA_API_PORT", "8765"))


def test_config_has_no_env_mutating_llm_override(tmp_path):
    # with_llm_override wrote user LLM selections into process-wide os.environ,
    # leaking one caller's provider/key to every other caller (and to other
    # tests). Removed — brain selection flows through CredentialScope and
    # resolve_cleaning_llm(overrides=...) instead.
    cfg = load_config(output_dir=tmp_path)
    assert not hasattr(cfg, "with_llm_override")


def test_load_settings_alias():
    from aria.config import load_settings
    assert load_settings is load_config
