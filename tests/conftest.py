"""Shared test fixtures."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

import pytest

# The API's secure default (auth required, auto-generated key) would make
# every unauthenticated TestClient request 401. Tests opt out explicitly,
# exactly like local dev does. Set before any aria.api import.
os.environ.setdefault("ARIA_API_KEY_REQUIRED", "false")

# Unit tests must not fetch robots.txt over the network.
os.environ.setdefault("ARIA_RESPECT_ROBOTS", "false")

from aria.config import load_config
from aria.utils.logger import configure_logging


# Env vars that select/configure the LLM or carry credentials. The developer's
# .env gets loaded during collection (aria.config, and crawl4ai as an import
# side effect), which made tests depend on local machine state.
_LLM_ENV_KEYS = (
    "LLM_PROVIDER",
    "OLLAMA_BASE_URL", "OLLAMA_MODEL",
    "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL",
    "OPENAI_API_KEY", "OPENAI_MODEL",
    "OPENROUTER_API_KEY", "OPENROUTER_MODEL",
    "SERPAPI_KEY", "UNPAYWALL_EMAIL",
)


@pytest.fixture(autouse=True, scope="session")
def _session_env_sanitizer():
    """Strip .env-derived LLM/credential state before the first test runs.

    Runs after all test modules are imported (so import-side-effect dotenv
    loads have already happened) and removes what they injected.
    """
    for key in _LLM_ENV_KEYS:
        os.environ.pop(key, None)
    yield


@pytest.fixture(autouse=True)
def _env_guard():
    """Restore os.environ after every test.

    Keeps the suite hermetic: no test can leak LLM_PROVIDER, API keys, or
    other env state into later tests (monkeypatch only reverts its own
    writes, not writes made by product code under test).
    """
    snapshot = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(snapshot)


@pytest.fixture(autouse=True)
def _rate_limit_guard():
    """Keep API test clients independent without weakening production limits."""
    from aria.api.middleware import rate_limit

    rate_limit._run_windows.clear()
    rate_limit._req_windows.clear()
    rate_limit._login_windows.clear()
    yield
    rate_limit._run_windows.clear()
    rate_limit._req_windows.clear()
    rate_limit._login_windows.clear()


@pytest.fixture
def temp_output_root() -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def aria_settings(temp_output_root: Path):
    return load_config(output_dir=temp_output_root)


@pytest.fixture
def aria_logger():
    return configure_logging(verbose=True)
