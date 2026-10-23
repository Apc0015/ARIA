"""Server-Sent Events endpoint for live run progress.

The browser's EventSource sends the session cookie on same-origin requests,
so the stream uses the normal tenant authorization: no token in the URL.

    const source = new EventSource(`/api/runs/${runId}/stream`, { withCredentials: true });
    source.addEventListener("status", (e) => ...);
    source.addEventListener("done", () => source.close());
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from aria.api.authorization import require_run_tenant
from aria.api.events import subscribe, unsubscribe

router = APIRouter(tags=["stream"])
logger = logging.getLogger("aria")

TERMINAL_STATUSES = {
    "completed",
    "completed_with_failures",
    "collection_completed",
    "failed",
    "cancelled",
    "interrupted",
}
_KEEPALIVE_SECONDS = 15.0


def _format(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


async def _event_stream(request: Request, run_manager: Any, run_id: str) -> AsyncGenerator[str, None]:
    # Subscribe before the snapshot so no event falls between the two.
    queue = subscribe(run_id)
    try:
        # Current state first so the client never starts blank.
        snapshot = await run_manager.get_run(run_id)
        yield _format("state", json.dumps(snapshot, default=str))
        while run_manager.runs[run_id].status not in TERMINAL_STATUSES:
            if await request.is_disconnected():
                return
            try:
                message = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield _format(message["event"], message["data"])
        # The run finished: flush what was published before it did.
        while not queue.empty():
            message = queue.get_nowait()
            yield _format(message["event"], message["data"])
        state = run_manager.runs[run_id]
        yield _format("done", json.dumps({"run_id": run_id, "status": state.status}))
    finally:
        unsubscribe(run_id, queue)


@router.get("/api/runs/{run_id}/stream")
async def stream_run_events(run_id: str, request: Request) -> StreamingResponse:
    """Stream live events for one of the caller's tenant's runs."""
    run_manager = request.app.state.run_manager
    require_run_tenant(request, run_manager, run_id)

    return StreamingResponse(
        _event_stream(request, run_manager, run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx: flush events immediately
        },
    )
