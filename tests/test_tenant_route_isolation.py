"""End-to-end tenant isolation checks for every run-data surface."""

import asyncio
import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from aria.api.app import app
from aria.api.run_manager import RunState


def _session(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.cookies.get("aria_session", "")


def test_foreign_tenant_cannot_access_any_run_surface(tmp_path: Path):
    os.environ["ARIA_COOKIE_SECURE"] = "false"
    os.environ["ARIA_CREDENTIALS_KEY"] = "q7uF5aD5yR0I4aV9P4KvvXPAcsn4GFZ4Vzuow9VSi9A="
    store = app.state.tenant_store
    tenant_a = store.create_tenant_admin("Tenant A", "tenant-a-isolation@example.com", "correct-horse-battery-staple")
    store.create_tenant_admin("Tenant B", "tenant-b-isolation@example.com", "correct-horse-battery-staple")
    output_dir = tmp_path / "tenant-a" / "run-a"
    output_dir.mkdir(parents=True)
    (output_dir / "report.json").write_text("{}", encoding="utf-8")
    state = RunState(
        run_id="tenant-a-private-run",
        tenant_id=tenant_a["tenant_id"],
        user_id=tenant_a["id"],
        output_dir=str(output_dir),
        documents=[{"title": "Private", "url": "https://example.com/private", "source": "web"}],
        raw_documents=[{"title": "Private", "url": "https://example.com/private", "source": "web", "text": "secret"}],
        exports={"raw_json": str(output_dir / "report.json")},
    )
    app.state.run_manager.runs[state.run_id] = state

    with TestClient(app, raise_server_exceptions=False) as client:
        token = _session(client, "tenant-b-isolation@example.com", "correct-horse-battery-staple")
        headers = {"Cookie": f"aria_session={token}"}
        paths = [
            f"/api/runs/{state.run_id}",
            f"/api/runs/{state.run_id}/documents",
            f"/api/runs/{state.run_id}/documents/raw",
            f"/api/runs/{state.run_id}/evidence/0",
            f"/api/runs/{state.run_id}/intelligence",
            f"/api/runs/{state.run_id}/findings",
            f"/api/runs/{state.run_id}/export/raw",
            f"/api/runs/{state.run_id}/download/report.json",
        ]
        for path in paths:
            assert client.get(path, headers=headers).status_code == 404


def test_source_settings_are_scoped_to_the_authenticated_tenant():
    os.environ["ARIA_COOKIE_SECURE"] = "false"
    store = app.state.tenant_store
    store.create_tenant_admin("Settings A", "settings-a@example.com", "correct-horse-battery-staple")
    store.create_tenant_admin("Settings B", "settings-b@example.com", "correct-horse-battery-staple")
    with TestClient(app) as client:
        token_a = _session(client, "settings-a@example.com", "correct-horse-battery-staple")
        token_b = _session(client, "settings-b@example.com", "correct-horse-battery-staple")
        headers_a = {"Cookie": f"aria_session={token_a}"}
        headers_b = {"Cookie": f"aria_session={token_b}"}
        assert client.put("/api/source-settings", headers=headers_a, json={"enabled_sources": {"web": True, "arxiv": False}}).status_code == 200
        assert client.get("/api/source-settings", headers=headers_b).json()["enabled_sources"] == {}


def test_viewer_role_is_read_only_for_research_configuration():
    os.environ["ARIA_COOKIE_SECURE"] = "false"
    store = app.state.tenant_store
    suffix = uuid4().hex
    admin_email = f"viewer-admin-{suffix}@example.com"
    viewer_email = f"viewer-{suffix}@example.com"
    admin = store.create_tenant_admin("Viewer Tenant", admin_email, "correct-horse-battery-staple")
    store.create_user(admin["tenant_id"], viewer_email, "correct-horse-battery-staple", "viewer")
    with TestClient(app) as client:
        token = _session(client, viewer_email, "correct-horse-battery-staple")
        headers = {"Cookie": f"aria_session={token}"}
        assert client.get("/api/source-settings", headers=headers).status_code == 200
        assert client.put("/api/source-settings", headers=headers, json={"enabled_sources": {"web": True}}).status_code == 403


def test_tenant_without_ai_configuration_is_not_given_server_default_llm(monkeypatch):
    os.environ["ARIA_COOKIE_SECURE"] = "false"
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://internal-only:11434")
    suffix = uuid4().hex
    email = f"no-llm-{suffix}@example.com"
    app.state.tenant_store.create_tenant_admin("No LLM Tenant", email, "correct-horse-battery-staple")
    with TestClient(app) as client:
        token = _session(client, email, "correct-horse-battery-staple")
        status = client.get("/api/llm/status", headers={"Cookie": f"aria_session={token}"})
    assert status.status_code == 200
    assert status.json()["provider"] == "none"
    assert status.json()["message"] == "No LLM connected. Connect an AI model in Settings."


def test_tenant_run_scope_does_not_inherit_server_ai_credentials(monkeypatch):
    monkeypatch.setenv("ARIA_SAAS_MODE", "true")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://internal-only:11434")
    suffix = uuid4().hex
    tenant = app.state.tenant_store.create_tenant_admin(
        "Scoped AI Tenant", f"scoped-ai-{suffix}@example.com", "correct-horse-battery-staple"
    )
    scope = app.state.run_manager._build_credential_scope({}, tenant["tenant_id"])
    assert "LLM_PROVIDER" not in scope.to_env()
    assert "OLLAMA_BASE_URL" not in scope.to_env()


def test_tenant_run_scope_does_not_inherit_server_source_credentials(monkeypatch):
    monkeypatch.setenv("ARIA_SAAS_MODE", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "deployment-source-token")
    suffix = uuid4().hex
    tenant = app.state.tenant_store.create_tenant_admin(
        "Scoped Source Tenant", f"scoped-source-{suffix}@example.com", "correct-horse-battery-staple"
    )
    scope = app.state.run_manager._build_credential_scope({}, tenant["tenant_id"])
    assert "GITHUB_TOKEN" not in scope.to_env()


def test_tenant_run_scope_uses_only_the_tenants_saved_source_credential(monkeypatch):
    monkeypatch.setenv("ARIA_SAAS_MODE", "true")
    monkeypatch.setenv("ARIA_CREDENTIALS_KEY", "q7uF5aD5yR0I4aV9P4KvvXPAcsn4GFZ4Vzuow9VSi9A=")
    monkeypatch.setenv("GITHUB_TOKEN", "deployment-source-token")
    suffix = uuid4().hex
    tenant = app.state.tenant_store.create_tenant_admin(
        "Scoped Saved Source Tenant", f"scoped-saved-source-{suffix}@example.com", "correct-horse-battery-staple"
    )
    app.state.run_manager.save_credentials(tenant["tenant_id"], {"GITHUB_TOKEN": "tenant-source-token"})
    scope = app.state.run_manager._build_credential_scope({}, tenant["tenant_id"])
    assert scope.to_env()["GITHUB_TOKEN"] == "tenant-source-token"


def test_scoped_environment_can_temporarily_remove_server_credentials(monkeypatch):
    from aria.types.credentials import scoped_environ

    monkeypatch.setenv("OPENAI_API_KEY", "server-secret")

    async def check() -> None:
        async with scoped_environ({}, unset={"OPENAI_API_KEY"}):
            assert "OPENAI_API_KEY" not in os.environ
        assert os.environ["OPENAI_API_KEY"] == "server-secret"

    asyncio.run(check())


def test_foreign_tenant_cannot_read_director_session():
    os.environ["ARIA_COOKIE_SECURE"] = "false"
    from aria.api.routes.director import _Session, _sessions

    suffix = uuid4().hex
    owner_email = f"director-owner-{suffix}@example.com"
    other_email = f"director-other-{suffix}@example.com"
    owner = app.state.tenant_store.create_tenant_admin("Director Owner", owner_email, "correct-horse-battery-staple")
    app.state.tenant_store.create_tenant_admin("Director Other", other_email, "correct-horse-battery-staple")
    session_id = f"private-director-{suffix}"
    _sessions[session_id] = _Session("private topic", session_id, owner["tenant_id"], owner["id"])
    try:
        with TestClient(app) as client:
            token = _session(client, other_email, "correct-horse-battery-staple")
            response = client.get(f"/api/director/{session_id}", headers={"Cookie": f"aria_session={token}"})
        assert response.status_code == 404
    finally:
        _sessions.pop(session_id, None)


def test_other_member_cannot_access_a_director_session_in_the_same_tenant():
    os.environ["ARIA_COOKIE_SECURE"] = "false"
    from aria.api.routes.director import _Session, _sessions

    suffix = uuid4().hex
    owner_email = f"director-member-owner-{suffix}@example.com"
    member_email = f"director-member-other-{suffix}@example.com"
    owner = app.state.tenant_store.create_tenant_admin("Director Member Tenant", owner_email, "correct-horse-battery-staple")
    app.state.tenant_store.create_user(owner["tenant_id"], member_email, "correct-horse-battery-staple", "member")
    session_id = f"private-director-member-{suffix}"
    _sessions[session_id] = _Session("private topic", session_id, owner["tenant_id"], owner["id"])
    try:
        with TestClient(app) as client:
            token = _session(client, member_email, "correct-horse-battery-staple")
            headers = {"Cookie": f"aria_session={token}"}
            assert client.get(f"/api/director/{session_id}", headers=headers).status_code == 404
            assert client.post(
                f"/api/director/{session_id}/answer", headers=headers, json={"answer": "skip"}
            ).status_code == 404
    finally:
        _sessions.pop(session_id, None)


def test_guided_research_requires_the_tenants_ai_connection():
    os.environ["ARIA_COOKIE_SECURE"] = "false"
    suffix = uuid4().hex
    email = f"director-no-llm-{suffix}@example.com"
    app.state.tenant_store.create_tenant_admin("No Director LLM", email, "correct-horse-battery-staple")
    with TestClient(app) as client:
        token = _session(client, email, "correct-horse-battery-staple")
        response = client.post(
            "/api/director/session",
            headers={"Cookie": f"aria_session={token}"},
            json={"topic": "climate policy"},
        )
    assert response.status_code == 422
    assert response.json()["detail"] == "No LLM connected. Connect an AI model in Settings, then run again."


def test_full_research_run_requires_the_tenants_ai_connection():
    os.environ["ARIA_COOKIE_SECURE"] = "false"
    suffix = uuid4().hex
    email = f"run-no-llm-{suffix}@example.com"
    app.state.tenant_store.create_tenant_admin("No Run LLM", email, "correct-horse-battery-staple")
    mission = """
collection:
  topic: climate policy
  sources:
    enabled: [wikipedia]
cleaning:
  instructions: Extract evidence.
  output_schema:
    title: string
output:
  formats: [json]
"""
    with TestClient(app) as client:
        token = _session(client, email, "correct-horse-battery-staple")
        response = client.post(
            "/api/runs",
            headers={"Cookie": f"aria_session={token}"},
            json={"mission_yaml": mission},
        )
    assert response.status_code == 422
    assert response.json()["detail"] == "No LLM connected. Connect an AI model in Settings, then run again."


def test_director_never_returns_a_heuristic_brief_after_an_ai_failure():
    from aria.engine.intelligence.research_director import ResearchDirector

    async def unavailable_model(_prompt: str, _system: str) -> str:
        raise RuntimeError("provider request failed")

    async def run() -> None:
        director = ResearchDirector(llm_caller=unavailable_model)
        generator = director.run_conversation("climate policy")
        try:
            await generator.asend(None)
            assert False, "expected AI failure to stop guided research"
        except RuntimeError as exc:
            assert "provider request failed" in str(exc)

    asyncio.run(run())


def test_last_organization_admin_cannot_be_disabled_or_demoted():
    store = app.state.tenant_store
    suffix = uuid4().hex
    admin = store.create_tenant_admin(
        "Protected Admin Tenant", f"protected-admin-{suffix}@example.com", "correct-horse-battery-staple"
    )
    try:
        store.update_user(admin["tenant_id"], admin["id"], disabled=True)
        assert False, "expected last-admin protection"
    except ValueError as exc:
        assert "at least one active administrator" in str(exc)
    try:
        store.update_user(admin["tenant_id"], admin["id"], role="member")
        assert False, "expected last-admin protection"
    except ValueError as exc:
        assert "at least one active administrator" in str(exc)


def test_user_can_change_password_and_old_sessions_are_revoked():
    os.environ["ARIA_COOKIE_SECURE"] = "false"
    suffix = uuid4().hex
    email = f"password-change-{suffix}@example.com"
    old_password = "correct-horse-battery-staple"
    new_password = "new-correct-horse-battery-staple"
    app.state.tenant_store.create_tenant_admin("Password Tenant", email, old_password)
    with TestClient(app) as client:
        token = _session(client, email, old_password)
        headers = {"Cookie": f"aria_session={token}"}
        assert client.post(
            "/api/auth/password",
            headers=headers,
            json={"current_password": "wrong-password", "new_password": new_password},
        ).status_code == 401
        assert client.post(
            "/api/auth/password",
            headers=headers,
            json={"current_password": old_password, "new_password": "too-short"},
        ).status_code == 422
        assert client.post(
            "/api/auth/password",
            headers=headers,
            json={"current_password": old_password, "new_password": new_password},
        ).status_code == 200
        assert client.get("/api/auth/me", headers=headers).status_code == 401
        assert client.post("/api/auth/login", json={"email": email, "password": old_password}).status_code == 401
        assert client.post("/api/auth/login", json={"email": email, "password": new_password}).status_code == 200


def test_admin_can_reset_member_password_without_cross_tenant_access():
    os.environ["ARIA_COOKIE_SECURE"] = "false"
    suffix = uuid4().hex
    admin_email = f"reset-admin-{suffix}@example.com"
    member_email = f"reset-member-{suffix}@example.com"
    foreign_email = f"reset-foreign-{suffix}@example.com"
    old_password = "correct-horse-battery-staple"
    new_password = "replacement-correct-horse-battery-staple"
    admin = app.state.tenant_store.create_tenant_admin("Reset Tenant", admin_email, old_password)
    member = app.state.tenant_store.create_user(admin["tenant_id"], member_email, old_password)
    foreign = app.state.tenant_store.create_tenant_admin("Other Reset Tenant", foreign_email, old_password)
    with TestClient(app) as client:
        token = _session(client, admin_email, old_password)
        headers = {"Cookie": f"aria_session={token}"}
        assert client.post(
            f"/api/organization/users/{foreign['id']}/reset-password",
            headers=headers,
            json={"new_password": new_password},
        ).status_code == 404
        assert client.post(
            f"/api/organization/users/{member['id']}/reset-password",
            headers=headers,
            json={"new_password": "short"},
        ).status_code == 422
        assert client.post(
            f"/api/organization/users/{member['id']}/reset-password",
            headers=headers,
            json={"new_password": new_password},
        ).status_code == 200
        assert client.post("/api/auth/login", json={"email": member_email, "password": old_password}).status_code == 401
        assert client.post("/api/auth/login", json={"email": member_email, "password": new_password}).status_code == 200
