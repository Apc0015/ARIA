"""Tenant-scoped organization membership administration."""

from fastapi import APIRouter, HTTPException, Request

from aria.api.authorization import current_user

router = APIRouter()


def _require_admin(request: Request) -> dict:
    user = current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Organization administrator role required")
    return user


@router.get("/api/organization/users")
async def list_users(request: Request):
    user = _require_admin(request)
    return {"users": request.app.state.tenant_store.list_users(user["tenant_id"])}


@router.post("/api/organization/users")
async def create_user(payload: dict, request: Request):
    admin = _require_admin(request)
    try:
        user = request.app.state.tenant_store.create_user(admin["tenant_id"], str(payload.get("email", "")), str(payload.get("password", "")), str(payload.get("role", "member")))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    request.app.state.tenant_store.audit(admin["tenant_id"], admin["id"], "organization.user_created", {"user_id": user["id"], "role": user["role"]})
    return {"user": user}


@router.patch("/api/organization/users/{user_id}")
async def update_user(user_id: str, payload: dict, request: Request):
    admin = _require_admin(request)
    try:
        user = request.app.state.tenant_store.update_user(admin["tenant_id"], user_id, role=payload.get("role"), disabled=payload.get("disabled"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    request.app.state.tenant_store.audit(admin["tenant_id"], admin["id"], "organization.user_updated", {"user_id": user_id})
    return {"user": user}


@router.post("/api/organization/users/{user_id}/reset-password")
async def reset_user_password(user_id: str, payload: dict, request: Request):
    """Allow an organization admin to issue a replacement member password."""
    admin = _require_admin(request)
    try:
        user = request.app.state.tenant_store.reset_user_password(
            admin["tenant_id"], user_id, str(payload.get("new_password", ""))
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    request.app.state.tenant_store.audit(
        admin["tenant_id"], admin["id"], "organization.password_reset", {"user_id": user_id}
    )
    return {"user": user}


@router.get("/api/organization/audit-events")
async def list_audit_events(request: Request):
    admin = _require_admin(request)
    return {"events": request.app.state.tenant_store.list_audit_events(admin["tenant_id"])}
