"""Tests for aria utility modules: formatter, robots, language, storage index."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from aria.engine.output.formatter import format_document_excerpt
from aria.utils.robots import is_allowed
from aria.engine.storage.index import IndexManager


# ---------------------------------------------------------------------------
# format_document_excerpt
# ---------------------------------------------------------------------------

def test_excerpt_short_text():
    doc = {"text": "Short text."}
    assert format_document_excerpt(doc) == "Short text."


def test_excerpt_long_text_truncated():
    doc = {"text": "A" * 300}
    result = format_document_excerpt(doc, max_length=100)
    assert result.endswith("...")
    assert len(result) <= 103  # 100 + "..."


def test_excerpt_uses_summary_first():
    doc = {"summary": "Summary text.", "text": "Raw text."}
    assert format_document_excerpt(doc) == "Summary text."


def test_excerpt_falls_back_to_raw_text():
    doc = {"raw_text": "Raw text fallback.", "text": ""}
    assert format_document_excerpt(doc) == "Raw text fallback."


def test_excerpt_falls_back_to_text():
    doc = {"text": "Plain text content."}
    assert format_document_excerpt(doc) == "Plain text content."


def test_excerpt_empty_doc():
    assert format_document_excerpt({}) == ""


def test_excerpt_none_values():
    doc = {"summary": None, "raw_text": None, "text": "fallback"}
    assert format_document_excerpt(doc) == "fallback"


def test_excerpt_exactly_max_length():
    doc = {"text": "X" * 240}
    result = format_document_excerpt(doc, max_length=240)
    assert result == "X" * 240
    assert not result.endswith("...")


# ---------------------------------------------------------------------------
# is_allowed (robots.txt)
# ---------------------------------------------------------------------------

def test_is_allowed_network_error_returns_true():
    with patch("aria.utils.robots.urllib.robotparser.RobotFileParser") as MockParser:
        instance = MockParser.return_value
        instance.read.side_effect = Exception("network error")
        result = is_allowed("*", "https://example.com/page")
    assert result is True


def test_is_allowed_respects_robots_txt():
    with patch("aria.utils.robots.urllib.robotparser.RobotFileParser") as MockParser:
        instance = MockParser.return_value
        instance.read.return_value = None
        instance.can_fetch.return_value = False
        result = is_allowed("mybot", "https://example.com/private")
    assert result is False


def test_is_allowed_permissive_robots():
    with patch("aria.utils.robots.urllib.robotparser.RobotFileParser") as MockParser:
        instance = MockParser.return_value
        instance.read.return_value = None
        instance.can_fetch.return_value = True
        result = is_allowed("mybot", "https://example.com/public")
    assert result is True


def test_is_allowed_constructs_robots_url():
    with patch("aria.utils.robots.urllib.robotparser.RobotFileParser") as MockParser:
        instance = MockParser.return_value
        instance.read.return_value = None
        instance.can_fetch.return_value = True
        is_allowed("bot", "https://mysite.org/some/page")
        instance.set_url.assert_called_once_with("https://mysite.org/robots.txt")


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------

def test_detect_language_empty_string():
    try:
        from aria.utils.language import detect_language
    except ImportError:
        pytest.skip("langdetect not installed")
    assert detect_language("") == "unknown"


def test_detect_language_whitespace_only():
    try:
        from aria.utils.language import detect_language
    except ImportError:
        pytest.skip("langdetect not installed")
    assert detect_language("   ") == "unknown"


def test_detect_language_english():
    try:
        from aria.utils.language import detect_language
        import langdetect  # noqa
    except ImportError:
        pytest.skip("langdetect not installed")
    result = detect_language("The quick brown fox jumps over the lazy dog.")
    assert result == "en"


def test_detect_language_exception_returns_unknown():
    try:
        from aria.utils.language import detect_language
    except ImportError:
        pytest.skip("langdetect not installed")
    with patch("aria.utils.language.detect", side_effect=Exception("error")):
        assert detect_language("some text") == "unknown"


# ---------------------------------------------------------------------------
# IndexManager
# ---------------------------------------------------------------------------

def test_index_manager_load_calls_raw_store_load(tmp_path):
    from aria.engine.storage.raw_store import RawStore
    raw_store = RawStore(tmp_path / "raw")
    docs = [{"url": "https://a.com", "title": "A", "text": "body"}]
    raw_store.save(docs)

    manager = IndexManager(raw_store)
    loaded = manager.load()
    assert len(loaded) == 1
    assert loaded[0]["url"] == "https://a.com"


def test_index_manager_load_empty_store(tmp_path):
    from aria.engine.storage.raw_store import RawStore
    raw_store = RawStore(tmp_path / "raw")
    manager = IndexManager(raw_store)
    assert manager.load() == []
