"""Run management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from aria.api.run_manager import RunManager, clean_topic as _clean_topic, run_progress
from aria.api.authorization import require_role, require_run_tenant

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
        "output": {"formats": ["json", "csv", "markdown", "html", "zip"]},
    }
    seed = (payload.get("seed_doi") or payload.get("seed_url") or "").strip()
    if seed:
        from aria.api.routes.seed import parse_seed_input

        seed_doi, seed_url = parse_seed_input(seed)
        mission_dict["citation_crawl"] = {
            "enabled": True,
            "seed_doi": seed_doi,
            "seed_url": seed_url,
            "levels": 1,
            "resolve_abstracts": True,
            "fetch_open_access": True,
            "max_refs": max(1, min(int(payload.get("max_refs", 100)), 500)),
        }
    return yaml.dump(mission_dict, allow_unicode=True)


@router.post("/api/runs")
async def start_run(payload: dict, request: Request, run_manager: RunManager = Depends(get_run_manager)):
    """Start a new research run.

    Accepts either:
    - React UI format:  {topic, intent, depth_level, free_sources, ...}
    - Direct format:     {mission_yaml: "..."}

    Optional: include director_session_id to wire in the Research Director brief.
    """
    # Starting research consumes organization resources; viewers are read-only.
    require_role(request, "admin", "member")
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
        user = require_role(request, "admin", "member")
        if session and (session.tenant_id != user["tenant_id"] or session.user_id != user["id"]):
            raise HTTPException(status_code=404, detail=f"Session '{director_session_id}' not found")
        if session and session.done and session.brief:
            research_brief = session.brief
            # Override topic from resolved brief if topic not in payload
            if "topic" not in payload and research_brief.get("resolved_topic"):
                payload = dict(payload)
                payload["topic"] = research_brief["resolved_topic"]

    # Convert UI payload to mission_yaml if needed
    if "mission_yaml" not in payload and "topic" in payload:
        try:
            mission_yaml = _ui_payload_to_mission_yaml(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        payload = {
            "mission_yaml": mission_yaml,
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
        user = require_role(request, "admin", "member")
        state = await run_manager.start_run(payload, tenant_id=user.get("tenant_id", "local"), user_id=user.get("id", "local"))
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "run_id": state.run_id,
        "status": state.status,
        "stage": state.stage,
        "message": state.message,
        "created_at": state.created_at,
    }


@router.get("/api/runs")
async def list_runs(request: Request, run_manager: RunManager = Depends(get_run_manager)):
    """List all runs."""
    runs = []
    tenant_id = getattr(request.state, "user", {}).get("tenant_id", "local")
    for run_id, state in run_manager.runs.items():
        if state.tenant_id and state.tenant_id != tenant_id:
            continue
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
                "progress": run_progress(state),
            }
        )
    return {"runs": runs, "total": len(runs)}


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)):
    """Get run status and details."""
    require_run_tenant(request, run_manager, run_id)
    return await run_manager.get_run(run_id)


@router.post("/api/runs/{run_id}/restart")
async def restart_run(run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)):
    """Start a new tenant-owned run from an interrupted run's saved mission."""
    previous = require_run_tenant(request, run_manager, run_id)
    user = require_role(request, "admin", "member")
    if previous.status != "interrupted":
        raise HTTPException(status_code=409, detail="Only interrupted runs can be restarted")
    import yaml
    # Preserve the original non-secret behavior contract. Restarting a
    # collection-only job must not unexpectedly require an AI provider.
    flags = dict(previous.flags or {})
    if previous.workflow == "collection_only":
        flags["collect_only"] = True
    payload = {
        "mission_yaml": yaml.safe_dump(previous.mission or {}),
        "flags": flags,
    }
    state = await run_manager.start_run(payload, tenant_id=user["tenant_id"], user_id=user["id"])
    return {"run_id": state.run_id, "restarted_from": run_id, "status": state.status}


@router.get("/api/runs/{run_id}/documents")
async def get_run_documents(
    run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)
):
    """Get document preview for a run (first 100 documents)."""
    state = require_run_tenant(request, run_manager, run_id)
    documents = [_normalize_document(doc) for doc in state.documents[:100]]
    return {
        "run_id": run_id,
        "documents": documents,
        "total": len(state.documents),
    }


@router.get("/api/runs/{run_id}/documents/raw")
async def get_run_raw_documents(
    run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)
):
    """Get raw documents for a run."""
    state = require_run_tenant(request, run_manager, run_id)
    return {
        "run_id": run_id,
        "documents": state.raw_documents[:100],
        "total": len(state.raw_documents),
    }


