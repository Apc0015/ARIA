"""Server-Sent Events (SSE) endpoint for live run progress streaming.

Clients subscribe to a run's event stream and receive documents and
progress updates as they arrive — no more waiting for the full pipeline.

Usage:
    const source = new EventSource(`/api/runs/${runId}/stream?token=${apiKey}`);
    source.addEventListener('document', e => addDoc(JSON.parse(e.data)));
    source.addEventListener('progress', e => updateProgress(JSON.parse(e.data)));
    source.addEventListener('done', () => source.close());
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()
logger = logging.getLogger("aria")

# In-memory pub/sub: run_id → list of subscriber queues
_subscribers: dict[str, list[asyncio.Queue]] = {}


def publish_event(run_id: str, event_type: str, data: dict) -> None:
    """Push an event to all active SSE subscribers for a run.

    Called from record_event in RunManager after every pipeline event.
    Thread-safe: puts into asyncio queues.
    """
    queues = _subscribers.get(run_id, [])
    payload = json.dumps(data, default=str)
    for q in queues:
        try:
            q.put_nowait({"event": event_type, "data": payload})
        except asyncio.QueueFull:
            pass  # slow subscriber — drop the event rather than block


async def _event_generator(
    run_id: str,
    run_manager: any,
    queue: asyncio.Queue,
) -> AsyncGenerator[dict, None]:
    """Yield SSE events until the run completes or client disconnects."""
    # Send current state as the first event so the client doesn't start blank
    try:
        current = await run_manager.get_run(run_id)
        yield {"event": "state", "data": json.dumps(current, default=str)}
    except Exception:
        pass

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Keep-alive ping so the connection doesn't time out
                yield {"event": "ping", "data": "{}"}
                continue

            yield event

            # Check if the run has finished
            event_data = json.loads(event.get("data", "{}"))
            stage = event_data.get("stage", "")
            if stage in ("completed", "failed", "cancelled") or event.get("event") == "done":
                yield {"event": "done", "data": json.dumps({"run_id": run_id, "stage": stage})}
                break
    finally:
        # Clean up subscriber queue
        queues = _subscribers.get(run_id, [])
        if queue in queues:
            queues.remove(queue)


@router.get("/api/runs/{run_id}/stream")
async def stream_run_events(
    run_id: str,
    request: Request,
    token: str = Query(default="", description="API key (alternative to header for EventSource)"),
) -> EventSourceResponse:
    """Stream live events for a run via Server-Sent Events.

    EventSource does not support custom headers, so the API key can be
    passed as a `?token=` query parameter as an alternative to X-API-Key.
    """
    run_manager = request.app.state.run_manager

    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    # Register this subscriber
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    _subscribers.setdefault(run_id, []).append(queue)

    return EventSourceResponse(
        _event_generator(run_id, run_manager, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
