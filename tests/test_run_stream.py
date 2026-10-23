"""Live run event stream (SSE): tenant isolation and event delivery."""

import asyncio
import os
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from aria.api.app import app
from aria.api.events import _subscribers, publish_event
from aria.api.routes.stream import _event_stream
from aria.api.run_manager import RunState


def _session(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.cookies.get("aria_session", "")


def test_stream_is_tenant_scoped_and_closes_for_finished_runs():
    os.environ["ARIA_COOKIE_SECURE"] = "false"
    store = app.state.tenant_store
    suffix = uuid4().hex
    owner = store.create_tenant_admin("Stream A", f"stream-a-{suffix}@example.com", "correct-horse-battery-staple")
    store.create_tenant_admin("Stream B", f"stream-b-{suffix}@example.com", "correct-horse-battery-staple")
    state = RunState(run_id=f"stream-run-{suffix}", tenant_id=owner["tenant_id"], user_id=owner["id"], status="completed", stage="completed")
    app.state.run_manager.runs[state.run_id] = state

    with TestClient(app) as client:
        foreign = {"Cookie": f"aria_session={_session(client, f'stream-b-{suffix}@example.com', 'correct-horse-battery-staple')}"}
        assert client.get(f"/api/runs/{state.run_id}/stream", headers=foreign).status_code == 404

        mine = {"Cookie": f"aria_session={_session(client, f'stream-a-{suffix}@example.com', 'correct-horse-battery-staple')}"}
        response = client.get(f"/api/runs/{state.run_id}/stream", headers=mine)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: state" in response.text
        assert "event: done" in response.text
        assert '"status": "completed"' in response.text
    assert state.run_id not in _subscribers


def test_stream_delivers_published_events_until_the_run_finishes():
    run_id = f"live-{uuid4().hex}"
    run = SimpleNamespace(status="running")

    class FakeManager:
        runs = {run_id: run}

        async def get_run(self, _run_id):
            return {"run_id": run_id, "status": run.status}

    class FakeRequest:
        async def is_disconnected(self):
            return False

    async def consume() -> list[str]:
        chunks = []
        stream = _event_stream(FakeRequest(), FakeManager(), run_id)
        chunks.append(await stream.__anext__())  # initial state snapshot
        publish_event(run_id, "collect_done", {"stage": "collect_done", "count": 12})
        chunks.append(await stream.__anext__())
        run.status = "completed"
        publish_event(run_id, "status", {"status": "completed"})
        async for chunk in stream:
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(consume())
    assert chunks[0].startswith("event: state")
    assert chunks[1] == 'event: collect_done\ndata: {"stage": "collect_done", "count": 12}\n\n'
    assert chunks[2].startswith("event: status")
    assert chunks[-1].startswith("event: done")
    assert run_id not in _subscribers
