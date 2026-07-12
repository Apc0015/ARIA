"""Simple static API key authentication for ARIA API routes."""
from __future__ import annotations

import os
import secrets
import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("aria")

# Read from env; if missing, auth can be explicitly disabled.
_API_KEY: str = os.environ.get("ARIA_API_KEY", "")
_REQUIRE_KEY_RAW = os.environ.get("ARIA_API_KEY_REQUIRED")
if _REQUIRE_KEY_RAW is None:
    _REQUIRE_KEY_RAW = "true" if _API_KEY else "false"
_REQUIRE_KEY = _REQUIRE_KEY_RAW.lower() in ("true", "1", "yes")

if _REQUIRE_KEY and not _API_KEY:
    raise RuntimeError(
        "ARIA_API_KEY_REQUIRED is true but ARIA_API_KEY is not set. "
        "Set ARIA_API_KEY or disable auth with ARIA_API_KEY_REQUIRED=false."
    )

if not _REQUIRE_KEY:
    logger.warning("API key auth disabled (ARIA_API_KEY_REQUIRED=false)")

# Paths exempt from auth (health check, static assets, CORS preflight)
_PUBLIC_PREFIXES = ("/assets", "/favicon")
_PUBLIC_EXACT = {"/api/health", "/", ""}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Rejects requests without a valid X-API-Key or Authorization: Bearer header."""

    async def dispatch(self, request: Request, call_next):
        # Always allow CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # Exempt public paths
        if not path.startswith("/api/"):
            return await call_next(request)
        if path in _PUBLIC_EXACT:
            return await call_next(request)
        if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        if not _REQUIRE_KEY:
            return await call_next(request)

        # Extract key from X-API-Key header first, then Authorization: Bearer
        x_key = request.headers.get("X-API-Key", "")
        auth_header = request.headers.get("Authorization", "")
        bearer = (
            auth_header[len("Bearer "):].strip()
            if auth_header.startswith("Bearer ")
            else ""
        )
        provided = x_key or bearer

        if not provided:
            return JSONResponse(
                {"detail": "Missing API key. Provide X-API-Key header."},
                status_code=401,
            )

        if not secrets.compare_digest(provided.encode(), _API_KEY.encode()):
            return JSONResponse(
                {"detail": "Invalid API key."},
                status_code=401,
            )

        return await call_next(request)
