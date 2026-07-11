"""
React web UI API adapter — normalized endpoints for the ARIA web app.
Registers at /api/studio/* so core /api/* routes are unchanged.
Works in both real-backend mode (RunManager) and demo mode.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/studio")

# In-memory credential store (web UI only, not persisted to .env)
_studio_creds: list[dict] = []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts(iso: str | None) -> int:
    """ISO 8601 → Unix milliseconds."""
    if not iso:
        return int(time.time() * 1000)
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return int(time.time() * 1000)


def _normalize_run(state: Any) -> dict:
    """RunState dataclass or demo dict → studio frontend shape."""
    if hasattr(state, "run_id"):
        stats = state.stats or {}
        mission = state.mission or {}
        col = mission.get("collection", {}) if isinstance(mission, dict) else {}
        return {
            "id": state.run_id,
            "topic": col.get("topic") or state.message or "Unnamed run",
            "depth": col.get("depth") or "standard",
            "status": state.status,
            "docs": (
                stats.get("docs_collected")
                or stats.get("total_documents")
                or stats.get("documents_collected")
                or len(state.documents)
            ),
            "dedup": stats.get("dedup_ratio") or stats.get("deduplication_ratio") or 0.0,
            "relevance_avg": (
                stats.get("avg_relevance")
                or stats.get("relevance_avg")
                or stats.get("mean_relevance")
                or 0.0
            ),
            "started": _ts(state.created_at),
            "agents_active": stats.get("agents_active") or stats.get("active_agents") or 0,
            "agents_total": 26,
        }
    # Demo dict
    return {
        "id": state.get("id", state.get("run_id", "?")),
        "topic": state.get("topic", "Demo run"),
        "depth": state.get("depth", "standard"),
        "status": state.get("status", "unknown"),
        "docs": state.get("documents_collected", state.get("docs", 0)),
        "dedup": state.get("dedup", 0.0),
        "relevance_avg": state.get("relevance_avg", 0.0),
        "started": _ts(state.get("created_at")),
        "agents_active": state.get("agents_active", 0),
        "agents_total": 26,
    }


def _get_rm(request: Request):
    return getattr(request.app.state, "run_manager", None)


def _get_demo_runs(request: Request) -> dict:
    if not hasattr(request.app.state, "_studio_demo_runs"):
        request.app.state._studio_demo_runs = {}
    return request.app.state._studio_demo_runs


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.post("/auth/login")
async def login(payload: dict):
    """No-op auth — studio just needs a token to pass the client-side gate."""
    email = payload.get("email", "user@aria.dev")
    name = payload.get("name", "ARIA Operator")
    return {
        "token": "aria_web_" + uuid.uuid4().hex[:12],
        "user": {"email": email, "name": name},
    }


# ── Runs ──────────────────────────────────────────────────────────────────────

@router.get("/runs")
async def list_runs(request: Request):
    rm = _get_rm(request)
    if rm:
        return [_normalize_run(s) for s in rm.runs.values()]
    return [_normalize_run(v) for v in _get_demo_runs(request).values()]


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request):
    rm = _get_rm(request)
    if rm:
        if run_id not in rm.runs:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        return _normalize_run(rm.runs[run_id])
    demo = _get_demo_runs(request)
    if run_id not in demo:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    r = demo[run_id]
    if r["status"] == "running":
        r["docs"] = min(r["docs"] + 15, 5000)
        r["agents_active"] = min(r["agents_active"] + 1, 26)
        r["relevance_avg"] = round(min(0.95, 0.60 + r["docs"] / 10000), 2)
        r["dedup"] = round(min(0.90, r["docs"] / 8000), 2)
    return _normalize_run(r)


_DEPTH_MAP = {"surface": 1, "shallow": 1, "standard": 2, "deep": 3, "maximum": 5}
_MAX_DOCS  = {1: 50, 2: 500, 3: 1500, 5: 5000}


@router.post("/runs")
async def start_run(payload: dict, request: Request):
    topic     = payload.get("topic", "Untitled")
    depth_str = payload.get("depth", "standard")
    depth_lvl = _DEPTH_MAP.get(depth_str, 2)
    max_docs  = payload.get("max_documents", _MAX_DOCS.get(depth_lvl, 500))

    rm = _get_rm(request)
    if rm:
        mission_dict = {
            "mission": {"name": f"Research: {topic[:60]}"},
            "collection": {
                "topic": topic,
                "depth": depth_str,
                "max_documents": max_docs,
                "sources": {"enabled": ["web", "academic", "pdf"]},
            },
            "cleaning": {"instructions": topic},
            "output": {"formats": ["json", "markdown"]},
        }
        state = await rm.start_run({"mission_yaml": yaml.dump(mission_dict)})
        return _normalize_run(state)

    run_id = "msn_" + uuid.uuid4().hex[:7]
    now    = datetime.now(timezone.utc).isoformat()
    r = {
        "id": run_id, "topic": topic, "depth": depth_str, "status": "running",
        "docs": 0, "dedup": 0.0, "relevance_avg": 0.0,
        "started": int(time.time() * 1000), "agents_active": 0, "agents_total": 26,
        "created_at": now,
    }
    _get_demo_runs(request)[run_id] = r
    return _normalize_run(r)


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, request: Request):
    rm = _get_rm(request)
    if rm:
        if run_id not in rm.runs:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        rm.runs[run_id].status = "cancelled"
        return _normalize_run(rm.runs[run_id])
    demo = _get_demo_runs(request)
    if run_id not in demo:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    demo[run_id]["status"] = "cancelled"
    return _normalize_run(demo[run_id])


# ── Missions ──────────────────────────────────────────────────────────────────

@router.get("/missions")
async def list_missions(request: Request):
    rm = _get_rm(request)
    if rm:
        templates = rm.list_templates()
        return [
            {
                "id": t["name"],
                "name": t["name"] + ".yaml",
                "topic": t["name"].replace("-", " ").replace("_", " "),
                "depth": "standard",
            }
            for t in templates
        ]
    return [
        {"id": "mis_default",  "name": "default.yaml",       "topic": "general research",  "depth": "standard"},
        {"id": "mis_academic", "name": "academic-deep.yaml",  "topic": "academic research", "depth": "deep"},
        {"id": "mis_news",     "name": "news-pulse.yaml",     "topic": "news tracking",     "depth": "surface"},
    ]


# ── Credentials ───────────────────────────────────────────────────────────────

@router.get("/credentials")
async def list_credentials():
    return _studio_creds


@router.post("/credentials")
async def add_credential(payload: dict):
    c = {
        "id": "cr_" + uuid.uuid4().hex[:6],
        "provider": payload.get("provider", "Unknown"),
        "key_hint": payload.get("key_hint", "***"),
        "status": "active",
        "added": int(time.time() * 1000),
    }
    _studio_creds.append(c)
    return c


@router.delete("/credentials/{cred_id}")
async def delete_credential(cred_id: str):
    global _studio_creds
    _studio_creds = [c for c in _studio_creds if c["id"] != cred_id]
    return {"ok": True}
