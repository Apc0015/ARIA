"""Export endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from aria.api.run_manager import RunManager

router = APIRouter()


async def get_run_manager(request: Request) -> RunManager:
    return request.app.state.run_manager


def _require_run(run_id: str, run_manager: RunManager):
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run_manager.runs[run_id]


@router.get("/api/runs/{run_id}/export/raw")
async def export_raw(run_id: str, run_manager: RunManager = Depends(get_run_manager)):
    """Get raw export info for a run."""
    state = _require_run(run_id, run_manager)
    raw_path = state.exports.get("raw_json") or state.exports.get("raw")
    return {
        "run_id": run_id,
        "format": "raw_json",
        "path": raw_path,
        "download_url": f"/api/runs/{run_id}/download/{Path(raw_path).name}" if raw_path else None,
    }


@router.get("/api/runs/{run_id}/export/clean/json")
async def export_clean_json(run_id: str, run_manager: RunManager = Depends(get_run_manager)):
    """Get clean JSON export info for a run."""
    state = _require_run(run_id, run_manager)
    path = state.exports.get("clean_json") or state.exports.get("clean")
    return {
        "run_id": run_id,
        "format": "clean_json",
        "path": path,
        "download_url": f"/api/runs/{run_id}/download/{Path(path).name}" if path else None,
    }


@router.get("/api/runs/{run_id}/export/clean/csv")
async def export_clean_csv(run_id: str, run_manager: RunManager = Depends(get_run_manager)):
    """Get clean CSV export info for a run."""
    state = _require_run(run_id, run_manager)
    path = state.exports.get("clean_csv") or state.exports.get("csv")
    return {
        "run_id": run_id,
        "format": "clean_csv",
        "path": path,
        "download_url": f"/api/runs/{run_id}/download/{Path(path).name}" if path else None,
    }


@router.get("/api/runs/{run_id}/export/markdown")
async def export_markdown(run_id: str, run_manager: RunManager = Depends(get_run_manager)):
    """Get markdown export info for a run."""
    state = _require_run(run_id, run_manager)
    path = state.exports.get("markdown") or state.report_path or None
    return {
        "run_id": run_id,
        "format": "markdown",
        "path": path,
        "download_url": f"/api/runs/{run_id}/download/{Path(path).name}" if path else None,
    }


@router.get("/api/runs/{run_id}/download/{filename}")
async def download_file(
    run_id: str,
    filename: str,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Serve an export file for download."""
    state = _require_run(run_id, run_manager)
    output_dir = Path(state.output_dir)

    # Search for the file in the output dir and its subdirectories
    candidates = list(output_dir.rglob(filename))
    if not candidates:
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found for run '{run_id}'")

    file_path = candidates[0]
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{filename}' is not a regular file")

    return FileResponse(path=str(file_path), filename=filename)
