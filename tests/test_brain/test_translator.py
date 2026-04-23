"""Tests for the translation module."""

from __future__ import annotations

import pytest
from unittest.mock import patch

from aria.brain.translator import translate_text, is_translation_available


def test_translate_empty_text():
    assert translate_text("") == ""
    assert translate_text("  ") == "  "


def test_translate_same_language():
    """No translation needed when source == target."""
    result = translate_text("Hello world", source_language="en", target_language="en")
    assert result == "Hello world"


def test_translate_english_variants_skip():
    """English variants (en-us, en-gb) skipped when target is en."""
    text = "This is English text."
    for code in ("en", "en-us", "en-gb", "en-au", "en-ca"):
        result = translate_text(text, source_language=code, target_language="en")
        assert result == text


def test_translate_returns_original_when_no_backend():
    """Returns original text with warning when deep_translator is unavailable."""
    with patch.dict("sys.modules", {"deep_translator": None}):
        # Even if deep_translator not installed, no exception raised
        result = translate_text("Bonjour le monde", source_language="fr", target_language="en")
        assert isinstance(result, str)
        assert len(result) > 0


def test_translate_with_deep_translator_success():
    """Uses deep_translator when available."""
    class MockGoogleTranslator:
        def __init__(self, source, target):
            pass
        def translate(self, text):
            return "Hello world"

    mock_module = type("deep_translator", (), {
        "GoogleTranslator": MockGoogleTranslator,
        "exceptions": type("exceptions", (), {})(),
    })()

    with patch.dict("sys.modules", {"deep_translator": mock_module}):
        result = translate_text("Bonjour le monde", source_language="fr", target_language="en")
        assert result == "Hello world"


def test_is_translation_available():
    """is_translation_available returns bool."""
    result = is_translation_available()
    assert isinstance(result, bool)
