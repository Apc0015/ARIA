"""Run management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from aria.api.run_manager import RunManager

router = APIRouter()


async def get_run_manager(request: Request) -> RunManager:
    return request.app.state.run_manager


def _flutter_payload_to_mission_yaml(payload: dict) -> str:
    """Convert Flutter UI payload to a mission YAML string."""
    import yaml

    topic = payload.get("topic", "")
    intent = payload.get("intent", topic)
    depth_level = int(payload.get("depth_level", 2))
    depth_names = {1: "low", 2: "medium", 3: "high", 4: "high", 5: "exhaustive"}
    max_docs = {1: 50, 2: 200, 3: 500, 4: 1500, 5: 5000}

    free_sources = payload.get("free_sources", {})
    auth_sources = payload.get("auth_sources", {})
    enabled = [s for s, v in {**free_sources, **auth_sources}.items() if v]
    if not enabled:
        enabled = ["web", "pdf", "academic"]

    cleaning = payload.get("cleaning", {})
    instructions = (
        cleaning.get("instructions")
        or cleaning.get("research_goal")
        or intent
        or topic
    )
    schema = cleaning.get("output_schema") or {
        "is_relevant": "bool",
        "relevance_score": "float",
        "title": "string",
        "summary": "string",
        "key_topics": "list",
    }

    ensemble_models = payload.get("ensemble_models", [])

    mission_dict = {
        "mission": {"name": f"Research: {topic[:60]}"},
        "collection": {
            "topic": topic,
            "depth": depth_names.get(depth_level, "standard"),
            "max_documents": max_docs.get(depth_level, 200),
            "max_per_source": 30,
            "sources": {"enabled": enabled},
        },
        "cleaning": {
            "instructions": instructions,
            "output_schema": schema,
        },
        "llm_sources": {
            "enabled": bool(ensemble_models),
            "models": ensemble_models,
        },
        "output": {"formats": ["json", "csv", "markdown"]},
    }
    return yaml.dump(mission_dict, allow_unicode=True)


@router.post("/api/runs")
async def start_run(payload: dict, run_manager: RunManager = Depends(get_run_manager)):
    """Start a new research run.

    Accepts either:
    - Flutter UI format: {topic, intent, depth_level, free_sources, ...}
    - Direct format:     {mission_yaml: "..."}
    """
    # Convert Flutter payload to mission_yaml if needed
    if "mission_yaml" not in payload and "topic" in payload:
        payload = {
            "mission_yaml": _flutter_payload_to_mission_yaml(payload),
            # Preserve fields the orchestrator/run_manager reads from payload
            "flags":       payload.get("flags", {}),
            "credentials": payload.get("credentials"),
            "auth_tokens": payload.get("auth_tokens", {}),
        }

    try:
        state = await run_manager.start_run(payload)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "run_id": state.run_id,
        "status": state.status,
        "stage": state.stage,
        "message": state.message,
        "created_at": state.created_at,
        "output_dir": state.output_dir,
    }


@router.get("/api/runs")
async def list_runs(run_manager: RunManager = Depends(get_run_manager)):
    """List all runs."""
    runs = []
    for run_id, state in run_manager.runs.items():
        runs.append({
            "run_id": state.run_id,
            "status": state.status,
            "stage": state.stage,
            "message": state.message,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
            "error": state.error,
        })
    return {"runs": runs, "total": len(runs)}


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str, run_manager: RunManager = Depends(get_run_manager)):
    """Get run status and details."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return await run_manager.get_run(run_id)


@router.get("/api/runs/{run_id}/documents")
async def get_run_documents(run_id: str, run_manager: RunManager = Depends(get_run_manager)):
    """Get document preview for a run (first 100 documents)."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]
    return {
        "run_id": run_id,
        "documents": state.documents[:100],
        "total": len(state.documents),
    }


@router.get("/api/runs/{run_id}/documents/raw")
async def get_run_raw_documents(run_id: str, run_manager: RunManager = Depends(get_run_manager)):
    """Get raw documents for a run."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]
    return {
        "run_id": run_id,
        "documents": state.raw_documents[:100],
        "total": len(state.raw_documents),
    }


@router.get("/api/runs/{run_id}/documents/ensemble")
async def get_run_ensemble_documents(run_id: str, run_manager: RunManager = Depends(get_run_manager)):
    """Get LLM ensemble documents for a run."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]
    return {
        "run_id": run_id,
        "documents": state.ensemble_documents,
        "total": len(state.ensemble_documents),
    }
