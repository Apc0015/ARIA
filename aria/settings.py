"""Validated application settings via pydantic-settings.

All environment variables are validated at startup with clear error messages
for missing required values and automatic type coercion.

Usage:
    from aria.settings import get_settings
    settings = get_settings()
    print(settings.llm_provider)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ARIASettings(BaseSettings):
    """All ARIA configuration in one validated place.

    Values are read from environment variables (case-insensitive).
    A .env file in the project root is loaded automatically.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # silently ignore unknown env vars
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: Literal["openrouter", "openai", "anthropic", "ollama"] = Field(
        default="openrouter",
        description="Which LLM provider to use for cleaning and intelligence.",
    )
    openrouter_api_key: Optional[str] = Field(default=None)
    openrouter_model: str = Field(default="openai/gpt-4o-mini")
    openai_api_key: Optional[str] = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")
    anthropic_api_key: Optional[str] = Field(default=None)
    anthropic_model: str = Field(default="claude-3-5-haiku-latest")
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.1:8b")
    llm_max_tokens: int = Field(default=2000, ge=100, le=16000)
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)

    # ── Search ────────────────────────────────────────────────────────────────
    serpapi_key: Optional[str] = Field(default=None)

    # ── API server ────────────────────────────────────────────────────────────
    aria_api_port: int = Field(default=8765, ge=1, le=65535)
    aria_api_host: str = Field(default="0.0.0.0")
    aria_api_key: Optional[str] = Field(
        default=None,
        description="Static API key. If unset, a random ephemeral key is generated at startup.",
    )
    aria_allowed_origins: str = Field(
        default="http://localhost:8765,http://localhost:5173,http://127.0.0.1:5173"
    )
    aria_max_concurrent_runs: int = Field(default=20, ge=1, le=100)
    aria_rate_limit_runs_per_hour: int = Field(default=30, ge=1)
    aria_rate_limit_reqs_per_min: int = Field(default=300, ge=1)

    # ── Storage ───────────────────────────────────────────────────────────────
    shared_memory_backend: Literal["dict", "redis"] = Field(default="dict")
    redis_url: Optional[str] = Field(default=None)

    # ── Intelligence features ────────────────────────────────────────────────
    aria_kb_enabled: bool = Field(default=True)
    aria_gap_detection: bool = Field(default=True)
    aria_knowledge_graph: bool = Field(default=True)
    aria_semantic_dedup: bool = Field(default=False)
    aria_streaming_clean: bool = Field(default=False)

    # ── Authenticated sources ─────────────────────────────────────────────────
    twitter_bearer_token: Optional[str] = Field(default=None)
    linkedin_email: Optional[str] = Field(default=None)
    linkedin_password: Optional[str] = Field(default=None)
    notion_token: Optional[str] = Field(default=None)
    slack_token: Optional[str] = Field(default=None)
    vimeo_access_token: Optional[str] = Field(default=None)
    github_token: Optional[str] = Field(default=None)
    news_api_key: Optional[str] = Field(default=None)
    gnews_api_key: Optional[str] = Field(default=None)
    regulations_gov_key: Optional[str] = Field(default=None)
    ieee_api_key: Optional[str] = Field(default=None)
    elsevier_api_key: Optional[str] = Field(default=None)
    springer_api_key: Optional[str] = Field(default=None)
    jstor_session_cookie: Optional[str] = Field(default=None)
    acm_session_cookie: Optional[str] = Field(default=None)
    zotero_api_key: Optional[str] = Field(default=None)
    zotero_library_id: Optional[str] = Field(default=None)
    zotero_library_type: str = Field(default="user")
    core_api_key: Optional[str] = Field(default=None)
    propublica_api_key: Optional[str] = Field(default=None)
    mastodon_access_token: Optional[str] = Field(default=None)

    # ── Podcast / Whisper ─────────────────────────────────────────────────────
    podcast_transcribe: bool = Field(default=False)
    whisper_model: str = Field(default="base")

    # ── Open access ───────────────────────────────────────────────────────────
    unpaywall_email: Optional[str] = Field(default=None)

    # ── Multilingual ──────────────────────────────────────────────────────────
    multilingual_regions: str = Field(default="de-de,fr-fr,es-es,zh-cn")

    @field_validator("redis_url")
    @classmethod
    def redis_url_requires_redis_backend(cls, v: Optional[str]) -> Optional[str]:
        return v

    @model_validator(mode="after")
    def warn_if_no_llm_key(self) -> "ARIASettings":
        """Emit a warning (not an error) if the selected provider has no key."""
        import logging
        log = logging.getLogger("aria.settings")
        provider = self.llm_provider
        has_key = {
            "openrouter": bool(self.openrouter_api_key),
            "openai": bool(self.openai_api_key),
            "anthropic": bool(self.anthropic_api_key),
            "ollama": True,  # no key needed
        }
        if not has_key.get(provider, False):
            log.warning(
                "No API key set for LLM provider '%s'. "
                "Cleaning will use fallback (unscored) mode. "
                "Set %s_API_KEY in your .env to enable LLM cleaning.",
                provider,
                provider.upper(),
            )
        return self

    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.aria_allowed_origins.split(",") if o.strip()]

    def configured_sources(self) -> list[str]:
        """Return list of authenticated sources that have credentials set."""
        sources = []
        if self.twitter_bearer_token:
            sources.append("twitter")
        if self.linkedin_email and self.linkedin_password:
            sources.append("linkedin")
        if self.notion_token:
            sources.append("notion")
        if self.slack_token:
            sources.append("slack")
        if self.github_token:
            sources.append("github")
        if self.zotero_api_key:
            sources.append("zotero")
        if self.ieee_api_key:
            sources.append("ieee")
        if self.elsevier_api_key:
            sources.append("elsevier")
        if self.springer_api_key:
            sources.append("springer")
        return sources


@lru_cache(maxsize=1)
def get_settings() -> ARIASettings:
    """Return the cached application settings (parsed once at startup)."""
    return ARIASettings()
