"""Simple static API key authentication for ARIA API routes.

Security model (fail-closed):
- Auth is REQUIRED by default. If ``ARIA_API_KEY`` is not set, a random key
  is generated at startup and printed once to the server log — the API is
  never silently open.
- Local development can opt out explicitly with ``ARIA_API_KEY_REQUIRED=false``
  (``aria --serve-api`` does this automatically when binding a loopback
  interface without a configured key).
"""
from __future__ import annotations

import os
import secrets
import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("aria")

# Paths exempt from auth (health check, static assets, CORS preflight)
_PUBLIC_PREFIXES = ("/assets", "/favicon")
_PUBLIC_EXACT = {"/api/health", "/api/health/ready", "/api/auth/login", "/", ""}

_TRUTHY = ("true", "1", "yes")


def resolve_auth() -> tuple[bool, str]:
    """Resolve (require_key, api_key) from the environment.

    Reads env at call time so tests and the CLI can adjust settings before
    the app (and this middleware) is instantiated.
    """
    api_key = os.environ.get("ARIA_API_KEY", "")
    required_raw = os.environ.get("ARIA_API_KEY_REQUIRED")

    if required_raw is not None:
        required = required_raw.lower() in _TRUTHY
    else:
        required = True  # secure default: never silently open

    if not required:
        logger.warning(
            "API key auth DISABLED (ARIA_API_KEY_REQUIRED=false). "
            "Do not expose this server beyond localhost."
        )
        return False, api_key

    if not api_key:
        api_key = secrets.token_urlsafe(32)
        logger.warning(
            "ARIA_API_KEY is not set — generated a one-session key.\n"
            "    API key: %s\n"
            "    Set ARIA_API_KEY to make it permanent, or "
            "ARIA_API_KEY_REQUIRED=false to disable auth for local dev.",
            api_key,
        )
    return True, api_key


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Rejects requests without a valid X-API-Key or Authorization: Bearer header."""

    def __init__(self, app, require_key: bool | None = None, api_key: str | None = None):
        super().__init__(app)
        if require_key is None or api_key is None:
            resolved_required, resolved_key = resolve_auth()
            require_key = resolved_required if require_key is None else require_key
            api_key = resolved_key if api_key is None else api_key
        self._require_key = require_key
        self._api_key = api_key

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

        tenant_store = getattr(request.app.state, "tenant_store", None)
        session_token = request.cookies.get("aria_session")
        if tenant_store and session_token:
            user = tenant_store.get_session_user(session_token)
            if user:
                request.state.user = user
                return await call_next(request)

        # Managed SaaS customer traffic must use an authenticated server-side
        # session. The legacy shared API key is reserved for non-SaaS/internal
        # deployments and cannot become a cross-tenant customer credential.
        if tenant_store and os.getenv("ARIA_SAAS_MODE", "true").lower() in _TRUTHY:
            return JSONResponse({"detail": "Authentication required."}, status_code=401)

        if not self._require_key:
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

        if not secrets.compare_digest(provided.encode(), self._api_key.encode()):
            return JSONResponse(
                {"detail": "Invalid API key."},
                status_code=401,
            )

        return await call_next(request)
