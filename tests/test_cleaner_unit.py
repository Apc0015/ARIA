"""Unit tests for LLMCleaner internals — no LLM calls required."""

from __future__ import annotations

import json
import pytest

from aria.engine.cleaner.llm_cleaner import (
    LLMCleaner,
    _build_cleaning_prompt,
    _default_for_schema_type,
    _fallback_clean,
    _merge_doc_with_extraction,
    _parse_llm_json,
)
from aria.engine.ensemble.providers import resolve_cleaning_llm as _resolve_llm


# ---------------------------------------------------------------------------
# _default_for_schema_type
# ---------------------------------------------------------------------------

def test_default_bool():
    assert _default_for_schema_type("bool") is False


def test_default_float():
    assert _default_for_schema_type("float") == 0.0


def test_default_int():
    assert _default_for_schema_type("int") == 0


def test_default_list():
    assert _default_for_schema_type("list") == []


def test_default_dict():
    assert _default_for_schema_type("dict") == {}


def test_default_unknown_str():
    assert _default_for_schema_type("string") is None


def test_default_dict_type():
    assert _default_for_schema_type({"nested": "type"}) == {}


def test_default_other():
    assert _default_for_schema_type(42) is None


# ---------------------------------------------------------------------------
# _parse_llm_json
# ---------------------------------------------------------------------------

def test_parse_valid_json():
    text = '{"key": "value", "num": 42}'
    result = _parse_llm_json(text)
    assert result == {"key": "value", "num": 42}


def test_parse_markdown_wrapped_json():
    text = '```json\n{"key": "value"}\n```'
    result = _parse_llm_json(text)
    assert result == {"key": "value"}


def test_parse_markdown_without_lang():
    text = '```\n{"key": "value"}\n```'
    result = _parse_llm_json(text)
    assert result == {"key": "value"}


def test_parse_json_embedded_in_text():
    text = 'Here is the result: {"key": "value"} end.'
    result = _parse_llm_json(text)
    assert result == {"key": "value"}


def test_parse_empty_returns_none():
    assert _parse_llm_json("") is None
    assert _parse_llm_json(None) is None


def test_parse_invalid_json_returns_none():
    assert _parse_llm_json("not json at all") is None


def test_parse_whitespace_stripped():
    result = _parse_llm_json('  {"a": 1}  ')
    assert result == {"a": 1}


# ---------------------------------------------------------------------------
# _fallback_clean
# ---------------------------------------------------------------------------

def test_fallback_sets_content_type():
    doc = {"url": "https://example.com", "text": "raw text", "title": "T"}
    result = _fallback_clean(doc, {})
    assert result["content_type"] == "unknown"
    assert result["relevance_score"] == 0.5
    assert result["is_relevant"] is True
    assert result["cleaned"] is False


def test_fallback_summary_is_text_excerpt():
    doc = {"text": "A" * 400}
    result = _fallback_clean(doc, {})
    assert result["summary"] == "A" * 300


def test_fallback_populates_schema_defaults():
    doc = {"text": "content"}
    schema = {"my_bool": "bool", "my_float": "float", "my_list": "list"}
    result = _fallback_clean(doc, schema)
    assert result["my_bool"] is False
    assert result["my_float"] == 0.0
    assert result["my_list"] == []


def test_fallback_preserves_existing_schema_keys():
    doc = {"text": "content", "my_bool": True}
    result = _fallback_clean(doc, {"my_bool": "bool"})
    assert result["my_bool"] is True


# ---------------------------------------------------------------------------
# _merge_doc_with_extraction
# ---------------------------------------------------------------------------

def test_merge_sets_standard_fields():
    doc = {"url": "https://x.com", "text": "content"}
    extracted = {
        "content_type": "news_article",
        "relevance_score": 0.8,
        "is_relevant": True,
        "summary": "A summary here.",
    }
    result = _merge_doc_with_extraction(doc, extracted, {})
    assert result["content_type"] == "news_article"
    assert result["relevance_score"] == 0.8
    assert result["is_relevant"] is True
    assert result["summary"] == "A summary here."
    assert result["cleaned"] is True


