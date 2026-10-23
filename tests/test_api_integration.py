"""Integration tests for ARIA Studio API critical routes.

Run with: pytest tests/test_api_integration.py -v

Uses FastAPI TestClient — no live server needed.
"""
from __future__ import annotations

import os
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


@skip_no_client
class TestSPAFallback:
    """Deep links into the React app must serve index.html, not JSON 404s."""

    @pytest.fixture()
    def client(self):
        from aria.api.app import app, _REACT_DIST_DIR

        if not (_REACT_DIST_DIR / "index.html").exists():
            pytest.skip("React UI not built (aria-report/dist missing)")
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_deep_link_serves_index_html(self, client):
        r = client.get("/settings")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_parameterized_route_serves_index_html(self, client):
        r = client.get("/report/some-run-id")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_unknown_api_path_stays_json_404(self, client):
        r = client.get("/api/definitely-not-a-route")
        assert r.status_code in (401, 404)
        assert "application/json" in r.headers["content-type"]
skip_demo_mode = pytest.mark.skipif(not USE_REAL_BACKEND, reason="aria.engine not installed (demo mode)")


@pytest.fixture(scope="module")
def client():
    if not HAS_CLIENT:
        pytest.skip("TestClient unavailable")
    with TestClient(app, raise_server_exceptions=False) as c:
        os.environ["ARIA_COOKIE_SECURE"] = "false"
        os.environ["ARIA_CREDENTIALS_KEY"] = "q7uF5aD5yR0I4aV9P4KvvXPAcsn4GFZ4Vzuow9VSi9A="
        app.state.tenant_store.create_tenant_admin(
            "Integration Test Tenant", "integration@example.com", "correct-horse-battery-staple"
        )
        login = c.post(
            "/api/auth/login",
            json={"email": "integration@example.com", "password": "correct-horse-battery-staple"},
        )
        assert login.status_code == 200
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

    def test_untrusted_host_is_rejected_before_api_handling(self, client):
        response = client.get("/api/health", headers={"Host": "evil.example"})
        assert response.status_code == 400

    def test_readiness_reports_required_saas_checks(self, client):
        r = client.get("/api/health/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready"
        assert all(body["checks"].values())

    def test_readiness_fails_without_credential_encryption_key(self, client, monkeypatch):
        monkeypatch.delenv("ARIA_CREDENTIALS_KEY", raising=False)
        r = client.get("/api/health/ready")
        assert r.status_code == 503
        assert r.json()["checks"]["credential_encryption"] is False


@skip_no_client
class TestLLMProviderCatalog:
    def test_catalog_only_lists_runnable_cleaning_providers(self, client):
        from aria.engine.ensemble.providers import STATIC_MODEL_CATALOG

        assert set(STATIC_MODEL_CATALOG) == {"anthropic", "openai", "openrouter", "ollama"}
        assert client.get("/api/llm/models/gemini").status_code == 404
        assert client.get("/api/llm/models/cohere").status_code == 404


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

    def test_run_rejects_arbitrary_transient_environment_field(self, client):
        r = client.post(
            "/api/runs",
            json={
                "mission_yaml": "collection:\n  topic: safe test\n  sources:\n    enabled: [web]\n",
                "flags": {"collect_only": True},
                "credentials": {"PATH": "/tmp/untrusted"},
            },
        )
        assert r.status_code == 422
        assert "Unsupported credential field" in r.json()["detail"]


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
        r = client.post("/api/credentials", json={"OPENAI_API_KEY": "test_value"})
        assert r.status_code in (200, 201)
        body = r.json()
        assert "path" not in body, (
            f"credentials endpoint leaks filesystem path: {body}"
        )
        assert body.get("status") == "saved"

    def test_saving_one_setting_preserves_existing_credentials(self, client):
        first = "first-preserved-credential"
        second = "second-new-credential"
        assert client.post("/api/credentials", json={"ANTHROPIC_API_KEY": first}).status_code == 200
        assert client.post("/api/credentials", json={"OPENROUTER_API_KEY": second}).status_code == 200

        saved = client.get("/api/credentials").json()["platforms"]
        assert saved["ANTHROPIC_API_KEY"].startswith(first[:4])
        assert saved["OPENROUTER_API_KEY"].startswith(second[:4])

    def test_saas_rejects_arbitrary_process_environment_fields(self, client):
        r = client.post("/api/credentials", json={"PATH": "/tmp/untrusted"})
        assert r.status_code == 422
        assert "Unsupported credential field" in r.json()["detail"]
