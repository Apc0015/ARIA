"""LLM provider discovery and catalog building."""

from __future__ import annotations

import os
from typing import Any, Optional


def build_provider_catalog(config: Any) -> list[dict]:
    """Return a list of available LLM providers with API keys set.

    Each entry has: provider, model_id, enabled, base_url, notes.

    Args:
        config: ARIA Config instance (used for Ollama base URL etc.)

    Returns:
        List of provider dicts for available providers.
    """
    catalog = []

    # OpenRouter
    or_key = os.getenv("OPENROUTER_API_KEY")
    if or_key:
        catalog.extend([
            {
                "provider": "openrouter",
                "model_id": "openai/gpt-4o-mini",
                "enabled": True,
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": or_key,
                "notes": "OpenRouter / GPT-4o Mini",
            },
            {
                "provider": "openrouter",
                "model_id": "anthropic/claude-3-haiku",
                "enabled": True,
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": or_key,
                "notes": "OpenRouter / Claude 3 Haiku",
            },
        ])

    # OpenAI direct
    oai_key = os.getenv("OPENAI_API_KEY")
    if oai_key and not or_key:
        catalog.extend([
            {
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "enabled": True,
                "base_url": "https://api.openai.com/v1",
                "api_key": oai_key,
                "notes": "OpenAI GPT-4o Mini",
            },
        ])

    # Anthropic direct
    ant_key = os.getenv("ANTHROPIC_API_KEY")
    if ant_key:
        catalog.extend([
            {
                "provider": "anthropic",
                "model_id": "claude-3-haiku-20240307",
                "enabled": True,
                "base_url": None,
                "api_key": ant_key,
                "notes": "Anthropic Claude 3 Haiku",
            },
        ])

    # Ollama (local, always try)
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    catalog.extend([
        {
            "provider": "ollama",
            "model_id": "llama3.1:8b",
            "enabled": True,
            "base_url": ollama_base,
            "api_key": "ollama",
            "notes": "Local Ollama / Llama 3.1 8B",
        },
        {
            "provider": "ollama",
            "model_id": "mistral",
            "enabled": True,
            "base_url": ollama_base,
            "api_key": "ollama",
            "notes": "Local Ollama / Mistral 7B",
        },
    ])

    return catalog


def default_llm_source_models(config: Any) -> list[dict]:
    """Return default models to use for LLM-as-source collection.

    Prefers cloud providers if keys are available, falls back to Ollama.

    Args:
        config: ARIA Config instance.

    Returns:
        List of model config dicts.
    """
    catalog = build_provider_catalog(config)
    # Pick first 2 enabled models from different providers for diversity
    selected = []
    seen_providers = set()
    for entry in catalog:
        prov = entry["provider"]
        if prov not in seen_providers:
            selected.append(entry)
            seen_providers.add(prov)
        if len(selected) >= 2:
            break
    return selected


def describe_cleaning_brain(config: Any) -> dict:
    """Describe the LLM configuration used for document cleaning.

    Returns the provider/model that will be used for cleaning, based on
    available API keys.

    Args:
        config: ARIA Config instance.

    Returns:
        Dict with provider, model_id, base_url, and notes fields.
    """
    # Priority order: Anthropic > OpenRouter > OpenAI > Ollama
    ant_key = os.getenv("ANTHROPIC_API_KEY")
    if ant_key:
        return {
            "provider": "anthropic",
            "model_id": "claude-3-haiku-20240307",
            "base_url": None,
            "notes": "Anthropic Claude 3 Haiku (direct)",
            "available": True,
        }

    or_key = os.getenv("OPENROUTER_API_KEY")
    if or_key:
        return {
            "provider": "openrouter",
            "model_id": "openai/gpt-4o-mini",
            "base_url": "https://openrouter.ai/api/v1",
            "notes": "OpenRouter / GPT-4o Mini",
            "available": True,
        }

    oai_key = os.getenv("OPENAI_API_KEY")
    if oai_key:
        return {
            "provider": "openai",
            "model_id": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
            "notes": "OpenAI GPT-4o Mini (direct)",
            "available": True,
        }

    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return {
        "provider": "ollama",
        "model_id": "llama3.1:8b",
        "base_url": ollama_base,
        "notes": "Local Ollama / Llama 3.1 8B (no LLM key set)",
        "available": False,  # Flag as potentially unavailable
    }


def resolve_cleaning_llm(config: Any) -> tuple[str, str, Optional[str], str]:
    """Single source of truth for which LLM to use for cleaning/planning.

    Priority: Anthropic > OpenRouter > OpenAI > Ollama (local fallback).

    Returns:
        Tuple of (provider, model_id, base_url, api_key).
    """
    ant_key = os.getenv("ANTHROPIC_API_KEY", "")
    if ant_key:
        return ("anthropic", "claude-3-haiku-20240307", None, ant_key)

    or_key = os.getenv("OPENROUTER_API_KEY", "")
    if or_key:
        return ("openrouter", "openai/gpt-4o-mini", "https://openrouter.ai/api/v1", or_key)

    oai_key = os.getenv("OPENAI_API_KEY", "")
    if oai_key:
        return ("openai", "gpt-4o-mini", "https://api.openai.com/v1", oai_key)

    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return ("ollama", "llama3.1:8b", ollama_base + "/v1", "ollama")
