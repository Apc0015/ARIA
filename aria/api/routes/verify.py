"""Credential verification and LLM status endpoints."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Request

from aria.api.authorization import current_user, require_role
from aria.api.run_manager import RunManager
from aria.types.credentials import scoped_environ
from aria.utils.scrub import scrub_secrets

router = APIRouter()


def _tenant_brain_overrides(request: Request) -> dict[str, str]:
    """Resolve AI configuration from the authenticated tenant only."""
    run_manager: RunManager = request.app.state.run_manager
    return run_manager.get_tenant_llm_overrides(current_user(request)["tenant_id"])


@router.post("/api/credentials/verify")
async def verify_credential(payload: dict[str, Any], request: Request):
    """Test whether credentials for a source are valid.

    Body: { source_id: str, credentials: { ENV_KEY: value, ... } }
    Returns: { ok: bool, message: str }
    """
    require_role(request, "admin", "member")
    source_id = (payload.get("source_id") or "").strip()
    creds = {k: v for k, v in (payload.get("credentials") or {}).items() if v}

    if not source_id:
        return {"ok": False, "message": "source_id is required"}

    from aria.engine.orchestrator.collection import _COLLECTOR_REGISTRY

    entry = _COLLECTOR_REGISTRY.get(source_id)
    if not entry:
        return {"ok": False, "message": f"Unknown source: {source_id}"}

    module_path, class_name, _, label = entry
    try:
        import importlib

        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        async with scoped_environ(creds):
            collector = cls()
            result = await collector.validate()
        return {
            "ok": bool(result),
            "message": "Connected ✓" if result else "Credentials not accepted",
        }
    except Exception as exc:
        # Scrub before echoing: HTTP client errors can embed the submitted
        # credential in URLs or headers.
        return {"ok": False, "message": scrub_secrets(str(exc))[:300]}


@router.get("/api/llm/status")
async def llm_status(request: Request):
    """Return the active LLM provider and model as resolved by the cleaning pipeline."""
    try:
        from aria.engine.ensemble.providers import resolve_cleaning_llm

        overrides = _tenant_brain_overrides(request)
        if not overrides.get("provider"):
            return {
                "provider": "none",
                "model": "",
                "base_url": "",
                "configured": False,
                "connected": False,
                "message": "No LLM connected. Connect an AI model in Settings.",
            }
        provider, model_id, base_url, api_key = resolve_cleaning_llm(
            None, overrides=overrides
        )
        base_url = base_url or ""

        if not provider:
            return {
                "provider": "none",
                "model": "",
                "base_url": "",
                "configured": False,
                "connected": False,
                "message": "No LLM connected. Connect an AI model in Settings.",
            }

        if provider == "ollama":
            url = (base_url or "http://localhost:11434/v1").removesuffix("/v1")
            try:
                async with httpx.AsyncClient(timeout=2.5) as client:
                    resp = await client.get(f"{url}/api/tags")
                resp.raise_for_status()
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                has_model = model_id in models
                return {
                    "provider": provider,
                    "model": model_id,
                    "base_url": url,
                    "configured": has_model,
                    "connected": True,
                    "message": (
                        "Ready"
                        if has_model
                        else (
                            f"Ollama connected, but model '{model_id}' "
                            "is not installed."
                        )
                    ),
                }
            except Exception:
                return {
                    "provider": provider,
                    "model": model_id,
                    "base_url": url,
                    "configured": False,
                    "connected": False,
                    "message": "Ollama is not reachable.",
                }

        configured = bool(api_key)
        return {
            "provider": provider,
            "model": model_id,
            "base_url": base_url,
            "configured": configured,
            "connected": None,
            "message": "API key configured" if configured else "API key required",
        }
    except Exception as exc:
        return {
            "provider": "unknown",
            "model": "unknown",
            "base_url": "",
            "configured": False,
            "connected": False,
            "message": scrub_secrets(str(exc))[:300],
        }


@router.get("/api/llm/models")
async def llm_models(
    provider: str = "ollama", base_url: str = "http://localhost:11434"
):
    """Return available models for a provider.

    Currently supports Ollama (calls /api/tags).
    Cloud providers return their static default model list.
    """
    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{base_url}/api/tags")
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    return {"provider": "ollama", "models": models, "connected": True}
        except Exception:
            pass
        return {"provider": "ollama", "models": [], "connected": False}

    # Cloud providers — shared static catalog (see providers.py)
    from aria.engine.ensemble.providers import STATIC_MODEL_CATALOG

    return {
        "provider": provider,
        "models": STATIC_MODEL_CATALOG.get(provider, []),
        "connected": False,
    }
