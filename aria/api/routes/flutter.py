"""Flutter UI – specific endpoints that map the aria_studio API contract."""

from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from aria.api.run_manager import RunManager

router = APIRouter()

# ─── dependency ────────────────────────────────────────────────────────────

async def get_run_manager(request: Request) -> RunManager:
    return request.app.state.run_manager


# ─── LLM Sources (cleaning brain + provider catalog) ───────────────────────

@router.get("/api/llm-sources")
async def llm_sources(run_manager: RunManager = Depends(get_run_manager)):
    """Return cleaning brain config + provider catalog used by Flutter UI."""
    try:
        base = run_manager.get_llm_sources()
        # Add current brain config
        base["current_brain"] = run_manager.get_brain_config()
        # Add model catalog for each provider
        base["model_catalog"] = {
            "anthropic": ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-haiku-20240307", "claude-3-opus-latest"],
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
            "openrouter": ["openai/gpt-4o", "openai/gpt-4o-mini", "anthropic/claude-3-5-sonnet", "anthropic/claude-3-haiku", "meta-llama/llama-3.1-70b-instruct", "mistralai/mistral-7b-instruct", "google/gemini-flash-1.5"],
            "ollama": [],  # populated from /api/llm/ollama/models
        }
        return base
    except Exception:
        return {"providers": [], "default_models": [], "cleaning_brain": {}, "current_brain": {}, "model_catalog": {}}


# ─── Mission generate / validate aliases ───────────────────────────────────

@router.post("/api/mission/generate")
async def generate_mission(payload: dict):
    """Generate a mission YAML from topic + intent (Flutter shortcut)."""
    topic = payload.get("topic", "")
    intent = payload.get("intent", topic)
    depth_level = int(payload.get("depth_level", 2))
    depth_names = {1: "low", 2: "medium", 3: "high", 4: "high", 5: "exhaustive"}
    depth = depth_names.get(depth_level, "standard")
    max_docs = {1: 50, 2: 200, 3: 500, 4: 1500, 5: 5000}.get(depth_level, 200)

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

    import yaml  # PyYAML
    mission_dict: dict[str, Any] = {
        "mission": {"name": f"Research: {topic[:60]}"},
        "collection": {
            "topic": topic,
            "depth": depth,
            "max_documents": max_docs,
            "max_per_source": 30,
            "sources": {"enabled": enabled},
        },
        "cleaning": {
            "instructions": instructions,
            "output_schema": schema,
        },
        "output": {"formats": ["json", "csv", "markdown"]},
    }
    return {"mission_yaml": yaml.dump(mission_dict, allow_unicode=True)}


