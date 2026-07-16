"""Per-run credential scope and environment overlay helpers.

Most collectors still resolve credentials with ``os.getenv``.  To keep those
collectors working while avoiding permanent process-wide secret mutation, API
runs build a CredentialScope from saved UI credentials and apply it only while
the run is executing.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
from dataclasses import dataclass, field
from typing import Optional


_FIELD_ENV_MAP = {
    # LLM providers
    "openai_api_key": "OPENAI_API_KEY",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "openrouter_api_key": "OPENROUTER_API_KEY",
    "ollama_base_url": "OLLAMA_BASE_URL",
    # Search / web
    "serpapi_key": "SERPAPI_KEY",
    "reddit_client_id": "REDDIT_CLIENT_ID",
    "reddit_client_secret": "REDDIT_CLIENT_SECRET",
    "reddit_username": "REDDIT_USERNAME",
    "reddit_password": "REDDIT_PASSWORD",
    # Social
    "twitter_bearer_token": "TWITTER_BEARER_TOKEN",
    "slack_token": "SLACK_TOKEN",
    "notion_token": "NOTION_TOKEN",
    "mastodon_access_token": "MASTODON_ACCESS_TOKEN",
    # Academic
    "ieee_api_key": "IEEE_API_KEY",
    "elsevier_api_key": "ELSEVIER_API_KEY",
    "springer_api_key": "SPRINGER_API_KEY",
    "jstor_session_cookie": "JSTOR_SESSION_COOKIE",
    "acm_session_cookie": "ACM_SESSION_COOKIE",
    "core_api_key": "CORE_API_KEY",
    "pubmed_api_key": "PUBMED_API_KEY",
    "semantic_scholar_api_key": "SEMANTIC_SCHOLAR_API_KEY",
    "unpaywall_email": "UNPAYWALL_EMAIL",
    # Media
    "youtube_api_key": "YOUTUBE_API_KEY",
    "vimeo_access_token": "VIMEO_ACCESS_TOKEN",
    # News / data
    "news_api_key": "NEWS_API_KEY",
    "gnews_api_key": "GNEWS_API_KEY",
    "fred_api_key": "FRED_API_KEY",
    "propublica_api_key": "PROPUBLICA_API_KEY",
    "regulations_gov_key": "REGULATIONS_GOV_KEY",
    "adzuna_app_id": "ADZUNA_APP_ID",
    "adzuna_app_key": "ADZUNA_APP_KEY",
    # GitHub / Zotero
    "github_token": "GITHUB_TOKEN",
    "zotero_api_key": "ZOTERO_API_KEY",
    "zotero_library_id": "ZOTERO_LIBRARY_ID",
    "zotero_library_type": "ZOTERO_LIBRARY_TYPE",
    "zotero_mode": "ZOTERO_MODE",
    # OSINT keys are accepted for future collectors but not advertised until
    # collector implementations exist.
    "shodan_api_key": "SHODAN_API_KEY",
    "censys_api_id": "CENSYS_API_ID",
    "censys_api_secret": "CENSYS_API_SECRET",
    "virustotal_api_key": "VIRUSTOTAL_API_KEY",
    "hibp_api_key": "HIBP_API_KEY",
    "whoxy_api_key": "WHOXY_API_KEY",
    "hunter_api_key": "HUNTER_API_KEY",
    "social_searcher_api_key": "SOCIAL_SEARCHER_API_KEY",
}

_ENV_FIELD_MAP = {env: attr for attr, env in _FIELD_ENV_MAP.items()}
_ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class _EnvRWLock:
    """Async readers-writer lock guarding os.environ overlays.

    Runs whose overlay is a no-op against the current environment are
    "readers" and may proceed concurrently. Runs that actually need to
    mutate the environment are "writers" and get exclusive access — they
    block (and are blocked by) all other runs while their overlay is live.
    """

    def __init__(self) -> None:
        self._readers = 0
        self._readers_mutex = asyncio.Lock()
        self._writer_lock = asyncio.Lock()

    async def acquire_read(self) -> None:
        async with self._readers_mutex:
            self._readers += 1
            if self._readers == 1:
                await self._writer_lock.acquire()

    async def release_read(self) -> None:
        async with self._readers_mutex:
            self._readers -= 1
            if self._readers == 0:
                self._writer_lock.release()

    def writer(self) -> asyncio.Lock:
        return self._writer_lock


_ENV_LOCK = _EnvRWLock()


def _coerce_env_key(key: str) -> str | None:
    raw = str(key or "").strip()
    if not raw:
        return None
    upper = raw.upper()
    if upper in _ENV_FIELD_MAP or _ENV_NAME_RE.match(upper):
        return upper
    return _FIELD_ENV_MAP.get(raw.lower())


def _flatten_credentials(data: dict) -> dict[str, str]:
    """Flatten API/legacy credential payloads into ENV_KEY -> value."""
    if not isinstance(data, dict):
        return {}
    payload = data.get("platforms", data)
    if not isinstance(payload, dict):
        return {}

    flattened: dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                env_key = _coerce_env_key(f"{key}_{sub_key}")
                if env_key and sub_value:
                    flattened[env_key] = str(sub_value)
            continue
        env_key = _coerce_env_key(str(key))
        if env_key and value:
            flattened[env_key] = str(value)
    return flattened


@dataclass
class CredentialScope:
    env: dict[str, str] = field(default_factory=dict)
    # LLM providers
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    # Search
    serpapi_key: Optional[str] = None
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_username: Optional[str] = None
    reddit_password: Optional[str] = None
    # Social
    twitter_bearer_token: Optional[str] = None
    slack_token: Optional[str] = None
    notion_token: Optional[str] = None
    mastodon_access_token: Optional[str] = None
    # Academic
    ieee_api_key: Optional[str] = None
    elsevier_api_key: Optional[str] = None
    springer_api_key: Optional[str] = None
    jstor_session_cookie: Optional[str] = None
    acm_session_cookie: Optional[str] = None
    core_api_key: Optional[str] = None
    pubmed_api_key: Optional[str] = None
    semantic_scholar_api_key: Optional[str] = None
    unpaywall_email: Optional[str] = None
    # Media
    youtube_api_key: Optional[str] = None
    vimeo_access_token: Optional[str] = None
    # News
    news_api_key: Optional[str] = None
    gnews_api_key: Optional[str] = None
    fred_api_key: Optional[str] = None
    propublica_api_key: Optional[str] = None
    regulations_gov_key: Optional[str] = None
    adzuna_app_id: Optional[str] = None
    adzuna_app_key: Optional[str] = None
    # GitHub
    github_token: Optional[str] = None
    # Zotero
    zotero_api_key: Optional[str] = None
    zotero_library_id: Optional[str] = None
    zotero_library_type: Optional[str] = None
    zotero_mode: Optional[str] = None
    # OSINT
    shodan_api_key: Optional[str] = None
    censys_api_id: Optional[str] = None
    censys_api_secret: Optional[str] = None
    virustotal_api_key: Optional[str] = None
    hibp_api_key: Optional[str] = None
    whoxy_api_key: Optional[str] = None
    hunter_api_key: Optional[str] = None
    social_searcher_api_key: Optional[str] = None

    @classmethod
    def _from_env_dict(cls, env: dict[str, str]) -> "CredentialScope":
        kwargs = {"env": {k: v for k, v in env.items() if v}}
        for attr, env_name in _FIELD_ENV_MAP.items():
            kwargs[attr] = env.get(env_name)
        return cls(**kwargs)

    @classmethod
    def from_env(cls) -> "CredentialScope":
        """Build a CredentialScope from current os.environ — snapshot, not live."""
        env = {
            env_name: os.getenv(env_name, "")
            for env_name in _ENV_FIELD_MAP
            if os.getenv(env_name)
        }
        return cls._from_env_dict(env)

    @classmethod
    def from_dict(cls, d: dict) -> "CredentialScope":
        """Build from a credentials dict (e.g. loaded from credentials.json).

        Keys from the dict override matching env vars; everything else falls
        back to recognized current environment credentials.
        """
        env = CredentialScope.from_env().to_env()
        env.update(_flatten_credentials(d))
        return cls._from_env_dict(env)

    def to_env(self) -> dict[str, str]:
        env = {k: v for k, v in self.env.items() if v}
        for attr, env_name in _FIELD_ENV_MAP.items():
            value = getattr(self, attr, None)
            if value:
                env[env_name] = value
        return env

    def get(self, env_name: str, scope_attr: str | None = None) -> str:
        if scope_attr:
            value = getattr(self, scope_attr, None)
            if value:
                return value
        return self.to_env().get(env_name, "")


def _is_noop(overrides: dict[str, str]) -> bool:
    return all(os.environ.get(k) == v for k, v in overrides.items())


@contextlib.asynccontextmanager
async def scoped_environ(overrides: dict[str, str]):
    """Temporarily apply env overrides, serializing only when necessary.

    The overlay for most runs equals the process environment (credentials come
    from .env / the shared saved store), so applying it changes nothing. Those
    runs take a shared read slot and execute CONCURRENTLY. Only a run whose
    overlay genuinely differs takes the exclusive writer lock — it waits for
    in-flight runs, applies its overlay, and restores the environment when done.

    This keeps per-run credential overrides correct without the old behavior
    of serializing every run behind a single process-wide lock.
    """
    clean = {k: str(v) for k, v in overrides.items() if k and v}

    if _is_noop(clean):
        await _ENV_LOCK.acquire_read()
        try:
            # Recheck under the read slot: while we hold it no writer can be
            # active, so the environment is authoritative base state.
            if _is_noop(clean):
                yield
                return
        finally:
            await _ENV_LOCK.release_read()
        # Classification changed between check and acquisition — fall through
        # to the writer path. (release_read above already ran.)

    async with _ENV_LOCK.writer():
        old: dict[str, str | None] = {k: os.environ.get(k) for k in clean}
        try:
            os.environ.update(clean)
            yield
        finally:
            for key, previous in old.items():
                if previous is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous
