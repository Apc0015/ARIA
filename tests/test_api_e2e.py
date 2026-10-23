"""End-to-end API flow: create run → poll to completion → download export.

Collectors are stubbed with canned documents so the test runs offline, but
everything else is real: RunManager, credential scoping, the orchestrator
pipeline (collect_only), stores, exporters, and the download endpoint.
"""

from __future__ import annotations

import time
import zipfile
from pathlib import Path
from types import SimpleNamespace
import asyncio

import pytest

from fastapi.testclient import TestClient

CANNED_DOCS = [
    {
        "url": f"https://example.org/doc{i}",
        "title": f"Canned document {i}",
        "text": (
            f"Document {i} body about large language model evaluation. " * 20
        ),
        "source_type": "web_page",
        "platform": "stub",
        "word_count": 200,
    }
    for i in range(1, 5)
]

MISSION_YAML = """
mission:
  name: "API E2E"

collection:
  topic: "large language model evaluation"
  max_documents: 10
  max_per_source: 5
  sources:
    enabled: [web]

cleaning:
  instructions: "Extract key information."
  output_schema:
    title: string
    summary: string

output:
  formats: [json, csv, markdown, html, zip]
  sort_by: "relevance_score"
  sort_order: "desc"
"""


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    # Isolate run storage and KB, stub the collector dispatch, disable
    # network-dependent enrichment.
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("ARIA_KB_ENABLED", "false")
    monkeypatch.setenv("ARIA_SMART_QUERIES", "false")
    monkeypatch.setenv("ARIA_LINK_CRAWL", "false")
    monkeypatch.setenv("ARIA_IMAGE_EXTRACTION", "false")

    async def fake_dispatch(self, source_name, queries, max_per_source):
        return [dict(d) for d in CANNED_DOCS]

    from aria.engine.orchestrator.collection import CollectorDispatcher

    monkeypatch.setattr(CollectorDispatcher, "dispatch", fake_dispatch)

    # Fresh app state pointing at the tmp runs dir
    from fastapi import FastAPI
    from aria.api.run_manager import RunManager
    from aria.api.routes import runs_router, exports_router

    app = FastAPI()
    @app.middleware("http")
    async def authenticated_tenant(request, call_next):
        request.state.user = {"id": "test-user", "tenant_id": "test-tenant", "email": "test@example.com", "role": "admin"}
        return await call_next(request)
    manager = RunManager()
    manager.base_settings = manager.base_settings.model_copy(
        update={"runs_dir": tmp_path / "runs"}
    )
    app.state.run_manager = manager
    app.include_router(runs_router)
    app.include_router(exports_router)

    with TestClient(app) as c:
        yield c


def _poll_until_done(client: TestClient, run_id: str, timeout_s: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        r = client.get(f"/api/runs/{run_id}")
        assert r.status_code == 200
        body = r.json()
        if body["status"] in ("completed", "collection_completed", "failed"):
            return body
        time.sleep(0.1)
    pytest.fail(f"run {run_id} did not finish within {timeout_s}s")


def test_create_poll_download_flow(client, monkeypatch):
    # 1. Create a collect-only run (no LLM required)
    r = client.post(
        "/api/runs",
        json={"mission_yaml": MISSION_YAML, "flags": {"collect_only": True}},
    )
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]

    # 2. Poll until the pipeline completes
    final = _poll_until_done(client, run_id)
    assert final["status"] == "collection_completed", final.get("error")
    assert final["docs_collected"] == len(CANNED_DOCS)
    assert final["docs_cleaned"] == 0
    assert final["stats"]["cleaned"] == 0
    assert final["documents"], "completed run should expose documents"
    assert final["progress"] == 100
    assert "output_dir" not in final
    assert "exports" not in final
    assert {"raw_json", "raw_csv", "markdown", "html", "zip"}.issubset(
        set(final["available_exports"])
    )
    assert "clean_json" not in final["available_exports"]
    assert "clean_csv" not in final["available_exports"]
    assert client.app.state.run_manager.runs[run_id].flags == {"collect_only": True}
    listed = client.get("/api/runs").json()["runs"]
    assert next(run for run in listed if run["run_id"] == run_id)["progress"] == 100

    # 3. Export info endpoints report a download URL
    info = client.get(f"/api/runs/{run_id}/export/raw").json()
    assert info["download_url"], info
    assert info["filename"] == "raw_documents.json"
    assert "path" not in info

    # 4. Download every generated export through the API
    downloaded = 0
    for name in set(
        Path(path).name
        for path in client.app.state.run_manager.runs[run_id].exports.values()
    ):
        resp = client.get(f"/api/runs/{run_id}/download/{name}")
        assert resp.status_code == 200, f"{name}: {resp.status_code}"
        assert len(resp.content) > 0
        downloaded += 1
    assert downloaded >= 3  # json + csv + markdown at minimum

    archive = Path(client.app.state.run_manager.runs[run_id].exports["zip"])
    with zipfile.ZipFile(archive) as bundle:
        assert {"raw_documents.json", "raw_documents.csv", "research_digest.md", "report.html"}.issubset(
            set(bundle.namelist())
        )
        assert "clean_documents.json" not in bundle.namelist()
        assert "clean_documents.csv" not in bundle.namelist()

    finding = client.post(
        f"/api/runs/{run_id}/findings",
        json={"statement": "The evidence set is ready for review.", "evidence_document_indexes": [0]},
    )
    assert finding.status_code == 200
    with zipfile.ZipFile(archive) as bundle:
        assert "approved_findings.json" in bundle.namelist()

    # 4b. A symlink placed inside a run directory must not expose a file
    # outside that run's tenant-owned artifact boundary.
    outside = Path(client.app.state.run_manager.base_settings.runs_dir).parent / "outside-secret.json"
    outside.write_text('{"private": true}', encoding="utf-8")
    leak = Path(client.app.state.run_manager.runs[run_id].output_dir) / "leak.json"
    leak.symlink_to(outside)
    assert client.get(f"/api/runs/{run_id}/download/leak.json").status_code == 403

    # 4c. Restart retains the collection-only contract instead of silently
    # changing into a full LLM-backed run after an API restart.
    state = client.app.state.run_manager.runs[run_id]
    state.status = "interrupted"
    captured: dict = {}

    async def fake_start(payload, *, tenant_id, user_id):
        captured.update(payload)
        return SimpleNamespace(run_id="restarted-run", status="queued")

    monkeypatch.setattr(client.app.state.run_manager, "start_run", fake_start)
    restarted = client.post(f"/api/runs/{run_id}/restart")
    assert restarted.status_code == 200
    assert captured["flags"] == {"collect_only": True}

    # 5. Run history survives a RunManager restart (new instance, same disk)
    from aria.api.run_manager import RunManager

    reloaded = RunManager()
    reloaded.base_settings = client.app.state.run_manager.base_settings
    reloaded.runs = {}
    reloaded._load_persisted_runs()
    assert run_id in reloaded.runs
    assert reloaded.runs[run_id].status == "collection_completed"


def test_manager_shutdown_marks_unfinished_runs_interrupted(tmp_path: Path):
    from aria.api.run_manager import RunManager, RunState

    manager = RunManager()
    output_dir = tmp_path / "shutdown-run"
    output_dir.mkdir()
    state = RunState(
        run_id="shutdown-run",
        status="running",
        stage="collect",
        output_dir=str(output_dir),
        tenant_id="tenant",
    )
    manager.runs[state.run_id] = state
    asyncio.run(manager.shutdown())

    assert state.status == "interrupted"
    assert state.stage == "interrupted"
    assert "shutdown" in state.message.lower()
    assert (output_dir / "run_state.json").exists()