@router.post("/api/mission/validate")
async def validate_mission_alias(
    payload: dict,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Alias of /api/missions/validate for Flutter UI."""
    mission_yaml = payload.get("mission_yaml", "")
    if not mission_yaml:
        raise HTTPException(status_code=422, detail="mission_yaml is required")
    try:
        result = run_manager.validate_mission(mission_yaml)
        return {"valid": True, "mission": result}
    except Exception as exc:
        return {"valid": False, "error": str(exc)}


# ─── LLM provider detection ────────────────────────────────────────────────

_PROVIDER_PREFIXES = {
    "sk-ant-": ("anthropic", "Anthropic"),
    "sk-or-":  ("openrouter", "OpenRouter"),
}

_OPENAI_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
_ANTHROPIC_MODELS = [
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
    "claude-3-opus-latest",
]
_OPENROUTER_MODELS = [
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "anthropic/claude-3-5-sonnet",
    "meta-llama/llama-3.1-70b-instruct",
    "mistralai/mistral-7b-instruct",
]


@router.post("/api/llm/detect")
async def detect_llm_provider(payload: dict):
    """Detect LLM provider from an API key prefix / live probe."""
    api_key: str = payload.get("api_key", "").strip()
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key is required")

    # Fast prefix check
    for prefix, (provider, name) in _PROVIDER_PREFIXES.items():
        if api_key.startswith(prefix):
            models = _ANTHROPIC_MODELS if provider == "anthropic" else _OPENROUTER_MODELS
            return {
                "provider": provider,
                "name": name,
                "models": models,
                "base_url": "https://openrouter.ai/api/v1" if provider == "openrouter" else "",
            }

    # Try OpenAI
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code == 200:
            return {
                "provider": "openai",
                "name": "OpenAI",
                "models": _OPENAI_MODELS,
                "base_url": "",
            }
    except Exception:
        pass

    # Unknown but non-empty key → treat as generic OpenAI-compat
    return {
        "provider": "openai",
        "name": "OpenAI (unverified)",
        "models": _OPENAI_MODELS,
        "base_url": "",
    }


# ─── Ollama models ─────────────────────────────────────────────────────────

@router.get("/api/llm/ollama/models")
async def ollama_models():
    """List locally available Ollama models."""
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{base_url}/api/tags")
        if resp.status_code == 200:
            data = resp.json()
            names = [m.get("name", "") for m in data.get("models", [])]
            return {"models": [n for n in names if n], "connected": True}
    except Exception:
        pass
    return {"models": [], "connected": False}


# ─── Brain config endpoints ─────────────────────────────────────────────────

@router.get("/api/llm/brain")
async def get_brain_config(run_manager: RunManager = Depends(get_run_manager)):
    """Return current cleaning brain config."""
    return run_manager.get_brain_config()


@router.post("/api/llm/brain")
async def set_brain_config(payload: dict, run_manager: RunManager = Depends(get_run_manager)):
    """Set cleaning brain: {provider, model_id, api_key, base_url}"""
    required = {"provider", "model_id"}
    if not required.issubset(payload.keys()):
        raise HTTPException(status_code=422, detail=f"Required fields: {required}")
    run_manager.set_brain_config(payload)
    return {"ok": True, "brain": run_manager.get_brain_config()}


@router.get("/api/llm/models/{provider}")
async def list_provider_models(provider: str, api_key: str = ""):
    """Return available models for a cloud provider given an API key.
    Also returns local Ollama models if provider == 'ollama'.
    """
    MODELS_MAP = {
        "anthropic": [
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
            "claude-3-haiku-20240307",
            "claude-3-opus-latest",
        ],
        "openai": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ],
        "openrouter": [
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "anthropic/claude-3-5-sonnet",
            "anthropic/claude-3-haiku",
            "meta-llama/llama-3.1-70b-instruct",
            "mistralai/mistral-7b-instruct",
            "google/gemini-flash-1.5",
            "google/gemini-pro-1.5",
        ],
    }
    if provider == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                names = [m.get("name", "") for m in data.get("models", [])]
                return {"provider": "ollama", "models": [n for n in names if n], "connected": True}
        except Exception:
            pass
        return {"provider": "ollama", "models": [], "connected": False}

    models = MODELS_MAP.get(provider, [])
    return {"provider": provider, "models": models, "connected": bool(api_key)}


# ─── Platform auth (subscription platforms) ────────────────────────────────

_platform_sessions: dict[str, bool] = {}

# Store platform credentials (api_key or username/password)
_platform_credentials: dict[str, dict] = {}


@router.post("/api/platforms/login")
async def platform_login(payload: dict):
    """Authenticate with a platform using real credentials/tokens."""
    platform: str = payload.get("platform", "")
    if not platform:
        raise HTTPException(status_code=422, detail="platform is required")

    # Build credentials dict from payload
    credentials = {
        "username":      payload.get("username", "").strip(),
        "email":         payload.get("email", "").strip(),
        "password":      payload.get("password", "").strip(),
        "api_key":       payload.get("api_key", "").strip(),
        "token":         payload.get("token", "").strip(),
        "client_id":     payload.get("client_id", "").strip(),
        "client_secret": payload.get("client_secret", "").strip(),
        "institution":   payload.get("institution", "").strip(),
        "library_id":    payload.get("library_id", "").strip(),
        "library_type":  payload.get("library_type", "").strip(),
    }
    # Remove empty values
    credentials = {k: v for k, v in credentials.items() if v}

    if not credentials:
        raise HTTPException(status_code=422, detail="At least one credential field is required")

    try:
        from aria.engine.access.session_manager import get_session_manager
        manager = get_session_manager()
        result = await manager.login(platform, credentials)
    except Exception as exc:
        result = {"success": False, "message": str(exc)}

    # Update in-memory session state
    if result.get("success"):
        _platform_sessions[platform] = True
        _platform_credentials[platform] = credentials

    return {
        "platform": platform,
        "connected": result.get("success", False),
        "message": result.get("message", ""),
        "method": result.get("method", ""),
        "cookies_saved": result.get("cookies_saved", False),
        "username": result.get("username", ""),
    }


@router.delete("/api/platforms/{platform_id}/logout")
async def platform_logout(platform_id: str):
    """Clear saved session for a platform."""
    _platform_sessions.pop(platform_id, None)
    _platform_credentials.pop(platform_id, None)
    try:
        from aria.engine.access.session_manager import get_session_manager
        get_session_manager().clear_session(platform_id)
    except Exception:
        pass
    return {"platform": platform_id, "cleared": True}


@router.get("/api/platforms/status")
async def platform_status():
    """Return connection status for all platforms."""
    import os
    try:
        from aria.engine.access.session_manager import get_session_manager
        sm = get_session_manager()
    except Exception:
        sm = None

    all_platforms = [
        {"id": "ieee",               "label": "IEEE Xplore",             "auth_type": "api_key",      "env_var": "IEEE_API_KEY"},
        {"id": "acm",                "label": "ACM Digital Library",     "auth_type": "api_key",      "env_var": "ACM_API_KEY"},
        {"id": "springer",           "label": "Springer",                "auth_type": "api_key",      "env_var": "SPRINGER_API_KEY"},
        {"id": "elsevier",           "label": "Elsevier/ScienceDirect",  "auth_type": "api_key",      "env_var": "ELSEVIER_API_KEY"},
        {"id": "jstor",              "label": "JSTOR",                   "auth_type": "institution",  "env_var": "JSTOR_INSTITUTION"},
        {"id": "twitter",            "label": "Twitter / X",             "auth_type": "token_or_login","env_var": "TWITTER_BEARER_TOKEN"},
        {"id": "reddit",             "label": "Reddit",                  "auth_type": "public_or_api","env_var": "REDDIT_CLIENT_ID"},
        {"id": "linkedin",           "label": "LinkedIn",                "auth_type": "browser_login","env_var": "LINKEDIN_EMAIL"},
        {"id": "medium",             "label": "Medium",                  "auth_type": "browser_login","env_var": ""},
        {"id": "substack",           "label": "Substack",                "auth_type": "browser_login","env_var": ""},
        {"id": "slack",              "label": "Slack",                   "auth_type": "token",        "env_var": "SLACK_TOKEN"},
        {"id": "notion",             "label": "Notion",                  "auth_type": "token",        "env_var": "NOTION_TOKEN"},
        {"id": "vimeo",              "label": "Vimeo",                   "auth_type": "token",        "env_var": "VIMEO_ACCESS_TOKEN"},
        {"id": "university_library", "label": "University Library",      "auth_type": "api_key",      "env_var": "UNIVERSITY_LIBRARY_API_KEY"},
        {"id": "zotero",             "label": "Zotero",                  "auth_type": "api_key",      "env_var": "ZOTERO_API_KEY"},
    ]

    return {
        "platforms": [
            {
                "platform": p["id"],
                "label": p["label"],
                "auth_type": p["auth_type"],
                "connected": (
                    _platform_sessions.get(p["id"], False)
                    or bool(os.getenv(p["env_var"], "") if p["env_var"] else False)
                    or (sm.has_session(p["id"]) if sm else False)
                ),
                "has_credentials": bool(_platform_credentials.get(p["id"])) or bool(os.getenv(p["env_var"], "") if p["env_var"] else False),
                "has_browser_session": sm.has_session(p["id"]) if sm else False,
            }
            for p in all_platforms
        ]
    }


# ─── Export: raw JSON (full document data) ─────────────────────────────────

@router.get("/api/runs/{run_id}/export/raw")
async def export_raw_data(
    run_id: str,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Return ALL raw collected documents as a JSON payload."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]

    # Prefer on-disk file if available
    raw_path = state.exports.get("raw_json") or state.exports.get("raw")
    if raw_path and Path(raw_path).exists():
        docs = _read_jsonl(Path(raw_path))
    else:
        docs = state.raw_documents

    return {"run_id": run_id, "documents": docs, "total": len(docs)}


# ─── Export: clean JSON ─────────────────────────────────────────────────────

@router.get("/api/runs/{run_id}/export/clean")
async def export_clean_data(
    run_id: str,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Return ALL cleaned documents as a JSON payload."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]

    clean_path = state.exports.get("clean_json") or state.exports.get("clean")
    if clean_path and Path(clean_path).exists():
        docs = _read_jsonl(Path(clean_path))
    else:
        docs = state.documents

    return {"run_id": run_id, "documents": docs, "total": len(docs)}


# ─── Export: raw CSV bytes ──────────────────────────────────────────────────

@router.get("/api/runs/{run_id}/export/raw/csv")
async def export_raw_csv(
    run_id: str,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Download raw documents as CSV."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]

    csv_path = state.exports.get("raw_csv")
    if csv_path and Path(csv_path).exists():
        content = Path(csv_path).read_bytes()
    else:
        raw_docs = state.raw_documents
        content = _docs_to_csv(raw_docs).encode("utf-8")

    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="aria_raw_{run_id}.csv"'},
    )


# ─── Export: clean CSV bytes ────────────────────────────────────────────────

@router.get("/api/runs/{run_id}/export/clean/csv")
async def export_clean_csv(
    run_id: str,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Download cleaned documents as CSV."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]

    # exporter.export_all() stores clean CSV under key "csv"
    csv_path = state.exports.get("csv") or state.exports.get("clean_csv")
    if csv_path and Path(csv_path).exists():
        content = Path(csv_path).read_bytes()
    else:
        clean_docs = state.documents
        content = _docs_to_csv(clean_docs).encode("utf-8")

    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="aria_clean_{run_id}.csv"'},
    )


# ─── Export: clean Markdown bytes ──────────────────────────────────────────

@router.get("/api/runs/{run_id}/export/clean/markdown")
async def export_clean_markdown(
    run_id: str,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Download clean documents as Markdown."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]

    md_path = state.exports.get("markdown")
    if md_path and Path(md_path).exists():
        content = Path(md_path).read_bytes()
    else:
        content = _docs_to_markdown(state.documents, state.mission or {}).encode("utf-8")

    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="aria_clean_{run_id}.md"'},
    )


# ─── Intelligence endpoints ─────────────────────────────────────────────────

@router.get("/api/runs/{run_id}/knowledge-graph")
async def get_knowledge_graph(
    run_id: str,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Return knowledge graph: entities, relationships, contradictions."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]

    # Try on-disk file first (full graph), fall back to in-memory
    kg_path = state.exports.get("knowledge_graph")
    if kg_path and Path(kg_path).exists():
        try:
            data = json.loads(Path(kg_path).read_text(encoding="utf-8"))
            return {"run_id": run_id, **data}
        except Exception:
            pass

    kg = state.knowledge_graph or {}
    return {
        "run_id": run_id,
        "top_entities": kg.get("top_entities", []),
        "total_entities": kg.get("total_entities", 0),
        "total_claims": kg.get("total_claims", 0),
        "contradictions": kg.get("contradictions", []),
        "has_contradictions": kg.get("has_contradictions", False),
        "graph": kg.get("graph"),
    }


@router.get("/api/runs/{run_id}/gap-analysis")
async def get_gap_analysis(
    run_id: str,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Return gap analysis: unanswered questions, missing perspectives, follow-up queries."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]
    ga = state.gap_analysis or {}
    return {
        "run_id": run_id,
        "has_gaps": ga.get("has_gaps", False),
        "gaps": ga.get("gaps", []),
        "answered_questions": ga.get("answered_questions", []),
        "missing_perspectives": ga.get("missing_perspectives", []),
        "recommended_sources": ga.get("recommended_sources", []),
        "follow_up_queries": ga.get("follow_up_queries", []),
    }


@router.get("/api/runs/{run_id}/images")
async def get_images(
    run_id: str,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Return extracted images from collected documents."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]

    # Try on-disk file first
    img_path = state.exports.get("images")
    if img_path and Path(img_path).exists():
        try:
            images = json.loads(Path(img_path).read_text(encoding="utf-8"))
            return {"run_id": run_id, "images": images, "total": len(images)}
        except Exception:
            pass

    images = state.images or []
    return {"run_id": run_id, "images": images, "total": len(images)}


# ─── Export: ZIP bundle ─────────────────────────────────────────────────────

@router.get("/api/runs/{run_id}/export/zip")
async def export_zip(
    run_id: str,
    run_manager: RunManager = Depends(get_run_manager),
):
    """Download a ZIP bundle with all export formats."""
    if run_id not in run_manager.runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    state = run_manager.runs[run_id]

    # Build ZIP in memory — prefer on-disk export files (full dataset)
    # over in-memory state (capped at 100 docs for UI preview).
    exports = state.exports

    def _read_export(key: str, fallback_docs: list[dict]) -> bytes:
        path_str = exports.get(key)
        if path_str and Path(path_str).exists():
            return Path(path_str).read_bytes()
        return json.dumps(fallback_docs, indent=2, default=str).encode()

    def _read_export_text(key: str, fallback: str) -> str:
        path_str = exports.get(key)
        if path_str and Path(path_str).exists():
            return Path(path_str).read_text(encoding="utf-8")
        return fallback

    raw_docs_file = exports.get("raw_json")
    raw_docs = _read_jsonl(Path(raw_docs_file)) if raw_docs_file and Path(raw_docs_file).exists() else state.raw_documents
    clean_docs_file = exports.get("clean_json")
    clean_docs = _read_jsonl(Path(clean_docs_file)) if clean_docs_file and Path(clean_docs_file).exists() else state.documents

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Raw JSON (full dataset from disk)
        zf.writestr("raw/raw_documents.json", json.dumps(raw_docs, indent=2, default=str))
        # Raw CSV
        zf.writestr("raw/raw_documents.csv", _read_export_text("raw_csv", _docs_to_csv(raw_docs)))
        # Clean JSON (full dataset from disk)
        zf.writestr("clean/clean_documents.json", json.dumps(clean_docs, indent=2, default=str))
        # Clean CSV
        zf.writestr("clean/clean_documents.csv", _read_export_text("clean_csv", _docs_to_csv(clean_docs)))
        # Markdown
        zf.writestr("clean/report.md", _read_export_text("markdown", _docs_to_markdown(clean_docs, state.mission or {})))
        # Intelligence outputs
        kg_path = exports.get("knowledge_graph")
        if kg_path and Path(kg_path).exists():
            zf.writestr("intelligence/knowledge_graph.json", Path(kg_path).read_text(encoding="utf-8"))
        elif state.knowledge_graph:
            zf.writestr("intelligence/knowledge_graph.json", json.dumps(state.knowledge_graph, indent=2, default=str))
        img_path = exports.get("images")
        if img_path and Path(img_path).exists():
            zf.writestr("intelligence/images.json", Path(img_path).read_text(encoding="utf-8"))
        elif state.images:
            zf.writestr("intelligence/images.json", json.dumps(state.images, indent=2, default=str))
        if state.gap_analysis:
            zf.writestr("intelligence/gap_analysis.json", json.dumps(state.gap_analysis, indent=2, default=str))

    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="aria_export_{run_id}.zip"'},
    )


# ─── Helpers ───────────────────────────────────────────────────────────────

def _read_jsonl(path: Path) -> list[dict]:
    """Read a file that may be a JSON array OR newline-delimited JSON (JSONL)."""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read().strip()
    if not raw:
        return []
    # Try JSON array first (what Exporter.export_raw_json / export_clean_json writes)
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict)]
        except json.JSONDecodeError:
            pass
    # Fall back to JSONL (one JSON object per line)
    docs = []
    for line in raw.splitlines():
        line = line.strip()
        if line:
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    docs.append(obj)
            except json.JSONDecodeError:
                pass
    return docs


def _docs_to_csv(docs: list[dict]) -> str:
    import csv, io as _io
    if not docs:
        return "url,title,source_type,platform,word_count,relevance_score,summary\n"
    buf = _io.StringIO()
    fieldnames = ["url", "title", "source_type", "platform", "word_count",
                  "relevance_score", "summary", "content_type"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for doc in docs:
        row = {k: doc.get(k, "") for k in fieldnames}
        row["summary"] = str(row.get("summary", ""))[:500]
        writer.writerow(row)
    return buf.getvalue()


def _docs_to_markdown(docs: list[dict], mission: dict) -> str:
    topic = (mission.get("collection") or {}).get("topic", "Research")
    lines = [f"# ARIA Research Report: {topic}\n",
             f"**Total documents:** {len(docs)}\n"]
    for i, doc in enumerate(docs[:200], 1):
        title = doc.get("title", "Untitled")
        url = doc.get("url", "")
        summary = doc.get("summary", doc.get("text", "")[:300])
        score = doc.get("relevance_score", "")
        platform = doc.get("platform", "")
        lines.append(f"\n## {i}. {title}")
        if url:
            lines.append(f"**Source:** [{url}]({url})")
        if platform:
            lines.append(f"**Platform:** {platform}")
        if score != "":
            lines.append(f"**Relevance:** {score:.2f}" if isinstance(score, float) else f"**Relevance:** {score}")
        if summary:
            lines.append(f"\n{summary}")
    return "\n".join(lines)
