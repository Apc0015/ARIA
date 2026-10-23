"""Export endpoints."""

from __future__ import annotations

import re as _re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from aria.api.run_manager import RunManager
from aria.api.authorization import require_run_tenant

_SAFE_FILENAME = _re.compile(r'^[\w\-. ]+$')  # alphanum, dash, dot, space, underscore

router = APIRouter()


async def get_run_manager(request: Request) -> RunManager:
    return request.app.state.run_manager


def _require_run(request: Request, run_id: str, run_manager: RunManager):
    return require_run_tenant(request, run_manager, run_id)


@router.get("/api/runs/{run_id}/export/raw")
async def export_raw(run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)):
    """Get raw export info for a run."""
    state = _require_run(request, run_id, run_manager)
    raw_path = state.exports.get("raw_json") or state.exports.get("raw")
    return {
        "run_id": run_id,
        "format": "raw_json",
        "filename": Path(raw_path).name if raw_path else None,
        "download_url": f"/api/runs/{run_id}/download/{Path(raw_path).name}" if raw_path else None,
    }


@router.get("/api/runs/{run_id}/export/clean/json")
async def export_clean_json(run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)):
    """Get clean JSON export info for a run."""
    state = _require_run(request, run_id, run_manager)
    path = state.exports.get("clean_json") or state.exports.get("clean")
    return {
        "run_id": run_id,
        "format": "clean_json",
        "filename": Path(path).name if path else None,
        "download_url": f"/api/runs/{run_id}/download/{Path(path).name}" if path else None,
    }


@router.get("/api/runs/{run_id}/export/clean/csv")
async def export_clean_csv(run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)):
    """Get clean CSV export info for a run."""
    state = _require_run(request, run_id, run_manager)
    path = state.exports.get("clean_csv") or state.exports.get("csv")
    return {
        "run_id": run_id,
        "format": "clean_csv",
        "filename": Path(path).name if path else None,
        "download_url": f"/api/runs/{run_id}/download/{Path(path).name}" if path else None,
    }


@router.get("/api/runs/{run_id}/export/markdown")
async def export_markdown(run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)):
    """Get markdown export info for a run."""
    state = _require_run(request, run_id, run_manager)
    path = state.exports.get("markdown") or state.report_path or None
    return {
        "run_id": run_id,
        "format": "markdown",
        "filename": Path(path).name if path else None,
        "download_url": f"/api/runs/{run_id}/download/{Path(path).name}" if path else None,
    }


@router.get("/api/runs/{run_id}/export/html")
async def export_html(run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)):
    """Get visual HTML report download info for a run."""
    state = _require_run(request, run_id, run_manager)
    path = state.exports.get("html") or state.report_path or None
    return {
        "run_id": run_id,
        "format": "html",
        "filename": Path(path).name if path else None,
        "download_url": f"/api/runs/{run_id}/download/{Path(path).name}" if path else None,
    }


@router.get("/api/runs/{run_id}/export/zip")
async def export_zip(run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)):
    """Get bundled research archive download info for a run."""
    state = _require_run(request, run_id, run_manager)
    path = state.exports.get("zip")
    return {
        "run_id": run_id,
        "format": "zip",
        "filename": Path(path).name if path else None,
        "download_url": f"/api/runs/{run_id}/download/{Path(path).name}" if path else None,
    }


@router.get("/api/runs/{run_id}/export/findings")
async def export_findings(run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)):
    """Download human-approved findings for a tenant-owned research run."""
    state = _require_run(request, run_id, run_manager)
    path = state.exports.get("approved_findings")
    return {
        "run_id": run_id,
        "format": "approved_findings",
        "filename": Path(path).name if path else None,
        "download_url": f"/api/runs/{run_id}/download/{Path(path).name}" if path else None,
    }


@router.get("/api/runs/{run_id}/download/{filename}")
async def download_file(
    run_id: str,
    filename: str,
    request: Request,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Serve an export file for download (path-traversal safe)."""
    # 1. Validate filename — reject anything with path separators or unusual chars
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    state = _require_run(request, run_id, run_manager)
    output_dir = Path(state.output_dir).resolve()

    # 2. Search for file then verify it's actually inside output_dir
    candidates = list(output_dir.rglob(filename))
    if not candidates:
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found for run '{run_id}'")

    file_path = candidates[0].resolve()

    # 3. Boundary check — a textual prefix is unsafe for sibling names such
    # as ``run`` and ``run-archive`` and for symlinks inside a run directory.
    try:
        file_path.relative_to(output_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"'{filename}' is not a regular file")

    # Full SaaS deployments record downloads. Keep this endpoint usable by
    # embedded/self-hosted API instances that intentionally have no tenant DB.
    tenant_store = getattr(request.app.state, "tenant_store", None)
    user = getattr(request.state, "user", None)
    if tenant_store and user:
        tenant_store.audit(
            user["tenant_id"],
            user["id"],
            "export.downloaded",
            {"run_id": run_id, "filename": filename},
        )
    return FileResponse(path=str(file_path), filename=filename)
