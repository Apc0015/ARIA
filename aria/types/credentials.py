"""Per-run credential scope — immutable snapshot replacing os.environ mutation.

Collectors that read os.environ directly (twitter, slack, notion, github,
ieee, elsevier, springer, etc.) continue to work via the base .env values
already loaded at startup. CredentialScope only carries run-specific
overrides passed by the API client; the orchestrator plumbs it through
so collectors can opt in without touching os.environ.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class CredentialScope:
    # LLM providers
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    # Search
    serpapi_key: Optional[str] = None
    # Social
    twitter_bearer_token: Optional[str] = None
    slack_token: Optional[str] = None
    notion_token: Optional[str] = None
    # Academic
    ieee_api_key: Optional[str] = None
    elsevier_api_key: Optional[str] = None
    springer_api_key: Optional[str] = None
    jstor_session_cookie: Optional[str] = None
    acm_session_cookie: Optional[str] = None
    # Media
    vimeo_access_token: Optional[str] = None
    # News
    news_api_key: Optional[str] = None
    gnews_api_key: Optional[str] = None
    # GitHub
    github_token: Optional[str] = None
    # Zotero
    zotero_api_key: Optional[str] = None
    zotero_library_id: Optional[str] = None
    # OSINT
    shodan_api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "CredentialScope":
        """Build a CredentialScope from current os.environ — snapshot, not live."""
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL"),
            serpapi_key=os.getenv("SERPAPI_KEY"),
            twitter_bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
            slack_token=os.getenv("SLACK_TOKEN"),
            notion_token=os.getenv("NOTION_TOKEN"),
            ieee_api_key=os.getenv("IEEE_API_KEY"),
            elsevier_api_key=os.getenv("ELSEVIER_API_KEY"),
            springer_api_key=os.getenv("SPRINGER_API_KEY"),
            jstor_session_cookie=os.getenv("JSTOR_SESSION_COOKIE"),
            acm_session_cookie=os.getenv("ACM_SESSION_COOKIE"),
            vimeo_access_token=os.getenv("VIMEO_ACCESS_TOKEN"),
            news_api_key=os.getenv("NEWS_API_KEY"),
            gnews_api_key=os.getenv("GNEWS_API_KEY"),
            github_token=os.getenv("GITHUB_TOKEN"),
            zotero_api_key=os.getenv("ZOTERO_API_KEY"),
            zotero_library_id=os.getenv("ZOTERO_LIBRARY_ID"),
            shodan_api_key=os.getenv("SHODAN_API_KEY"),
        )

    @classmethod
    def from_dict(cls, d: dict) -> "CredentialScope":
        """Build from a credentials dict (e.g. loaded from credentials.json).

        Keys from the dict override matching env vars; everything else falls
        back to the current environment.
        """
        merged: dict[str, str] = {k.lower(): v for k, v in os.environ.items()}
        merged.update({k.lower(): v for k, v in d.items() if v})
        return cls(
            openai_api_key=merged.get("openai_api_key"),
            anthropic_api_key=merged.get("anthropic_api_key"),
            openrouter_api_key=merged.get("openrouter_api_key"),
            ollama_base_url=merged.get("ollama_base_url"),
            serpapi_key=merged.get("serpapi_key"),
            twitter_bearer_token=merged.get("twitter_bearer_token"),
            slack_token=merged.get("slack_token"),
            notion_token=merged.get("notion_token"),
            ieee_api_key=merged.get("ieee_api_key"),
            elsevier_api_key=merged.get("elsevier_api_key"),
            springer_api_key=merged.get("springer_api_key"),
            jstor_session_cookie=merged.get("jstor_session_cookie"),
            acm_session_cookie=merged.get("acm_session_cookie"),
            vimeo_access_token=merged.get("vimeo_access_token"),
            news_api_key=merged.get("news_api_key"),
            gnews_api_key=merged.get("gnews_api_key"),
            github_token=merged.get("github_token"),
            zotero_api_key=merged.get("zotero_api_key"),
            zotero_library_id=merged.get("zotero_library_id"),
            shodan_api_key=merged.get("shodan_api_key"),
        )
