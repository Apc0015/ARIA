"""LLM provider discovery and catalog building."""

from __future__ import annotations

import os
from typing import Any, Optional


class LLMUnavailableError(ValueError):
    """Raised when a run needs an LLM but none is ready to use."""


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
    provider, model_id, base_url, api_key = resolve_cleaning_llm(config)
    if not provider:
        return {
            "provider": "none",
            "model_id": "",
            "base_url": None,
            "notes": "No LLM connected",
            "available": False,
        }
    return {
        "provider": provider,
        "model_id": model_id,
        "base_url": base_url,
        "notes": f"Configured {provider} model",
        "available": bool(api_key) or provider == "ollama",
    }


def resolve_cleaning_llm(config: Any) -> tuple[str, str, Optional[str], str]:
    """Single source of truth for which LLM to use for cleaning/planning.

    A selected ``LLM_PROVIDER`` takes priority. Otherwise, a configured cloud
    key is selected in the historical priority order. There is deliberately no
    pretend local-model fallback: a run must tell the user to connect an LLM.

    Returns:
        Tuple of (provider, model_id, base_url, api_key).
    """
    selected = os.getenv("LLM_PROVIDER", "").strip().lower()
    defaults = {
        "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "claude-3-haiku-20240307", None),
        "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "openai/gpt-4o-mini", "https://openrouter.ai/api/v1"),
        "openai": ("OPENAI_API_KEY", "OPENAI_MODEL", "gpt-4o-mini", "https://api.openai.com/v1"),
    }
    if selected == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        return ("ollama", os.getenv("OLLAMA_MODEL", "llama3.1:8b"), f"{base_url}/v1", "ollama")
    if selected in defaults:
        key_name, model_name, default_model, base_url = defaults[selected]
        return (selected, os.getenv(model_name, default_model), base_url, os.getenv(key_name, ""))

    for provider in ("anthropic", "openrouter", "openai"):
        key_name, model_name, default_model, base_url = defaults[provider]
        api_key = os.getenv(key_name, "")
        if api_key:
            return (provider, os.getenv(model_name, default_model), base_url, api_key)

    if os.getenv("OLLAMA_BASE_URL"):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        return ("ollama", os.getenv("OLLAMA_MODEL", "llama3.1:8b"), f"{base_url}/v1", "ollama")
    return ("", "", None, "")


async def ensure_llm_ready(config: Any = None) -> tuple[str, str, Optional[str], str]:
    """Return a ready LLM configuration or a clear user-facing error."""
    provider, model_id, base_url, api_key = resolve_cleaning_llm(config)
    if not provider or (provider != "ollama" and not api_key):
        raise LLMUnavailableError(
            "No LLM connected. Connect an AI model in Settings, then run again."
        )
    if provider != "ollama":
        return provider, model_id, base_url, api_key

    import httpx

    ollama_url = (base_url or "http://localhost:11434/v1").removesuffix("/v1")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{ollama_url}/api/tags")
        response.raise_for_status()
        models = {model.get("name", "") for model in response.json().get("models", [])}
    except Exception as exc:
        raise LLMUnavailableError(
            "No LLM connected. Start Ollama or connect an AI model in Settings, then run again."
        ) from exc
    if model_id not in models:
        raise LLMUnavailableError(
            f"No LLM connected. Ollama model '{model_id}' is not installed. "
            "Connect an AI model in Settings, then run again."
        )
    return provider, model_id, base_url, api_key
