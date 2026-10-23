"""Regression tests for API auth defaults and rate-limiter hardening.

These encode the launch-blocker fixes from the production readiness audit:
fail-closed auth, spoof-proof rate-limit identity, and bounded memory.
"""

from __future__ import annotations

from collections import OrderedDict

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aria.api.middleware.auth import ApiKeyMiddleware, resolve_auth


def _app_with_auth(require_key: bool, api_key: str = "secret-key") -> TestClient:
    app = FastAPI()

    @app.get("/api/data")
    async def data():
        return {"ok": True}

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    app.add_middleware(ApiKeyMiddleware, require_key=require_key, api_key=api_key)
    return TestClient(app)


# ---------------------------------------------------------------------------
# resolve_auth — fail-closed defaults
# ---------------------------------------------------------------------------

def test_auth_required_by_default_generates_key(monkeypatch):
    monkeypatch.delenv("ARIA_API_KEY", raising=False)
    monkeypatch.delenv("ARIA_API_KEY_REQUIRED", raising=False)
    required, key = resolve_auth()
    assert required is True
    assert len(key) >= 32  # generated, never empty


def test_auth_uses_configured_key(monkeypatch):
    monkeypatch.setenv("ARIA_API_KEY", "my-key")
    monkeypatch.delenv("ARIA_API_KEY_REQUIRED", raising=False)
    assert resolve_auth() == (True, "my-key")


def test_auth_explicit_opt_out(monkeypatch):
    monkeypatch.delenv("ARIA_API_KEY", raising=False)
    monkeypatch.setenv("ARIA_API_KEY_REQUIRED", "false")
    required, _ = resolve_auth()
    assert required is False


# ---------------------------------------------------------------------------
# ApiKeyMiddleware — enforcement
# ---------------------------------------------------------------------------

def test_missing_key_rejected():
    client = _app_with_auth(require_key=True)
    assert client.get("/api/data").status_code == 401


def test_wrong_key_rejected():
    client = _app_with_auth(require_key=True)
    assert client.get("/api/data", headers={"X-API-Key": "nope"}).status_code == 401


def test_valid_x_api_key_accepted():
    client = _app_with_auth(require_key=True)
    resp = client.get("/api/data", headers={"X-API-Key": "secret-key"})
    assert resp.status_code == 200


def test_valid_bearer_accepted():
    client = _app_with_auth(require_key=True)
    resp = client.get("/api/data", headers={"Authorization": "Bearer secret-key"})
    assert resp.status_code == 200


def test_health_exempt_from_auth():
    client = _app_with_auth(require_key=True)
    assert client.get("/api/health").status_code == 200


def test_auth_disabled_allows_requests():
    client = _app_with_auth(require_key=False)
    assert client.get("/api/data").status_code == 200


# ---------------------------------------------------------------------------
# Rate limiter — identity and memory bounds
# ---------------------------------------------------------------------------

def test_rate_identity_ignores_api_key_header(monkeypatch):
    """A rotated X-API-Key header must NOT grant a fresh rate window."""
    from aria.api.middleware import rate_limit as rl

    class _Req:
        headers = {"X-API-Key": "attacker-rotates-this"}

        class client:  # noqa: N801 — mimic starlette shape
            host = "203.0.113.9"

    monkeypatch.setattr(rl, "_TRUST_PROXY", False)
    assert rl._client_identity(_Req()) == "203.0.113.9"


def test_rate_identity_uses_forwarded_ip_behind_proxy(monkeypatch):
    from aria.api.middleware import rate_limit as rl

    class _Req:
        headers = {"X-Forwarded-For": "198.51.100.7, 10.0.0.2"}

        class client:  # noqa: N801
            host = "172.18.0.3"  # nginx container IP

    monkeypatch.setattr(rl, "_TRUST_PROXY", True)
    assert rl._client_identity(_Req()) == "198.51.100.7"


def test_rate_windows_are_lru_capped(monkeypatch):
    from collections import OrderedDict
    from aria.api.middleware import rate_limit as rl

    monkeypatch.setattr(rl, "_MAX_TRACKED", 100)
    windows: OrderedDict = OrderedDict()
    for i in range(1000):
        rl._window(windows, f"10.0.{i // 256}.{i % 256}")
    assert len(windows) <= 100  # unbounded per-client dict was a memory DoS


def test_login_attempts_have_a_dedicated_bounded_window(monkeypatch):
    from aria.api.middleware import rate_limit as rl

    monkeypatch.setattr(rl, "_MAX_TRACKED", 3)
    windows = OrderedDict()
    for index in range(10):
        rl._window(windows, f"198.51.100.{index}")
    assert len(windows) == 3
