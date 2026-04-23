"""Tests for RawStore and CleanStore."""

from __future__ import annotations

import json

import pytest

from aria.engine.storage.clean_store import CleanStore
from aria.engine.storage.raw_store import RawStore


SAMPLE_DOCS = [
    {"url": "https://a.com", "title": "A", "text": "Body A"},
    {"url": "https://b.com", "title": "B", "text": "Body B"},
]


# ---------------------------------------------------------------------------
# RawStore
# ---------------------------------------------------------------------------

def test_raw_store_save_creates_file(tmp_path):
    store = RawStore(tmp_path / "raw")
    path = store.save(SAMPLE_DOCS)
    assert path.exists()
    assert path.name == "raw_documents.jsonl"


def test_raw_store_load_returns_docs(tmp_path):
    store = RawStore(tmp_path / "raw")
    store.save(SAMPLE_DOCS)
    loaded = store.load()
    assert len(loaded) == 2
    assert loaded[0]["url"] == "https://a.com"
    assert loaded[1]["url"] == "https://b.com"


def test_raw_store_load_empty_when_no_file(tmp_path):
    store = RawStore(tmp_path / "raw")
    assert store.load() == []


def test_raw_store_count(tmp_path):
    store = RawStore(tmp_path / "raw")
    store.save(SAMPLE_DOCS)
    assert store.count() == 2


def test_raw_store_count_empty(tmp_path):
    store = RawStore(tmp_path / "raw")
    assert store.count() == 0


def test_raw_store_save_overwrites(tmp_path):
    store = RawStore(tmp_path / "raw")
    store.save(SAMPLE_DOCS)
    store.save([SAMPLE_DOCS[0]])
    assert store.count() == 1


def test_raw_store_handles_special_chars(tmp_path):
    doc = {"url": "https://example.com", "title": "日本語", "text": "Unicode: café"}
    store = RawStore(tmp_path / "raw")
    store.save([doc])
    loaded = store.load()
    assert loaded[0]["title"] == "日本語"
    assert "café" in loaded[0]["text"]


def test_raw_store_creates_directory(tmp_path):
    store = RawStore(tmp_path / "deep" / "nested" / "raw")
    store.save(SAMPLE_DOCS)
    assert (tmp_path / "deep" / "nested" / "raw" / "raw_documents.jsonl").exists()


def test_raw_store_load_skips_invalid_lines(tmp_path):
    store = RawStore(tmp_path / "raw")
    path = store.save(SAMPLE_DOCS)
    # Corrupt one line
    content = path.read_text()
    path.write_text(content + "INVALID JSON LINE\n")
    loaded = store.load()
    assert len(loaded) == 2


def test_raw_store_save_empty_list(tmp_path):
    store = RawStore(tmp_path / "raw")
    store.save([])
    assert store.count() == 0


# ---------------------------------------------------------------------------
# CleanStore
# ---------------------------------------------------------------------------

def test_clean_store_save_creates_file(tmp_path):
    store = CleanStore(tmp_path / "clean")
    path = store.save(SAMPLE_DOCS)
    assert path.exists()
    assert path.name == "clean_documents.jsonl"


def test_clean_store_load_returns_docs(tmp_path):
    store = CleanStore(tmp_path / "clean")
    store.save(SAMPLE_DOCS)
    loaded = store.load()
    assert len(loaded) == 2


def test_clean_store_load_empty_when_no_file(tmp_path):
    store = CleanStore(tmp_path / "clean")
    assert store.load() == []


def test_clean_store_count(tmp_path):
    store = CleanStore(tmp_path / "clean")
    store.save(SAMPLE_DOCS)
    assert store.count() == 2


def test_clean_store_saves_complex_nested_fields(tmp_path):
    doc = {
        "url": "https://x.com",
        "title": "T",
        "relevance_score": 0.95,
        "entities": ["Alice", "Bob"],
        "metadata": {"source": "test"},
        "is_relevant": True,
    }
    store = CleanStore(tmp_path / "clean")
    store.save([doc])
    loaded = store.load()
    assert loaded[0]["relevance_score"] == 0.95
    assert loaded[0]["entities"] == ["Alice", "Bob"]
    assert loaded[0]["is_relevant"] is True
