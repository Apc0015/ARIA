"""Tenant-owned source selection settings."""

from fastapi import APIRouter, HTTPException, Request

from aria.api.authorization import current_user, require_role

router = APIRouter()
_KEY = "enabled_sources"


@router.get("/api/source-settings")
async def get_source_settings(request: Request):
    user = current_user(request)
    return {"enabled_sources": request.app.state.tenant_store.get_setting(user["tenant_id"], _KEY, {})}


@router.put("/api/source-settings")
async def save_source_settings(payload: dict, request: Request):
    user = require_role(request, "admin", "member")
    enabled_sources = payload.get("enabled_sources", {})
    if not isinstance(enabled_sources, dict) or not all(isinstance(key, str) and isinstance(value, bool) for key, value in enabled_sources.items()):
        raise HTTPException(status_code=422, detail="enabled_sources must map source IDs to booleans")
    request.app.state.tenant_store.set_setting(user["tenant_id"], _KEY, enabled_sources)
    return {"enabled_sources": enabled_sources}
