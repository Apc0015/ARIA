"""Seed paper preview route and seeded run payloads (no network)."""

import os
from uuid import uuid4

import pytest
import yaml
from fastapi.testclient import TestClient

from aria.api.app import app
from aria.api.routes.runs import _ui_payload_to_mission_yaml
from aria.api.routes.seed import parse_seed_input
from aria.engine.citation.seed import CorpusRecord, SeedResult


def _session(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.cookies.get("aria_session", "")


def test_parse_seed_input_accepts_doi_and_public_url():
    assert parse_seed_input("doi: 10.5787/52-3-1483.") == ("10.5787/52-3-1483", "")
    assert parse_seed_input(" https://example.org/paper ") == ("", "https://example.org/paper")


@pytest.mark.parametrize("value", ["", "not a doi", "http://169.254.169.254/latest", "http://localhost/x"])
def test_parse_seed_input_rejects_unusable_or_internal_input(value):
    with pytest.raises(ValueError):
        parse_seed_input(value)


def test_seeded_ui_payload_enables_citation_crawl():
    mission = yaml.safe_load(_ui_payload_to_mission_yaml({"topic": "coups", "seed_doi": "10.5787/52-3-1483"}))
    crawl = mission["citation_crawl"]
    assert crawl["enabled"] is True
    assert crawl["seed_doi"] == "10.5787/52-3-1483"
    assert crawl["seed_url"] == ""


def test_unseeded_ui_payload_has_no_citation_crawl():
    mission = yaml.safe_load(_ui_payload_to_mission_yaml({"topic": "coups"}))
    assert "citation_crawl" not in mission


def test_seed_resolve_requires_member_role_and_rejects_internal_urls(monkeypatch):
    os.environ["ARIA_COOKIE_SECURE"] = "false"
    store = app.state.tenant_store
    suffix = uuid4().hex
    admin = store.create_tenant_admin("Seed Tenant", f"seed-admin-{suffix}@example.com", "correct-horse-battery-staple")
    store.create_user(admin["tenant_id"], f"seed-viewer-{suffix}@example.com", "correct-horse-battery-staple", "viewer")

    async def fake_fetch(self, *, doi="", url=""):
        record = CorpusRecord(title="Coup Trap", doi=doi)
        return SeedResult(level0_record=record, raw_references=["Ref A", "Ref B"], parsed_references=[])

    monkeypatch.setattr("aria.engine.citation.seed.SeedFetcher.fetch", fake_fetch)

    with TestClient(app) as client:
        viewer = {"Cookie": f"aria_session={_session(client, f'seed-viewer-{suffix}@example.com', 'correct-horse-battery-staple')}"}
        assert client.get("/api/seed/resolve", params={"q": "10.1/x"}, headers=viewer).status_code == 403

        member = {"Cookie": f"aria_session={_session(client, f'seed-admin-{suffix}@example.com', 'correct-horse-battery-staple')}"}
        blocked = client.get("/api/seed/resolve", params={"q": "http://169.254.169.254/latest"}, headers=member)
        assert blocked.status_code == 400

        ok = client.get("/api/seed/resolve", params={"q": "10.5787/52-3-1483"}, headers=member)
        assert ok.status_code == 200
        assert ok.json()["title"] == "Coup Trap"
        assert ok.json()["ref_count"] == 2
