"""FastAPI application for ARIA Studio."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_STUDIO_DIR = Path(__file__).parent.parent / "studio"

# ---------------------------------------------------------------------------
# Attempt to load the real backend (requires aria.engine to be installed).
# Fall back to a lightweight demo mode if the dependency is absent.
# ---------------------------------------------------------------------------
from aria.api.routes.studio import router as studio_router

try:
    from aria.api.run_manager import RunManager
    from aria.api.routes import (
        credentials_router,
        director_router,
        exports_router,
        flutter_router,
        health_router,
        missions_router,
        runs_router,
        domains_router,
        chat_router,
    )
    USE_REAL_BACKEND = True
except ImportError:
    USE_REAL_BACKEND = False

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ARIA Studio API",
    version="5.0.0",
    description="Agentic Research Intelligence Architecture",
)

import os as _os

_ALLOWED_ORIGINS = _os.environ.get(
    "ARIA_ALLOWED_ORIGINS",
    "http://localhost:8765,http://127.0.0.1:8765,http://localhost:3000,http://localhost:4200",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    allow_credentials=False,
)

from aria.api.middleware.auth import ApiKeyMiddleware
app.add_middleware(ApiKeyMiddleware)

from aria.api.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# ---------------------------------------------------------------------------
# Real backend – register RunManager and all routers
# ---------------------------------------------------------------------------

if USE_REAL_BACKEND:
    run_manager = RunManager()
    app.state.run_manager = run_manager

    app.include_router(health_router)
    app.include_router(studio_router)    # Studio web UI adapter (normalized shapes)
    app.include_router(flutter_router)   # Flutter-specific endpoints (overrides must come before generic ones)
    app.include_router(runs_router)
    app.include_router(exports_router)
    app.include_router(credentials_router)
    app.include_router(missions_router)
    app.include_router(domains_router)   # ARIA 5.0: domain/country discovery + analysis
    app.include_router(chat_router)      # ARIA 5.0: intent agent streaming chat
    app.include_router(director_router)  # Research Director: pre-flight conversation

# ---------------------------------------------------------------------------
# Demo / fallback routes (only active when aria.engine is not available)
# ---------------------------------------------------------------------------

else:
    from uuid import uuid4

    _demo_runs: dict = {}

    DEMO_PROVIDERS = {
        "openrouter": ["openai/gpt-4.5-turbo", "openai/gpt-4o-mini"],
        "openai": ["gpt-4o", "gpt-4o-mini"],
        "anthropic": ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
        "ollama": ["llama3.1:8b", "mistral:latest"],
    }

    FREE_SOURCES = [
        "web_search", "pdf", "arxiv", "pubmed", "semantic_scholar",
        "youtube", "reddit", "hackernews", "wikipedia", "stackoverflow",
        "medium", "devto", "substack", "rss", "user_urls",
    ]

    AUTH_SOURCES = ["twitter", "linkedin", "notion", "slack", "vimeo", "podcast", "zotero"]

    CONTENT_TYPES = [
        "academic_paper", "news_article", "forum_post", "social_media",
        "technical_doc", "video_transcript", "encyclopedia", "opinion_essay",
        "gov_policy", "data_report",
    ]

    @app.get("/api/health")
    async def _demo_health():
        return {
            "status": "ok",
            "version": "5.0.0",
            "mode": "demo",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/api/info")
    async def _demo_info():
        return {
            "name": "ARIA",
            "title": "Agentic Research Intelligence Architecture",
            "version": "5.0.0",
            "mode": "demo",
            "description": "Fully automated research collection and intelligence platform",
            "agents": {"total": 22, "web": 15, "academic": 3, "media": 3},
            "features": [
                "Query expansion (1 topic -> 5-8 queries)",
                "Parallel collection (22+ agents)",
                "LLM ensemble (OpenRouter, OpenAI, Anthropic, Ollama)",
                "Smart content detection (10 types)",
                "Multi-format export (6 formats)",
                "Relevance scoring (0-1)",
            ],
            "llm_providers": list(DEMO_PROVIDERS.keys()),
            "content_types": CONTENT_TYPES,
            "export_formats": ["json", "csv", "markdown", "html"],
        }

    @app.get("/api/sources/free")
    async def _demo_free_sources():
        return {"sources": FREE_SOURCES, "count": len(FREE_SOURCES), "requires_auth": False}

    @app.get("/api/sources/authenticated")
    async def _demo_auth_sources():
        return {"sources": AUTH_SOURCES, "count": len(AUTH_SOURCES), "requires_auth": True}

    @app.get("/api/sources/all")
    async def _demo_all_sources():
        return {"free": FREE_SOURCES, "authenticated": AUTH_SOURCES, "total": len(FREE_SOURCES) + len(AUTH_SOURCES)}

    @app.get("/api/llm/providers")
    async def _demo_llm_providers():
        return {
            "providers": list(DEMO_PROVIDERS.keys()),
            "cloud": ["openrouter", "openai", "anthropic"],
            "local": ["ollama"],
            "details": DEMO_PROVIDERS,
        }

    @app.get("/api/llm/models/{provider}")
    async def _demo_llm_models(provider: str):
        if provider not in DEMO_PROVIDERS:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Unknown provider: '{provider}'")
        return {"provider": provider, "models": DEMO_PROVIDERS[provider]}

    @app.post("/api/runs")
    async def _demo_start_run(payload: dict):
        run_id = str(uuid4())[:8]
        _demo_runs[run_id] = {
            "id": run_id,
            "status": "running",
            "topic": payload.get("topic", "Demo topic"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "progress": 0,
            "documents_collected": 0,
        }
        return {"run_id": run_id, "status": "started", "message": f"Started demo run {run_id}"}

    @app.get("/api/runs")
    async def _demo_list_runs():
        return {"runs": list(_demo_runs.values()), "total": len(_demo_runs)}

    @app.get("/api/runs/{run_id}")
    async def _demo_get_run(run_id: str):
        from fastapi import HTTPException
        if run_id not in _demo_runs:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        run = _demo_runs[run_id]
        if run["status"] == "running":
            run["progress"] = min(run["progress"] + 10, 95)
            run["documents_collected"] = int(100 * run["progress"] / 100)
            if run["progress"] >= 95:
                run["status"] = "completed"
                run["progress"] = 100
                run["documents_collected"] = 247
        return run

    @app.get("/api/runs/{run_id}/documents")
    async def _demo_run_docs(run_id: str):
        from fastapi import HTTPException
        if run_id not in _demo_runs:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        return {
            "run_id": run_id,
            "documents": [
                {"title": "Sample Research Document", "url": "https://example.com/doc1",
                 "source": "web_search", "content_type": "news_article", "relevance_score": 0.89},
            ],
            "total_available": 247,
        }

    @app.get("/api/credentials")
    async def _demo_get_credentials():
        return {"saved": False, "message": "Credentials not configured (demo mode)"}

    @app.post("/api/credentials")
    async def _demo_save_credentials(payload: dict):
        return {"status": "saved", "message": "Credentials saved (demo mode)"}

    @app.get("/api/missions/templates")
    async def _demo_templates():
        return {"templates": [], "total": 0}

    @app.post("/api/missions/validate")
    async def _demo_validate(payload: dict):
        return {"valid": True, "mission": {}, "note": "demo mode - validation skipped"}

    # Studio adapter works in demo mode too (no RunManager dependency)
    app.include_router(studio_router)

# ---------------------------------------------------------------------------
# Root endpoint (always present)
# ---------------------------------------------------------------------------

@app.get("/studio", include_in_schema=False)
@app.get("/studio/", include_in_schema=False)
async def studio():
    """Studio UI — redirects to Flutter app (use aria_studio Flutter app)."""
    if _STUDIO_DIR.exists():
        return FileResponse(_STUDIO_DIR / "index.html")
    from fastapi.responses import JSONResponse
    return JSONResponse({
        "message": "ARIA Studio UI has moved to the Flutter desktop app",
        "version": "5.0.0",
        "flutter_app": "Run: cd aria_studio && flutter run",
        "api_docs": "/docs",
    })

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "ARIA Studio API",
        "version": "5.0.0",
        "backend": "real" if USE_REAL_BACKEND else "demo",
        "docs": "/docs",
        "studio": "/studio",
        "health": "/api/health",
    }


# Mount studio static assets (must come after all API routes)
if _STUDIO_DIR.exists():
    app.mount("/studio", StaticFiles(directory=str(_STUDIO_DIR), html=True), name="studio")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
