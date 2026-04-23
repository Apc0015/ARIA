"""Per-key rate limiting for ARIA Studio API."""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Sliding window rate limits
_RUN_LIMIT = int(os.environ.get("ARIA_RATE_LIMIT_RUNS_PER_HOUR", "30"))  # new runs per key per hour
_REQ_LIMIT = int(os.environ.get("ARIA_RATE_LIMIT_REQS_PER_MIN", "300"))  # total requests per key per minute

_run_windows: dict[str, deque] = defaultdict(deque)   # key → timestamps of run starts
_req_windows: dict[str, deque] = defaultdict(deque)   # key → timestamps of all requests
_lock = Lock()

# Paths exempt from request rate limiting (health checks, polling is fine)
_RATE_EXEMPT = {"/api/health", "/"}


def _sliding_count(window: deque, window_secs: float) -> int:
    now = time.monotonic()
    cutoff = now - window_secs
    while window and window[0] < cutoff:
        window.popleft()
    return len(window)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path in _RATE_EXEMPT:
            return await call_next(request)

        # Identify caller by API key (already validated by auth middleware)
        api_key = (
            request.headers.get("X-API-Key", "")
            or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            or request.client.host  # fallback to IP
        )

        now = time.monotonic()
        with _lock:
            # 1. General request rate: 300 req/min per key
            req_w = _req_windows[api_key]
            _sliding_count(req_w, 60)
            if len(req_w) >= _REQ_LIMIT:
                return JSONResponse(
                    {"detail": f"Rate limit exceeded. Max {_REQ_LIMIT} requests/minute."},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            req_w.append(now)

            # 2. Run creation rate: 30 runs/hour per key (POST /api/runs only)
            if request.method == "POST" and path == "/api/runs":
                run_w = _run_windows[api_key]
                _sliding_count(run_w, 3600)
                if len(run_w) >= _RUN_LIMIT:
                    return JSONResponse(
                        {"detail": f"Run rate limit exceeded. Max {_RUN_LIMIT} new runs/hour."},
                        status_code=429,
                        headers={"Retry-After": "3600"},
                    )
                run_w.append(now)

        return await call_next(request)
