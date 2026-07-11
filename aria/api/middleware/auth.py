"""Simple static API key authentication for ARIA API routes."""
from __future__ import annotations

import os
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Read from env; if not set, generate a random key at startup and print it.
_API_KEY: str = os.environ.get("ARIA_API_KEY", "")
if not _API_KEY:
    _API_KEY = secrets.token_urlsafe(32)
    print(
        f"\n⚠️  ARIA_API_KEY not set. Using ephemeral key (changes on every restart):\n"
        f"   ARIA_API_KEY={_API_KEY}\n"
        f"   Set this in your .env file to keep it stable.\n"
    )

# Paths exempt from auth (health check, static assets, CORS preflight)
_PUBLIC_PREFIXES = ("/assets", "/favicon")
_PUBLIC_EXACT = {"/api/health", "/api/auth/key", "/", ""}


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
