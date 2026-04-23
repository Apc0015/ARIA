"""ARIA LLM provider configuration."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class LLMProvider(str, Enum):
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


@dataclass
class LLMConfig:
    provider: LLMProvider = LLMProvider.OPENROUTER
    model: str = "openai/gpt-4.5-turbo"
    openrouter_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    temperature: float = 0.1
    max_tokens: int = 2000
    ensemble_enabled: bool = False
    ensemble_models: list[tuple[LLMProvider, str]] = field(default_factory=list)


class ModelsByProvider:
    OPENROUTER = [
        "openai/gpt-4.5-turbo",
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-sonnet",
        "meta-llama/llama-3.1-70b",
    ]
    OPENAI = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
    ]
    ANTHROPIC = [
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
        "claude-3-opus-latest",
    ]
    OLLAMA = [
        "llama3.1:8b",
        "llama3.1:70b",
        "mistral:latest",
        "neural-chat:latest",
    ]


ENV_VARS = {
    LLMProvider.OPENROUTER: "OPENROUTER_API_KEY",
    LLMProvider.OPENAI: "OPENAI_API_KEY",
    LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
    LLMProvider.OLLAMA: None,
}


def get_provider_from_env() -> LLMProvider:
    import os
    provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
    try:
        return LLMProvider(provider)
    except ValueError:
        return LLMProvider.OPENROUTER


def load_config_from_env() -> LLMConfig:
    import os
    
    provider = get_provider_from_env()
    
    config = LLMConfig(
        provider=provider,
        model=os.getenv(f"{provider.value.upper()}_MODEL", 
                       ModelsByProvider.__dict__.get(provider.name)[0]),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2000")),
        ensemble_enabled=os.getenv("LLM_ENSEMBLE_ENABLED", "false").lower() == "true",
    )
    
    return config


__all__ = [
    "LLMProvider",
    "LLMConfig",
    "ModelsByProvider",
    "get_provider_from_env",
    "load_config_from_env",
]
