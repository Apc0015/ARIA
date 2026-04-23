"""Tests for Exporter — all export formats."""

from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

import pytest

from aria.engine.output.exporter import Exporter, _flatten_value


SAMPLE_RAW = [
    {
        "url": "https://site1.com/article",
        "title": "Article One",
        "text": "Body text of article one.",
        "platform": "web_search",
        "source_type": "news_article",
        "language": "en",
        "word_count": 5,
        "collected_at": "2024-01-01T00:00:00Z",
        "metadata": {"author": "Alice"},
    }
]

SAMPLE_CLEAN = [
    {
        "url": "https://site1.com/article",
        "title": "Article One",
        "text": "Body text of article one.",
        "summary": "A good summary.",
        "platform": "web_search",
        "source_type": "news_article",
        "relevance_score": 0.9,
        "is_relevant": True,
        "content_type": "news_article",
        "language": "en",
        "word_count": 5,
        "collected_at": "2024-01-01T00:00:00Z",
        "key_topics": ["topic1", "topic2"],
    }
]


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def test_export_json_creates_file(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_json(SAMPLE_CLEAN)
    assert path.exists()


def test_export_json_content(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_json(SAMPLE_CLEAN)
    data = json.loads(path.read_text())
    assert isinstance(data, list)
    assert data[0]["title"] == "Article One"


def test_export_json_empty_list(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_json([])
    data = json.loads(path.read_text())
    assert data == []


def test_export_raw_json(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_raw_json(SAMPLE_RAW)
    data = json.loads(path.read_text())
    assert data[0]["platform"] == "web_search"


def test_export_clean_json(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_clean_json(SAMPLE_CLEAN)
    data = json.loads(path.read_text())
    assert data[0]["relevance_score"] == 0.9


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def test_export_raw_csv_creates_file(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_raw_csv(SAMPLE_RAW)
    assert path.exists()
    assert path.suffix == ".csv"


def test_export_raw_csv_has_header(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_raw_csv(SAMPLE_RAW)
    with path.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["url"] == "https://site1.com/article"


def test_export_raw_csv_empty(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_raw_csv([])
    content = path.read_text()
    assert "url" in content


def test_export_clean_csv_creates_file(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_clean_csv(SAMPLE_CLEAN)
    assert path.exists()


def test_export_clean_csv_has_relevance_score(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_clean_csv(SAMPLE_CLEAN)
    with path.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert rows[0]["relevance_score"] == "0.9"


def test_export_clean_csv_empty(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_clean_csv([])
    assert path.exists()


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------

def test_export_markdown_creates_file(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_markdown(SAMPLE_CLEAN, topic="AI Research")
    assert path.exists()
    assert path.suffix == ".md"


def test_export_markdown_contains_topic(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_markdown(SAMPLE_CLEAN, topic="AI Research")
    content = path.read_text()
    assert "AI Research" in content


def test_export_markdown_contains_title(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_markdown(SAMPLE_CLEAN, topic="Test")
    content = path.read_text()
    assert "Article One" in content


def test_export_markdown_contains_summary(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_markdown(SAMPLE_CLEAN, topic="Test")
    content = path.read_text()
    assert "A good summary." in content


def test_export_markdown_contains_key_topics(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_markdown(SAMPLE_CLEAN, topic="Test")
    content = path.read_text()
    assert "topic1" in content


def test_export_markdown_empty_docs(tmp_path):
    exp = Exporter(tmp_path)
    path = exp.export_markdown([], topic="Empty")
    content = path.read_text()
    assert "Empty" in content


# ---------------------------------------------------------------------------
# ZIP export
# ---------------------------------------------------------------------------

def test_export_zip_creates_file(tmp_path):
    exp = Exporter(tmp_path)
    paths = {"json": str(exp.export_clean_json(SAMPLE_CLEAN))}
    zip_path = exp.export_zip(paths)
    assert zip_path.exists()
    assert zip_path.suffix == ".zip"


def test_export_zip_contains_files(tmp_path):
    exp = Exporter(tmp_path)
    json_path = exp.export_clean_json(SAMPLE_CLEAN)
    zip_path = exp.export_zip({"json": str(json_path)})
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert json_path.name in names


def test_export_zip_skips_missing_paths(tmp_path):
    exp = Exporter(tmp_path)
    zip_path = exp.export_zip({"missing": str(tmp_path / "nonexistent.json")})
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.namelist() == []


# ---------------------------------------------------------------------------
# export_all
# ---------------------------------------------------------------------------

def test_export_all_json(tmp_path):
    exp = Exporter(tmp_path)
    result = exp.export_all(SAMPLE_RAW, SAMPLE_CLEAN, formats=["json"], topic="Test")
    assert "raw_json" in result
    assert "clean_json" in result
    assert Path(result["raw_json"]).exists()
    assert Path(result["clean_json"]).exists()


def test_export_all_csv(tmp_path):
    exp = Exporter(tmp_path)
    result = exp.export_all(SAMPLE_RAW, SAMPLE_CLEAN, formats=["csv"], topic="Test")
    assert "raw_csv" in result
    assert "clean_csv" in result


def test_export_all_markdown(tmp_path):
    exp = Exporter(tmp_path)
    result = exp.export_all(SAMPLE_RAW, SAMPLE_CLEAN, formats=["markdown"], topic="AI")
    assert "markdown" in result
    assert Path(result["markdown"]).exists()


def test_export_all_zip_bundles(tmp_path):
    exp = Exporter(tmp_path)
    result = exp.export_all(SAMPLE_RAW, SAMPLE_CLEAN, formats=["json", "csv", "zip"])
    assert "zip" in result
    assert Path(result["zip"]).exists()


def test_export_all_unknown_format_ignored(tmp_path):
    exp = Exporter(tmp_path)
    result = exp.export_all(SAMPLE_RAW, SAMPLE_CLEAN, formats=["unknown_format"])
    assert result == {}


# ---------------------------------------------------------------------------
# _flatten_value helper
# ---------------------------------------------------------------------------

def test_flatten_value_none():
    assert _flatten_value(None) == ""


def test_flatten_value_string():
    assert _flatten_value("hello") == "hello"


def test_flatten_value_list():
    result = _flatten_value(["a", "b"])
    assert result == '["a", "b"]'


def test_flatten_value_dict():
    result = _flatten_value({"k": "v"})
    assert result == '{"k": "v"}'


def test_flatten_value_int():
    assert _flatten_value(42) == "42"


def test_flatten_value_float():
    assert _flatten_value(0.5) == "0.5"
