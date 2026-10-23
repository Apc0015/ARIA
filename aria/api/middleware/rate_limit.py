"""Per-client rate limiting for ARIA API.

Identity is the client IP (proxy-aware when ARIA_TRUST_PROXY=true), never a
request header the caller invents: keying on the unvalidated X-API-Key let an
attacker rotate random keys to dodge the limiter entirely while growing an
unbounded per-key window dict. Tracked identities are LRU-capped.
"""
from __future__ import annotations

import asyncio as _asyncio
import os
import time
from collections import OrderedDict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Sliding window rate limits
_RUN_LIMIT = int(os.environ.get("ARIA_RATE_LIMIT_RUNS_PER_HOUR", "30"))  # new runs per client per hour
_REQ_LIMIT = int(os.environ.get("ARIA_RATE_LIMIT_REQS_PER_MIN", "300"))  # total requests per client per minute
_LOGIN_LIMIT = int(os.environ.get("ARIA_RATE_LIMIT_LOGINS_PER_15_MIN", "10"))
_MAX_TRACKED = int(os.environ.get("ARIA_RATE_LIMIT_MAX_CLIENTS", "10000"))
# Trust X-Forwarded-For / X-Real-IP (set when running behind the provided nginx)
_TRUST_PROXY = os.environ.get("ARIA_TRUST_PROXY", "").lower() in ("true", "1", "yes")

_run_windows: "OrderedDict[str, deque]" = OrderedDict()   # client → timestamps of run starts
_req_windows: "OrderedDict[str, deque]" = OrderedDict()   # client → timestamps of all requests
_login_windows: "OrderedDict[str, deque]" = OrderedDict() # client → login attempts
_lock: _asyncio.Lock | None = None


def _get_lock() -> _asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = _asyncio.Lock()
    return _lock

# Paths exempt from request rate limiting (health checks, polling is fine)
_RATE_EXEMPT = {"/api/health", "/"}


def _client_identity(request: Request) -> str:
    """Stable identity for the caller: real client IP where possible."""
    if _TRUST_PROXY:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP", "")
        if real_ip:
            return real_ip
    return request.client.host if request.client else "unknown"


def _window(windows: "OrderedDict[str, deque]", key: str) -> deque:
    """Fetch/create a window with LRU bookkeeping and a hard size cap."""
    win = windows.get(key)
    if win is None:
        win = deque()
        windows[key] = win
    else:
        windows.move_to_end(key)
    while len(windows) > _MAX_TRACKED:
        windows.popitem(last=False)  # evict least-recently-seen client
    return win


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

        client = _client_identity(request)

        now = time.monotonic()
        async with _get_lock():
            # 1. General request rate per client per minute
            req_w = _window(_req_windows, client)
            _sliding_count(req_w, 60)
            if len(req_w) >= _REQ_LIMIT:
                return JSONResponse(
                    {"detail": f"Rate limit exceeded. Max {_REQ_LIMIT} requests/minute."},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            req_w.append(now)

            # Login attempts have a much smaller window than ordinary API
            # traffic, limiting credential stuffing without slowing research.
            if request.method == "POST" and path == "/api/auth/login":
                login_w = _window(_login_windows, client)
                _sliding_count(login_w, 900)
                if len(login_w) >= _LOGIN_LIMIT:
                    return JSONResponse(
                        {"detail": "Too many sign-in attempts. Try again in 15 minutes."},
                        status_code=429,
                        headers={"Retry-After": "900"},
                    )
                login_w.append(now)

            # 2. Run creation rate per client per hour (POST /api/runs only)
            if request.method == "POST" and path == "/api/runs":
                run_w = _window(_run_windows, client)
                _sliding_count(run_w, 3600)
                if len(run_w) >= _RUN_LIMIT:
                    return JSONResponse(
                        {"detail": f"Run rate limit exceeded. Max {_RUN_LIMIT} new runs/hour."},
                        status_code=429,
                        headers={"Retry-After": "3600"},
                    )
                run_w.append(now)

        return await call_next(request)