def test_merge_fills_schema_fields():
    doc = {"url": "https://x.com", "text": ""}
    extracted = {"relevance_score": 0.6, "is_relevant": True, "summary": "", "content_type": "unknown", "my_key": "my_val"}
    schema = {"my_key": "string", "missing_key": "bool"}
    result = _merge_doc_with_extraction(doc, extracted, schema)
    assert result["my_key"] == "my_val"
    assert result["missing_key"] is False


def test_merge_falls_back_relevance_from_score():
    doc = {}
    extracted = {"relevance_score": 0.3, "summary": "", "content_type": "unknown"}
    result = _merge_doc_with_extraction(doc, extracted, {})
    assert result["is_relevant"] is False


def test_merge_sets_title_from_extraction_when_missing():
    doc = {"title": ""}
    extracted = {"content_type": "unknown", "relevance_score": 0.5, "is_relevant": True, "summary": "", "title": "Extracted Title"}
    result = _merge_doc_with_extraction(doc, extracted, {})
    assert result["title"] == "Extracted Title"


def test_merge_preserves_original_doc_title():
    doc = {"title": "Original"}
    extracted = {"content_type": "unknown", "relevance_score": 0.5, "is_relevant": True, "summary": "", "title": "Other"}
    result = _merge_doc_with_extraction(doc, extracted, {})
    assert result["title"] == "Original"


# ---------------------------------------------------------------------------
# _build_cleaning_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_contains_doc_fields():
    doc = {
        "title": "Test Article",
        "url": "https://test.com",
        "text": "Article content",
        "source_type": "web",
        "platform": "web_search",
    }
    schema = {"is_relevant": "bool", "summary": "string"}
    prompt = _build_cleaning_prompt(doc, "Extract key info", schema)
    assert "Test Article" in prompt
    assert "https://test.com" in prompt
    assert "Article content" in prompt
    assert "Extract key info" in prompt
    assert "is_relevant" in prompt


def test_build_prompt_truncates_long_text():
    doc = {"title": "", "url": "", "text": "X" * 20000, "source_type": "", "platform": ""}
    prompt = _build_cleaning_prompt(doc, "instructions", {})
    assert "..." in prompt
    assert "X" * 20000 not in prompt


def test_build_prompt_includes_content_types():
    doc = {"title": "", "url": "", "text": "", "source_type": "", "platform": ""}
    prompt = _build_cleaning_prompt(doc, "", {})
    assert "academic_paper" in prompt
    assert "news_article" in prompt


# ---------------------------------------------------------------------------
# LLMCleaner.clean_batch (no API key — uses fallback)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clean_batch_fallback_no_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:1")  # unreachable

    from aria.config import load_config
    cfg = load_config(output_dir=tmp_path)

    docs = [
        {"url": "https://a.com", "text": "First document content", "title": "A"},
        {"url": "https://b.com", "text": "Second document content", "title": "B"},
    ]

    cleaner = LLMCleaner(config=cfg)
    result = await cleaner.clean_batch(docs, "Extract info", {"my_field": "string"})
    assert len(result) == 2
    for r in result:
        assert "content_type" in r
        assert "relevance_score" in r
        assert "is_relevant" in r
        assert "my_field" in r


@pytest.mark.asyncio
async def test_clean_document_fallback_returns_merged_doc(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from aria.config import load_config
    cfg = load_config(output_dir=tmp_path)
    cleaner = LLMCleaner(config=cfg)

    doc = {"url": "https://test.com", "title": "T", "text": "body"}
    result = await cleaner.clean_document(doc, "instructions", {"score": "float"})
    assert result["url"] == "https://test.com"
    assert "content_type" in result


# ---------------------------------------------------------------------------
# _resolve_llm
# ---------------------------------------------------------------------------

def test_resolve_llm_anthropic_key(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key-123")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider, model, base_url, api_key = _resolve_llm(None)
    assert provider == "anthropic"
    assert api_key == "ant-key-123"
    assert base_url is None


def test_resolve_llm_openrouter_key(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key-456")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider, model, base_url, api_key = _resolve_llm(None)
    assert provider == "openrouter"
    assert "openrouter.ai" in base_url


def test_resolve_llm_openai_key(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-789")
    provider, model, base_url, api_key = _resolve_llm(None)
    assert provider == "openai"


def test_resolve_llm_without_configuration_returns_empty(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    provider, model, base_url, api_key = _resolve_llm(None)
    assert (provider, model, base_url, api_key) == ("", "", None, "")
