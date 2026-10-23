"""Credentials endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from aria.api.run_manager import RunManager
from aria.api.authorization import current_user, require_role

router = APIRouter()


async def get_run_manager(request: Request) -> RunManager:
    return request.app.state.run_manager


@router.get("/api/credentials")
async def get_credentials(request: Request, run_manager: RunManager = Depends(get_run_manager)):
    """Get saved credentials."""
    return run_manager.get_credentials(current_user(request)["tenant_id"])


@router.post("/api/credentials")
async def save_credentials(payload: dict, request: Request, run_manager: RunManager = Depends(get_run_manager)):
    """Save credentials."""
    user = require_role(request, "admin", "member")
    try:
        run_manager.save_credentials(user["tenant_id"], payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    request.app.state.tenant_store.audit(user["tenant_id"], user["id"], "credentials.updated")
    return {"status": "saved"}
