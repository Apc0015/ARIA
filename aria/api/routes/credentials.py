"""Credentials endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from aria.api.run_manager import RunManager

router = APIRouter()


async def get_run_manager(request: Request) -> RunManager:
    return request.app.state.run_manager


@router.get("/api/credentials")
async def get_credentials(run_manager: RunManager = Depends(get_run_manager)):
    """Get saved credentials."""
    return run_manager.get_credentials()


@router.post("/api/credentials")
async def save_credentials(payload: dict, run_manager: RunManager = Depends(get_run_manager)):
    """Save credentials."""
    path = run_manager.save_credentials(payload)
    return {"status": "saved"}
