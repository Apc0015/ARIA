"""FastAPI application for ARIA."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from aria import __version__
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REACT_DIST_DIR = _REPO_ROOT / "aria-report" / "dist"

from aria.api.run_manager import RunManager
from aria.api.tenancy import TenantStore
from aria.api.routes import (
    chat_router,
    credentials_router,
    director_router,
    domains_router,
    exports_router,
    health_router,
    missions_router,
    runs_router,
    sources_router,
)
from aria.api.routes.verify import router as verify_router
from aria.api.routes.auth import router as auth_router
from aria.api.routes.organization import router as organization_router
from aria.api.routes.source_settings import router as source_settings_router
from aria.api.routes.seed import router as seed_router

# Kept as a compatibility signal for existing integrations. There is no demo
# implementation: import failures now fail startup instead of serving fake data.
USE_REAL_BACKEND = True

@asynccontextmanager
async def lifespan(application: FastAPI):
    yield
    await application.state.run_manager.shutdown()


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ARIA API",
    version=__version__,
    description="Agentic Research Intelligence Architecture",
    lifespan=lifespan,
)
app.state.tenant_store = TenantStore(_REPO_ROOT / "data" / "aria_saas.db")
app.state.tenant_store.bootstrap_from_env()

import os as _os

_ALLOWED_ORIGINS = _os.environ.get(
    "ARIA_ALLOWED_ORIGINS",
    "http://localhost:8765,http://127.0.0.1:8765,http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:4200",
).split(",")
_ALLOWED_HOSTS = _os.environ.get(
    "ARIA_ALLOWED_HOSTS",
    "localhost,127.0.0.1,testserver,aria-api",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    # The browser session cookie is intentionally accepted for the configured
    # first-party origins. Production must set ARIA_ALLOWED_ORIGINS explicitly.
    allow_credentials=True,
)

# Host header validation prevents forged absolute URLs and password-reset/link
# poisoning when ARIA is deployed behind a reverse proxy.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_ALLOWED_HOSTS)

# Starlette runs the LAST middleware added FIRST. Rate limiting is added
# after auth so it is outermost: request floods (including brute-force key
# guessing) are throttled by client IP before the auth check runs.
from aria.api.middleware.auth import ApiKeyMiddleware
app.add_middleware(ApiKeyMiddleware)

from aria.api.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

run_manager = RunManager()
app.state.run_manager = run_manager

app.include_router(auth_router)
app.include_router(organization_router)
app.include_router(source_settings_router)
app.include_router(health_router)
app.include_router(verify_router)
app.include_router(runs_router)
app.include_router(exports_router)
app.include_router(credentials_router)
app.include_router(missions_router)
app.include_router(domains_router)
app.include_router(chat_router)
app.include_router(director_router)
app.include_router(sources_router)
app.include_router(seed_router)       # Seed paper preview for citation crawl

# ---------------------------------------------------------------------------
# Root endpoint (always present)
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root():
    """Serve the React UI when built; otherwise expose API metadata."""
    index = _REACT_DIST_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {
        "message": "ARIA API",
        "version": __version__,
        "backend": "production",
        "docs": "/docs",
        "ui": "Run React dev server from aria-report or build aria-report/dist",
        "health": "/api/health",
    }


# Mount React static assets and SPA fallback (must come after all API routes).
class _SPAStaticFiles(StaticFiles):
    """Serve index.html for unknown non-API paths (client-side routing).

    Without this, deep links like /settings or /report/<id> 404 on refresh —
    StaticFiles(html=True) only serves index.html for "/".
    """

    async def get_response(self, path: str, scope):
        from starlette.exceptions import HTTPException as StarletteHTTPException

        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # Unknown API endpoints must stay JSON 404s, not become HTML.
            if exc.status_code == 404 and not path.startswith("api"):
                return await super().get_response("index.html", scope)
            raise


if _REACT_DIST_DIR.exists():
    app.mount("/", _SPAStaticFiles(directory=str(_REACT_DIST_DIR), html=True), name="react")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
