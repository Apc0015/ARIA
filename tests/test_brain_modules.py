"""Tests for aria.brain modules: QueryExpander, QualityValidator, translator."""

from __future__ import annotations

import pytest

from aria.brain.expander import QueryExpander
from aria.orchestrator.quality import QualityValidator
from aria.orchestrator.strategy import QueryStrategy


# ---------------------------------------------------------------------------
# QueryExpander
# ---------------------------------------------------------------------------

def test_query_expander_instantiates(aria_settings, aria_logger):
    expander = QueryExpander(aria_settings, aria_logger)
    assert expander is not None


def test_query_expander_expand_returns_list(aria_settings, aria_logger):
    expander = QueryExpander(aria_settings, aria_logger)
    result = expander.expand("machine learning")
    assert isinstance(result, list)
    assert len(result) > 0


def test_query_expander_expand_topic_in_results(aria_settings, aria_logger):
    expander = QueryExpander(aria_settings, aria_logger)
    result = expander.expand("quantum computing")
    all_text = " ".join(result).lower()
    assert "quantum computing" in all_text


def test_query_expander_expand_diverse_queries(aria_settings, aria_logger):
    expander = QueryExpander(aria_settings, aria_logger)
    result = expander.expand("climate change")
    assert len(result) >= 4


def test_query_expander_no_duplicates(aria_settings, aria_logger):
    expander = QueryExpander(aria_settings, aria_logger)
    result = expander.expand("AI safety")
    lowered = [q.lower() for q in result]
    assert len(lowered) == len(set(lowered))


# ---------------------------------------------------------------------------
# QueryStrategy (mirrors QueryExpander via different module)
# ---------------------------------------------------------------------------

def test_query_strategy_instantiates(aria_settings, aria_logger):
    strategy = QueryStrategy(aria_settings, aria_logger)
    assert strategy is not None


def test_query_strategy_expand_returns_list(aria_settings, aria_logger):
    strategy = QueryStrategy(aria_settings, aria_logger)
    result = strategy.expand("renewable energy")
    assert isinstance(result, list)
    assert len(result) > 0


def test_query_strategy_expand_contains_topic(aria_settings, aria_logger):
    strategy = QueryStrategy(aria_settings, aria_logger)
    result = strategy.expand("blockchain")
    combined = " ".join(result).lower()
    assert "blockchain" in combined


# ---------------------------------------------------------------------------
# QualityValidator
# ---------------------------------------------------------------------------

def test_quality_validator_valid_document():
    validator = QualityValidator()
    doc = {"title": "T", "url": "https://x.com", "summary": "S"}
    result = validator.validate(doc, ["title", "url", "summary"])
    assert result["valid"] is True
    assert result["missing_keys"] == []


def test_quality_validator_missing_keys():
    validator = QualityValidator()
    doc = {"title": "T"}
    result = validator.validate(doc, ["title", "url", "summary"])
    assert result["valid"] is False
    assert "url" in result["missing_keys"]
    assert "summary" in result["missing_keys"]


def test_quality_validator_empty_required_keys():
    validator = QualityValidator()
    result = validator.validate({"anything": "x"}, [])
    assert result["valid"] is True
    assert result["missing_keys"] == []


def test_quality_validator_all_missing():
    validator = QualityValidator()
    result = validator.validate({}, ["a", "b", "c"])
    assert result["valid"] is False
    assert set(result["missing_keys"]) == {"a", "b", "c"}


def test_quality_validator_returns_dict():
    validator = QualityValidator()
    result = validator.validate({"k": "v"}, ["k"])
    assert isinstance(result, dict)
    assert "valid" in result
    assert "missing_keys" in result


# ---------------------------------------------------------------------------
# Translator
# ---------------------------------------------------------------------------

def test_translate_text_same_language_returns_original():
    from aria.brain.translator import translate_text
    text = "Hello world in English."
    result = translate_text(text, source_language="en", target_language="en")
    assert result == text


def test_translate_text_english_variant_skipped():
    from aria.brain.translator import translate_text
    text = "This is English content."
    result = translate_text(text, source_language="en-us", target_language="en")
    assert result == text


def test_translate_text_empty_returns_empty():
    from aria.brain.translator import translate_text
    assert translate_text("") == ""
    assert translate_text("   ") == "   "


def test_translate_text_no_backend_returns_original():
    from aria.brain.translator import translate_text
    from unittest.mock import patch
    text = "Hola mundo"
    with patch("aria.brain.translator._try_deep_translator", return_value=None):
        result = translate_text(text, source_language="es", target_language="en")
    assert result == text


def test_translate_text_truncates_long_input():
    from aria.brain.translator import translate_text
    from unittest.mock import patch
    long_text = "X" * 10000
    captured = []

    def fake_translate(text, src, tgt):
        captured.append(text)
        return "translated"

    with patch("aria.brain.translator._try_deep_translator", side_effect=fake_translate):
        translate_text(long_text, source_language="fr", target_language="en")

    assert len(captured[0]) == 8000


def test_is_translation_available_returns_bool():
    from aria.brain.translator import is_translation_available
    result = is_translation_available()
    assert isinstance(result, bool)


def test_try_deep_translator_handles_import_error():
    from aria.brain.translator import _try_deep_translator
    from unittest.mock import patch
    with patch.dict("sys.modules", {"deep_translator": None}):
        result = _try_deep_translator("text", "es", "en")
    assert result is None
