"""Tests for LLM provider string validation."""

from __future__ import annotations

import pytest

from aria.engine.ensemble.agent import _resolve_api_key, _resolve_base_url, _VALID_PROVIDERS


def test_valid_providers_set():
    assert "openrouter" in _VALID_PROVIDERS
    assert "openai" in _VALID_PROVIDERS
    assert "anthropic" in _VALID_PROVIDERS
    assert "ollama" in _VALID_PROVIDERS


def test_resolve_api_key_valid_providers(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")

    assert _resolve_api_key("openrouter") == "or-key"
    assert _resolve_api_key("openai") == "oai-key"
    assert _resolve_api_key("anthropic") == "ant-key"
    assert _resolve_api_key("ollama") == "ollama"


def test_resolve_api_key_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        _resolve_api_key("mistral")

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        _resolve_api_key("together")

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        _resolve_api_key("google")


def test_resolve_api_key_strips_whitespace():
    """Whitespace is normalised — stripped input resolves to valid provider."""
    # "openai " strips to "openai" which is valid → no raise
    import os
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("OPENAI_API_KEY", "oai-key")
        assert _resolve_api_key("openai ") == "oai-key"


def test_resolve_base_url_valid_providers(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    assert _resolve_base_url("openrouter") == "https://openrouter.ai/api/v1"
    assert _resolve_base_url("openai") == "https://api.openai.com/v1"
    assert _resolve_base_url("anthropic") is None  # SDK manages endpoint
    assert "11434" in _resolve_base_url("ollama")
