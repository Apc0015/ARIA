"""Central request authorization helpers for tenant-scoped API resources."""

from __future__ import annotations

from fastapi import HTTPException, Request


def current_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_run_tenant(request: Request, run_manager, run_id: str):
    """Return a run only when it belongs to the caller's tenant.

    A foreign run deliberately returns 404, avoiding confirmation that another
    tenant's run identifier exists.
    """
    user = current_user(request)
    state = run_manager.runs.get(run_id)
    if not state or state.tenant_id != user["tenant_id"]:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return state


def require_role(request: Request, *allowed_roles: str) -> dict:
    user = current_user(request)
    if user.get("role") not in allowed_roles:
        raise HTTPException(status_code=403, detail="Your organization role cannot perform this action")
    return user
