"""Run manager for the canonical ARIA API surface."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from aria.access.credentials import CredentialManager
from aria.config import load_config
from aria.mission import load_mission_text
from aria.orchestrator.master import MasterOrchestrator, RunResult
from aria.utils.logger import configure_logging
from aria.engine.ensemble.providers import build_provider_catalog, default_llm_source_models, describe_cleaning_brain

_logger = logging.getLogger("aria")

_MAX_CONCURRENT_RUNS = int(os.environ.get("ARIA_MAX_CONCURRENT_RUNS", "20"))

# Patterns that indicate a secret leaked into an exception message.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),      # OpenAI / Anthropic style
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),  # Anthropic
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{20,}", re.IGNORECASE),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),  # Slack tokens
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),           # GitHub PAT
    re.compile(r"[A-Za-z0-9_-]{40,}"),             # generic long opaque token
)


def _scrub_secrets(message: str) -> str:
    for pattern in _SECRET_PATTERNS:
        message = pattern.sub("[REDACTED]", message)
    return message


@dataclass
class RunState:
    """Tracked state for a background run."""

    run_id: str
    status: str = "queued"
    stage: str = "queued"
    message: str = "Queued"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    logs: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    exports: dict[str, str] = field(default_factory=dict)
    report_path: str = ""
    documents: list[dict[str, Any]] = field(default_factory=list)
    raw_documents: list[dict[str, Any]] = field(default_factory=list)
    ensemble_documents: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    mission: dict[str, Any] | None = None
    output_dir: str = ""
    # Intelligence outputs
    knowledge_graph: dict[str, Any] = field(default_factory=dict)
    gap_analysis: dict[str, Any] = field(default_factory=dict)
    images: list[dict[str, Any]] = field(default_factory=list)
    query_plan: dict[str, Any] = field(default_factory=dict)


class RunManager:
    """Manage validation, credential persistence, and background runs."""

    def __init__(self) -> None:
        self.base_settings = load_config()
        self.runs: dict[str, RunState] = {}
        self._lock = asyncio.Lock()
        self._brain_config: dict | None = None
        self._tasks: set[asyncio.Task] = set()
        # Limit simultaneous heavy research tasks
        self._run_semaphore = asyncio.Semaphore(
            int(os.environ.get("ARIA_MAX_CONCURRENT_RUNS", "20"))
        )
        # Serialize env-var mutations (auth tokens are set globally per-run)
        self._env_lock = asyncio.Lock()

    def list_templates(self) -> list[dict[str, Any]]:
        templates: list[dict[str, Any]] = []
        for path in sorted(self.base_settings.default_mission_file.parent.glob("*.yaml")):
            templates.append({"name": path.stem, "path": str(path), "content": path.read_text(encoding="utf-8")})
        return templates

    def get_credentials(self) -> dict[str, Any]:
        manager = CredentialManager(self.base_settings.credentials_file)
        return {"platforms": manager.credentials}

    def save_credentials(self, credentials_payload: dict[str, Any]) -> Path:
        manager = CredentialManager()
        manager.credentials = credentials_payload.get("platforms", credentials_payload)
        return manager.save(self.base_settings.credentials_file)

    def validate_mission(self, mission_yaml: str) -> dict[str, Any]:
        return load_mission_text(mission_yaml)

    def set_brain_config(self, config: dict) -> None:
        """Store user's cleaning brain selection: {provider, model_id, api_key, base_url}"""
        self._brain_config = config
        # Also set env vars so resolve_cleaning_llm() picks them up
        provider = config.get("provider", "")
        api_key = config.get("api_key", "")
        model_id = config.get("model_id", "")
        base_url = config.get("base_url", "")
        import os
        if provider == "anthropic" and api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
            os.environ["ANTHROPIC_MODEL"] = model_id
        elif provider == "openrouter" and api_key:
            os.environ["OPENROUTER_API_KEY"] = api_key
            os.environ["OPENROUTER_MODEL"] = model_id
        elif provider == "openai" and api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            os.environ["OPENAI_MODEL"] = model_id
        elif provider == "ollama":
            os.environ["OLLAMA_MODEL"] = model_id
            if base_url:
                os.environ["OLLAMA_BASE_URL"] = base_url
        os.environ["LLM_PROVIDER"] = provider

    def get_brain_config(self) -> dict:
        """Return current brain config (user-set or auto-detected from env)."""
        from aria.engine.ensemble.providers import describe_cleaning_brain
        if self._brain_config:
            return {**self._brain_config, "user_configured": True}
        return {**describe_cleaning_brain(self.base_settings), "user_configured": False}

    def get_llm_sources(self) -> dict[str, Any]:
        return {
            "providers": build_provider_catalog(self.base_settings),
            "default_models": default_llm_source_models(self.base_settings),
            "cleaning_brain": describe_cleaning_brain(self.base_settings),
        }

    async def start_run(self, payload: dict[str, Any]) -> RunState:
        # Advisory capacity check — not atomic, but provides fast UX feedback.
        # True enforcement is the semaphore inside _execute_run.
        active_runs = sum(1 for s in self.runs.values() if s.status == "running")
        max_runs = int(os.environ.get("ARIA_MAX_CONCURRENT_RUNS", "20"))
        if active_runs >= max_runs:
            raise ValueError(
                f"Server at capacity ({active_runs}/{max_runs} runs active). "
                f"Try again when a run finishes."
            )

        run_id = uuid4().hex[:12]
        output_dir = self.base_settings.runs_dir / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        mission = load_mission_text(payload["mission_yaml"])
        state = RunState(run_id=run_id, mission=mission, output_dir=str(output_dir))
        async with self._lock:
            self.runs[run_id] = state
        credentials = payload.get("credentials")
        if credentials:
            self.save_credentials(credentials)
        task = asyncio.create_task(self._execute_run(state, payload))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return state

    async def _execute_run(self, state: RunState, payload: dict[str, Any]) -> None:
        async with self._run_semaphore:  # acquire slot — released when run finishes
            _TOKEN_ENV_MAP = {
                "twitter_bearer_token": "TWITTER_BEARER_TOKEN",
                "linkedin_email":       "LINKEDIN_EMAIL",
                "linkedin_password":    "LINKEDIN_PASSWORD",
                "notion_token":         "NOTION_TOKEN",
                "slack_token":          "SLACK_TOKEN",
                "vimeo_token":          "VIMEO_ACCESS_TOKEN",
                "github_token":         "GITHUB_TOKEN",
                "news_api_key":         "NEWS_API_KEY",
                "gnews_api_key":        "GNEWS_API_KEY",
            }
            auth_tokens = payload.get("auth_tokens", {})
            # Snapshot prior env so we can restore after the run (scope tokens to this run).
            prior_env: dict[str, str | None] = {}

            # Acquire env lock to safely set auth env vars
            async with self._env_lock:
                for payload_key, env_key in _TOKEN_ENV_MAP.items():
                    val = auth_tokens.get(payload_key, "")
                    if val:
                        prior_env[env_key] = os.environ.get(env_key)
                        os.environ[env_key] = val

                # Zotero: api_key + library_id + library_type from top-level zotero_config
                zotero_config = payload.get("zotero_config") or {}
                for cfg_key, env_key in (
                    ("api_key",      "ZOTERO_API_KEY"),
                    ("library_id",   "ZOTERO_LIBRARY_ID"),
                    ("library_type", "ZOTERO_LIBRARY_TYPE"),
                ):
                    val = (zotero_config.get(cfg_key) or "").strip() if isinstance(zotero_config.get(cfg_key), str) else zotero_config.get(cfg_key)
                    if val:
                        prior_env[env_key] = os.environ.get(env_key)
                        os.environ[env_key] = str(val)

            try:
                # orchestrator runs WITHOUT holding env_lock (env vars are now set)
                flags = payload.get("flags", {})
                provider = payload.get("provider", {})
                settings = load_config(output_dir=Path(state.output_dir))
                if provider:
                    settings = settings.with_llm_override(
                        provider=provider.get("provider"),
                        model=provider.get("model"),
                        api_key=provider.get("api_key"),
                        base_url=provider.get("base_url"),
                    )
                logger = configure_logging(verbose=True)
                orchestrator = MasterOrchestrator(settings, logger, event_callback=lambda event: self.record_event(state.run_id, event))
                await self._update_state(state.run_id, status="running", stage="starting", message="Run started")
                result = await orchestrator.run(
                    state.mission or {},
                    collect_only=bool(flags.get("collect_only", False)),
                    clean_only=bool(flags.get("clean_only", False)),
                    validate_credentials=bool(flags.get("validate_credentials", False)),
                    authenticated_only=bool(flags.get("authenticated_only", False)),
                    public_only=bool(flags.get("public_only", False)),
                    resume=bool(flags.get("resume", False)),
                    credentials_path=str(self.base_settings.credentials_file),
                )
                await self._complete_run(state.run_id, result)
            except Exception as exc:
                _logger.exception("Run %s failed", state.run_id)
                safe_error = f"{type(exc).__name__}: {_scrub_secrets(str(exc))[:400]}"
                await self._update_state(state.run_id, status="failed", stage="failed", message="Run failed", error=safe_error)
            finally:
                # Re-acquire env lock to safely restore env vars
                async with self._env_lock:
                    for env_key, prior_val in prior_env.items():
                        if prior_val is None:
                            os.environ.pop(env_key, None)
                        else:
                            os.environ[env_key] = prior_val

    async def record_event(self, run_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            state = self.runs[run_id]
            state.logs.append(event)
            state.stage = event.get("stage", state.stage)
            state.message = event.get("message", state.message)
            state.updated_at = datetime.now(timezone.utc).isoformat()

    async def _complete_run(self, run_id: str, result: RunResult) -> None:
        async with self._lock:
            state = self.runs[run_id]
            state.status = "completed"
            state.stage = "completed"
            state.message = "Run completed"
            state.stats = result.stats
            state.exports = result.export_paths
            state.report_path = result.report_path
            state.documents = (result.clean_documents or result.raw_documents)[:100]
            state.raw_documents = result.raw_documents[:100]
            state.ensemble_documents = [
                document for document in result.raw_documents if document.get("source_type") in {"llm_response", "llm_comparison"}
            ][:60]
            # Intelligence outputs
            state.knowledge_graph = result.knowledge_graph or {}
            state.gap_analysis = result.gap_analysis or {}
            state.images = result.images or []
            state.query_plan = result.query_plan or {}
            state.updated_at = datetime.now(timezone.utc).isoformat()

    async def _update_state(self, run_id: str, **updates: Any) -> None:
        async with self._lock:
            state = self.runs[run_id]
            for key, value in updates.items():
                setattr(state, key, value)
            state.updated_at = datetime.now(timezone.utc).isoformat()

    async def get_run(self, run_id: str) -> dict[str, Any]:
        async with self._lock:
            state = self.runs[run_id]
            return {
                "run_id": state.run_id,
                "status": state.status,
                "stage": state.stage,
                "message": state.message,
                "created_at": state.created_at,
                "updated_at": state.updated_at,
                "logs": state.logs[-200:],
                "stats": state.stats,
                "exports": state.exports,
                "report_path": state.report_path,
                "documents": state.documents,
                "raw_documents": state.raw_documents,
                "ensemble_documents": state.ensemble_documents,
                "error": state.error,
                "output_dir": state.output_dir,
                # Intelligence outputs (lightweight summaries for main status call)
                "has_knowledge_graph": bool(state.knowledge_graph),
                "has_gap_analysis": bool(state.gap_analysis),
                "images_count": len(state.images),
                "contradictions_count": len((state.knowledge_graph or {}).get("contradictions", [])),
                "gaps_count": len((state.gap_analysis or {}).get("gaps", [])),
                "top_entities": (state.knowledge_graph or {}).get("top_entities", [])[:10],
                "query_plan": state.query_plan,
            }
