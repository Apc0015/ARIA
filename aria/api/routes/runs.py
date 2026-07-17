"""Run management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from aria.api.run_manager import RunManager, clean_topic as _clean_topic

router = APIRouter()


async def get_run_manager(request: Request) -> RunManager:
    return request.app.state.run_manager


def _ui_payload_to_mission_yaml(payload: dict) -> str:
    """Convert React UI payload to a mission YAML string."""
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
        cleaning.get("instructions") or cleaning.get("research_goal") or intent or topic
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
            "depth": depth_names.get(depth_level, "medium"),
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
    - React UI format:  {topic, intent, depth_level, free_sources, ...}
    - Direct format:     {mission_yaml: "..."}

    Optional: include director_session_id to wire in the Research Director brief.
    """
    # Attach research brief from a completed Director session if provided.
    # Direct mission_yaml launches are explicit contracts, so they do not inherit
    # Director phased-source overrides unless a caller opts into merging.
    has_direct_mission = bool(payload.get("mission_yaml"))
    director_session_id = payload.get("director_session_id")
    research_brief: dict | None = None
    merge_director_brief = bool(payload.get("merge_director_brief", False))
    if director_session_id and (not has_direct_mission or merge_director_brief):
        from aria.api.routes.director import _sessions

        session = _sessions.get(director_session_id)
        if session and session.done and session.brief:
            research_brief = session.brief
            # Override topic from resolved brief if topic not in payload
            if "topic" not in payload and research_brief.get("resolved_topic"):
                payload = dict(payload)
                payload["topic"] = research_brief["resolved_topic"]

    # Convert UI payload to mission_yaml if needed
    if "mission_yaml" not in payload and "topic" in payload:
        payload = {
            "mission_yaml": _ui_payload_to_mission_yaml(payload),
            # Preserve fields the orchestrator/run_manager reads from payload
            "flags": payload.get("flags", {}),
            "credentials": payload.get("credentials"),
            "auth_tokens": payload.get("auth_tokens", {}),
            "research_brief": research_brief,
        }
    elif research_brief:
        payload = dict(payload)
        payload["research_brief"] = research_brief

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
        mission = state.mission or {}
        collection = mission.get("collection", {}) if isinstance(mission, dict) else {}
        docs_collected = state.docs_collected or state.stats.get("collected", 0)
        docs_cleaned = state.docs_cleaned or state.stats.get("cleaned", 0)
        runs.append(
            {
                "run_id": state.run_id,
                "status": state.status,
                "stage": state.stage,
                "message": state.message,
                "created_at": state.created_at,
                "updated_at": state.updated_at,
                "error": state.error,
                # A real human topic, or None — never the run-id hash. The UI
                # renders "Untitled run" when this is empty.
                "topic": _clean_topic(
                    collection.get("topic") or state.stats.get("topic"),
                    state.run_id,
                ),
                "sources_used": collection.get("sources", {}).get("enabled", []),
                "total_documents": docs_cleaned
                or docs_collected
                or len(state.documents),
                "progress": (
                    100
                    if state.status == "completed"
                    else (10 if state.status == "running" else 0)
                ),
            }
        )
    return {"runs": runs, "total": len(runs)}


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str, run_manager: RunManager = Depends(get_run_manager)):
    """Get run status and details."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return await run_manager.get_run(run_id)


@router.get("/api/runs/{run_id}/documents")
async def get_run_documents(
    run_id: str, run_manager: RunManager = Depends(get_run_manager)
):
    """Get document preview for a run (first 100 documents)."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]
    documents = [_normalize_document(doc) for doc in state.documents[:100]]
    return {
        "run_id": run_id,
        "documents": documents,
        "total": len(state.documents),
    }


@router.get("/api/runs/{run_id}/documents/raw")
async def get_run_raw_documents(
    run_id: str, run_manager: RunManager = Depends(get_run_manager)
):
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
async def get_run_ensemble_documents(
    run_id: str, run_manager: RunManager = Depends(get_run_manager)
):
    """Get LLM ensemble documents for a run."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]
    return {
        "run_id": run_id,
        "documents": state.ensemble_documents,
        "total": len(state.ensemble_documents),
    }


def _normalize_document(doc: dict) -> dict:
    """Return a React-friendly document preview shape."""
    return {
        **doc,
        "title": doc.get("title") or doc.get("url") or "Untitled document",
        "source": doc.get("source")
        or doc.get("platform")
        or doc.get("source_type")
        or "unknown",
        "summary": doc.get("summary")
        or doc.get("text_english")
        or doc.get("text", "")[:300],
    }