@router.get("/api/runs/{run_id}/evidence/{document_index}")
async def get_document_evidence(
    run_id: str,
    document_index: int,
    request: Request,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Return the cleaned record and captured source material for review."""
    state = require_run_tenant(request, run_manager, run_id)
    if document_index < 0 or document_index >= len(state.documents):
        raise HTTPException(status_code=404, detail="Document not found")

    clean = state.documents[document_index]
    identifier = clean.get("id") or clean.get("url")
    raw = next(
        (
            document
            for document in state.raw_documents
            if (document.get("id") or document.get("url")) == identifier
        ),
        {},
    )
    raw_text = raw.get("text") or raw.get("content") or raw.get("text_english") or ""
    claims = clean.get("claims") or clean.get("extracted_claims") or []
    rationale = clean.get("scoring_rationale") or clean.get("relevance_rationale") or ""
    return {
        "run_id": run_id,
        "document_index": document_index,
        "clean_document": _normalize_document(clean),
        "raw_document": raw,
        "raw_text": raw_text,
        "claims": claims if isinstance(claims, list) else [claims],
        "scoring_rationale": rationale,
        "source_metadata": {
            "source": raw.get("source") or raw.get("platform") or clean.get("source"),
            "url": raw.get("url") or clean.get("url"),
            "published_at": raw.get("published_at") or clean.get("published_at"),
            "author": raw.get("author") or clean.get("author"),
            "collector_output": raw.get("metadata", {}),
        },
    }


@router.get("/api/runs/{run_id}/documents/ensemble")
async def get_run_ensemble_documents(
    run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)
):
    """Get LLM ensemble documents for a run."""
    state = require_run_tenant(request, run_manager, run_id)
    return {
        "run_id": run_id,
        "documents": state.ensemble_documents,
        "total": len(state.ensemble_documents),
    }


@router.get("/api/runs/{run_id}/intelligence")
async def get_run_intelligence(
    run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)
):
    """Return the run's generated graph, gaps, contradictions, and images."""
    state = require_run_tenant(request, run_manager, run_id)
    graph = state.knowledge_graph or {}
    return {
        "run_id": run_id,
        "knowledge_graph": graph,
        "gap_analysis": state.gap_analysis or {},
        "contradictions": graph.get("contradictions", []),
        "images": state.images or [],
    }


@router.get("/api/runs/{run_id}/findings")
async def get_approved_findings(
    run_id: str, request: Request, run_manager: RunManager = Depends(get_run_manager)
):
    state = require_run_tenant(request, run_manager, run_id)
    return {"run_id": run_id, "findings": state.approved_findings}


@router.post("/api/runs/{run_id}/findings")
async def approve_finding(
    run_id: str, payload: dict, request: Request, run_manager: RunManager = Depends(get_run_manager)
):
    """Persist a human-approved conclusion linked to its evidence."""
    state = require_run_tenant(request, run_manager, run_id)
    statement = str(payload.get("statement", "")).strip()
    if not statement:
        raise HTTPException(status_code=422, detail="A finding statement is required")
    user = require_role(request, "admin", "member")
    finding = {
        "id": uuid4().hex,
        "statement": statement[:4000],
        "evidence_document_indexes": [int(index) for index in payload.get("evidence_document_indexes", []) if isinstance(index, int) and 0 <= index < len(state.documents)],
        "notes": str(payload.get("notes", ""))[:4000],
        "approved_by": user["email"],
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    async with run_manager._lock:
        state.approved_findings.append(finding)
        export_dir = Path(state.output_dir) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        findings_path = export_dir / "approved_findings.json"
        findings_path.write_text(json.dumps(state.approved_findings, indent=2), encoding="utf-8")
        state.exports["approved_findings"] = str(findings_path)
        # A finding is a post-run human decision. Refresh the existing archive
        # so the advertised full package always contains that final artifact.
        if "zip" in state.exports:
            from aria.engine.output.exporter import Exporter

            state.exports["zip"] = str(
                Exporter(export_dir).export_zip(
                    {key: path for key, path in state.exports.items() if key != "zip"}
                )
            )
        run_manager._persist_state(state)
    tenant_store = getattr(request.app.state, "tenant_store", None)
    if tenant_store:
        tenant_store.audit(
            user["tenant_id"],
            user["id"],
            "finding.approved",
            {"run_id": run_id, "finding_id": finding["id"]},
        )
    return {"run_id": run_id, "finding": finding}


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
