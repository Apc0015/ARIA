"""In-process pub/sub for live run events.

Single-process only, which matches RunManager keeping run state in memory.
RunManager publishes; the SSE route subscribes.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

_QUEUE_SIZE = 500

_subscribers: dict[str, list[asyncio.Queue]] = {}


def subscribe(run_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_SIZE)
    _subscribers.setdefault(run_id, []).append(queue)
    return queue


def unsubscribe(run_id: str, queue: asyncio.Queue) -> None:
    queues = _subscribers.get(run_id, [])
    if queue in queues:
        queues.remove(queue)
    if not queues:
        _subscribers.pop(run_id, None)


def publish_event(run_id: str, event_type: str, data: dict[str, Any]) -> None:
    """Push an event to every live subscriber of a run without blocking."""
    queues = _subscribers.get(run_id)
    if not queues:
        return
    message = {"event": event_type, "data": json.dumps(data, default=str)}
    for queue in queues:
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            pass  # slow subscriber: drop rather than stall the pipeline
