"""Mission template and LLM provider endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from aria.api.run_manager import RunManager

router = APIRouter()


async def get_run_manager(request: Request) -> RunManager:
    return request.app.state.run_manager


@router.get("/api/missions/templates")
async def list_templates(run_manager: RunManager = Depends(get_run_manager)):
    """List available mission templates."""
    templates = run_manager.list_templates()
    return {"templates": templates, "total": len(templates)}


@router.post("/api/missions/validate")
async def validate_mission(payload: dict, run_manager: RunManager = Depends(get_run_manager)):
    """Validate mission YAML."""
    mission_yaml = payload.get("mission_yaml", "")
    if not mission_yaml:
        raise HTTPException(status_code=422, detail="mission_yaml is required")
    try:
        result = run_manager.validate_mission(mission_yaml)
        return {"valid": True, "mission": result}
    except Exception as exc:
        return {"valid": False, "error": str(exc)}


@router.get("/api/llm/providers")
async def get_llm_providers(run_manager: RunManager = Depends(get_run_manager)):
    """Get available LLM providers and their catalog."""
    return run_manager.get_llm_sources()


@router.get("/api/llm/models/{provider}")
async def get_llm_models(provider: str, run_manager: RunManager = Depends(get_run_manager)):
    """Get available models for a specific provider."""
    sources = run_manager.get_llm_sources()
    providers_catalog = sources.get("providers", {})
    if provider not in providers_catalog:
        raise HTTPException(status_code=404, detail=f"Unknown provider: '{provider}'")
    return {
        "provider": provider,
        "models": providers_catalog[provider],
    }
