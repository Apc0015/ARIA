"""Integration tests for ARIA Studio API critical routes.

Run with: pytest tests/test_api_integration.py -v

Uses FastAPI TestClient — no live server needed.
"""
from __future__ import annotations

import pytest

# Try importing the app — skip if engine not available
try:
    from fastapi.testclient import TestClient
    from aria.api.app import app, USE_REAL_BACKEND
    HAS_CLIENT = True
except ImportError:
    HAS_CLIENT = False
    USE_REAL_BACKEND = False

skip_no_client = pytest.mark.skipif(not HAS_CLIENT, reason="fastapi TestClient not available")
skip_demo_mode = pytest.mark.skipif(not USE_REAL_BACKEND, reason="aria.engine not installed (demo mode)")


@pytest.fixture(scope="module")
def client():
    if not HAS_CLIENT:
        pytest.skip("TestClient unavailable")
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── Health ─────────────────────────────────────────────────────────────────────

@skip_no_client
class TestHealth:
    def test_health_returns_200(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_health_has_status_field(self, client):
        r = client.get("/api/health")
        body = r.json()
        assert "status" in body


# ── CORS ───────────────────────────────────────────────────────────────────────

@skip_no_client
class TestCORS:
    def test_no_wildcard_with_credentials(self, client):
        """After fix: wildcard origin + credentials=true MUST NOT co-exist."""
        r = client.options(
            "/api/health",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = r.headers.get("access-control-allow-origin", "")
        allow_creds = r.headers.get("access-control-allow-credentials", "false")
        assert not (allow_origin == "*" and allow_creds.lower() == "true"), (
            "CRITICAL: wildcard origin + credentials=true is invalid CORS"
        )

    def test_known_origin_not_blocked(self, client):
        r = client.options(
            "/api/health",
            headers={
                "Origin": "http://127.0.0.1:8765",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code != 403


# ── Runs ───────────────────────────────────────────────────────────────────────

@skip_no_client
@skip_demo_mode
class TestRuns:
    def test_list_runs_returns_200(self, client):
        r = client.get("/api/runs")
        assert r.status_code == 200

    def test_get_nonexistent_run_is_404(self, client):
        r = client.get("/api/runs/does-not-exist-xyz-abc-123")
        assert r.status_code == 404

    def test_start_run_without_topic_is_validation_error(self, client):
        r = client.post("/api/runs", json={})
        assert r.status_code in (400, 422)


# ── Download security ──────────────────────────────────────────────────────────

@skip_no_client
class TestDownloadSecurity:
    """Path traversal must be blocked regardless of backend mode."""

    def test_path_traversal_filename_rejected(self, client):
        # Use a fake run_id — we want to test filename validation before run lookup
        payloads = [
            "../../../etc/passwd",
            "..%2F..%2F..%2Fetc%2Fpasswd",
            "/etc/passwd",
            "foo/../../bar",
        ]
        for payload in payloads:
            r = client.get(f"/api/runs/fake-run-id/download/{payload}")
            assert r.status_code in (400, 403, 404), (
                f"Path traversal not blocked for payload: {payload!r} (got {r.status_code})"
            )

    def test_valid_filename_is_not_rejected_with_400(self, client):
        """A valid filename should get 404 (run not found) not 400 (validation error)."""
        r = client.get("/api/runs/fake-run-id/download/report.json")
        # 404 is correct (run doesn't exist), 400 means our regex wrongly rejected valid name
        assert r.status_code != 400, "Valid filename 'report.json' should not be rejected with 400"


# ── Credentials ────────────────────────────────────────────────────────────────

@skip_no_client
@skip_demo_mode
class TestCredentials:
    def test_save_credentials_does_not_leak_path(self, client):
        r = client.post("/api/credentials", json={"test_key": "test_value"})
        assert r.status_code in (200, 201)
        body = r.json()
        assert "path" not in body, (
            f"credentials endpoint leaks filesystem path: {body}"
        )
        assert body.get("status") == "saved"
