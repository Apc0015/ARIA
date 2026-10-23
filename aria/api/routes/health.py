"""Health and info endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from aria import __version__

from aria.engine.ensemble.providers import STATIC_MODEL_CATALOG as PROVIDERS
from aria.engine.orchestrator.collection import _COLLECTOR_REGISTRY

router = APIRouter()

_TRUTHY = {"true", "1", "yes"}

CONTENT_TYPES = [
    "academic_paper", "news_article", "forum_post", "social_media",
    "technical_doc", "video_transcript", "encyclopedia", "opinion_essay",
    "gov_policy", "data_report",
]


@router.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/health/ready")
async def readiness(request: Request):
    """Report whether this instance can safely accept managed-SaaS traffic."""
    checks: dict[str, bool] = {}
    managed_saas = os.getenv("ARIA_SAAS_MODE", "true").lower() in _TRUTHY
    checks["credential_encryption"] = not managed_saas or bool(
        os.getenv("ARIA_CREDENTIALS_KEY")
    )

    tenant_store = getattr(request.app.state, "tenant_store", None)
    checks["tenant_store"] = bool(tenant_store and tenant_store.healthcheck())

    run_manager = getattr(request.app.state, "run_manager", None)
    checks["run_manager"] = run_manager is not None
    runs_dir = Path(run_manager.base_settings.runs_dir) if run_manager else None
    try:
        if runs_dir:
            runs_dir.mkdir(parents=True, exist_ok=True)
            checks["run_storage"] = os.access(runs_dir, os.W_OK)
        else:
            checks["run_storage"] = False
    except OSError:
        checks["run_storage"] = False

    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis

            client = redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
            checks["redis"] = bool(client.ping())
        except Exception:
            checks["redis"] = False

    ready = all(checks.values())
    return JSONResponse(
        {"status": "ready" if ready else "not_ready", "checks": checks},
        status_code=200 if ready else 503,
    )


@router.get("/api/info")
async def info():
    """Platform information."""
    return {
        "name": "ARIA",
        "title": "Agentic Research Intelligence Architecture",
        "version": __version__,
        "description": "Evidence-first research workspace for trusted-source collection and review.",
        "registered_sources": len(_COLLECTOR_REGISTRY),
        "features": [
            "Research brief and trusted-source selection",
            "Live per-source collection status and captured evidence",
            "Human-approved findings linked to source documents",
            "JSON, CSV, Markdown, HTML, and bundled exports",
            "Full research requires a connected tenant AI provider",
            "Collection-only runs preserve raw evidence without an AI provider",
        ],
        "llm_providers": list(PROVIDERS.keys()),
        "content_types": CONTENT_TYPES,
        "export_formats": ["json", "csv", "markdown", "html"],
    }
