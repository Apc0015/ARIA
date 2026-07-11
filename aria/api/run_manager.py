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
from aria.types.credentials import CredentialScope
from aria.utils.logger import configure_logging
from aria.engine.ensemble.providers import build_provider_catalog, default_llm_source_models, describe_cleaning_brain
from aria.engine.storage.run_store import RunStore

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
    # Live counters — updated mid-run from pipeline events so clients see progress
    docs_collected: int = 0
    docs_cleaned: int = 0
    exports: dict[str, str] = field(default_factory=dict)
    report_path: str = ""
    documents: list[dict[str, Any]] = field(default_factory=list)
    raw_documents: list[dict[str, Any]] = field(default_factory=list)
    ensemble_documents: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    mission: dict[str, Any] | None = None
    output_dir: str = ""
    # Per-source tracking — lets the UI show a source-by-source breakdown
    source_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    # e.g. {"web": {"docs": 23, "status": "ok"}, "twitter": {"docs": 0, "status": "skipped", "reason": "no token"}}
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
        # Persistent run store — survives server restarts
        self._run_store = RunStore()
        self._restore_runs_from_db()

    def _restore_runs_from_db(self) -> None:
        """Load completed/failed run metadata from SQLite into memory on startup."""
        try:
            for row in self._run_store.list_runs(limit=500):
                run_id = row["run_id"]
                state = RunState(
                    run_id=run_id,
                    status=row.get("status", "unknown"),
                    stage=row.get("stage", ""),
                    message=row.get("message", ""),
                    created_at=row.get("created_at", ""),
                    updated_at=row.get("updated_at", ""),
                    error=row.get("error"),
                    mission=row.get("mission"),
                    output_dir=row.get("output_dir", ""),
                    stats=row.get("stats", {}),
                    exports=row.get("exports", {}),
                    report_path=row.get("report_path", ""),
                    source_stats=row.get("source_stats", {}),
                    query_plan=row.get("query_plan", {}),
                )
                self.runs[run_id] = state
            _logger.info("RunManager: restored %d runs from database", len(self.runs))
        except Exception as exc:
            _logger.warning("RunManager: could not restore runs from DB: %s", exc)

    def list_templates(self) -> list[dict[str, Any]]:
        templates: list[dict[str, Any]] = []
        for path in sorted(self.base_settings.default_mission_file.parent.glob("*.yaml")):
            templates.append({"name": path.stem, "path": str(path), "content": path.read_text(encoding="utf-8")})
        return templates

    @staticmethod
    def _mask(value: str) -> str:
        """Mask a credential value so only the first/last 4 chars are visible."""
        if not value or len(value) < 8:
            return "***"
        return value[:4] + "*" * (len(value) - 8) + value[-4:]

    def get_credentials(self) -> dict[str, Any]:
        manager = CredentialManager(self.base_settings.credentials_file)
        raw = manager.credentials
        masked = {
            k: self._mask(v) if isinstance(v, str) and v else v
            for k, v in raw.items()
        }
        return {"platforms": masked}

    def save_credentials(self, credentials_payload: dict[str, Any]) -> Path:
        manager = CredentialManager()
        manager.credentials = credentials_payload.get("platforms", credentials_payload)
        return manager.save(self.base_settings.credentials_file)

    def validate_mission(self, mission_yaml: str) -> dict[str, Any]:
        return load_mission_text(mission_yaml)

    def set_brain_config(self, config: dict) -> None:
        """Store user's cleaning brain selection: {provider, model_id, api_key, base_url}.

        Config is stored in self._brain_config only — no os.environ mutation here.
        It is applied per-run inside _execute_run() via settings.with_llm_override()
        so concurrent runs never stomp each other's LLM credentials.
        """
        self._brain_config = config

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

        # Attach research brief from Research Director (enables phased collection)
        research_brief = payload.get("research_brief")
        if research_brief:
            mission = dict(mission)
            mission["_research_brief"] = research_brief

        collection = mission.get("collection", {}) if isinstance(mission, dict) else {}
        topic = collection.get("topic", "")
        state = RunState(run_id=run_id, mission=mission, output_dir=str(output_dir))
        async with self._lock:
            self.runs[run_id] = state
        # Persist immediately so it survives restart even if the run never completes
        self._run_store.upsert(
            run_id,
            status="queued",
            stage="queued",
            message="Queued",
            topic=topic,
            output_dir=str(output_dir),
            mission=mission,
            created_at=state.created_at,
        )
        credentials = payload.get("credentials")
        if credentials:
            self.save_credentials(credentials)
        task = asyncio.create_task(self._execute_run(state, payload))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return state

    async def _execute_run(self, state: RunState, payload: dict[str, Any]) -> None:
        async with self._run_semaphore:  # acquire slot — released when run finishes
            # Build a per-run CredentialScope from the payload — no os.environ mutation.
            # Concurrent runs each hold their own scope; no race condition possible.
            auth_tokens = payload.get("auth_tokens", {})
            zotero_cfg = payload.get("zotero_config") or {}

            # Merge zotero fields into the flat token dict for from_dict()
            merged_tokens = dict(auth_tokens)
            if zotero_cfg.get("api_key"):
                merged_tokens["zotero_api_key"] = zotero_cfg["api_key"]
            if zotero_cfg.get("library_id"):
                merged_tokens["zotero_library_id"] = str(zotero_cfg["library_id"])

            credential_scope = CredentialScope.from_dict(merged_tokens)

            try:
                flags = payload.get("flags", {})
                # Resolve LLM provider: per-run payload takes priority over
                # session-level brain config, which takes priority over env vars.
                provider = payload.get("provider") or self._brain_config or {}
                output_dir = Path(state.output_dir)
                settings = load_config(output_dir=output_dir)
                # Point runs_dir at the parent so the engine stores files directly
                # inside output_dir (data/runs/<run_id>/) rather than the default
                # data/runs/<run_id>/runs/<inner_id>/ double-nesting.
                settings = settings.model_copy(update={"runs_dir": output_dir.parent})
                if provider:
                    settings = settings.with_llm_override(
                        provider=provider.get("provider"),
                        model=provider.get("model") or provider.get("model_id"),
                        api_key=provider.get("api_key"),
                        base_url=provider.get("base_url"),
                    )
                logger = configure_logging(verbose=True)
                orchestrator = MasterOrchestrator(
                    settings,
                    logger,
                    event_callback=lambda event: self.record_event(state.run_id, event),
                    credential_scope=credential_scope,
                )
                await self._update_state(state.run_id, status="running", stage="starting", message="Run started")
                result = await orchestrator.run(
                    state.mission or {},
                    run_id=state.run_id,
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

    async def record_event(self, run_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            state = self.runs[run_id]
            state.logs.append(event)
            stage = event.get("stage", "")
            state.stage = stage or state.stage
            state.message = event.get("message", state.message)
            msg = event.get("message", "")

            # Update live counters so clients see progress during the run
            if stage in ("collect_done", "source_done") and "count" in event:
                state.docs_collected = max(state.docs_collected, int(event["count"]))
            if stage == "collect_done":
                state.stats.setdefault("dedup", {})
                state.stats["dedup"]["total_before"] = event.get("total_before_dedup", 0)
                state.stats["dedup"]["duplicates_removed"] = event.get("duplicates_removed", 0)
            elif stage in ("clean_progress", "clean_done") and "count" in event:
                state.docs_cleaned = int(event["count"])

            # Per-source stats — parse "SourceName: N docs" messages from source_done events
            if stage == "source_done" and msg:
                # Message format: "Reddit: 23 docs" or "Twitter: 0 docs (skipped)"
                import re as _re
                m = _re.match(r"^(.+?):\s*(\d+)\s*docs?(.*)?$", msg, _re.IGNORECASE)
                if m:
                    src_label = m.group(1).strip().lower().replace(" ", "_")
                    doc_count = int(m.group(2))
                    suffix = (m.group(3) or "").strip().lower()
                    status = "ok" if doc_count > 0 else "empty"
                    reason = None
                    if "skipped" in suffix or "no token" in suffix or "no credential" in suffix:
                        status = "skipped"
                        reason = suffix.strip("() ") or "no credentials"
                    elif "error" in suffix or "failed" in suffix:
                        status = "error"
                        reason = suffix.strip("() ") or "unknown error"
                    state.source_stats[src_label] = {
                        "docs": doc_count,
                        "status": status,
                        **({"reason": reason} if reason else {}),
                    }

            state.updated_at = datetime.now(timezone.utc).isoformat()

        # Push event to any active SSE subscribers (non-blocking)
        try:
            from aria.api.routes.stream import publish_event
            publish_event(run_id, event.get("stage", "event"), event)
        except Exception:
            pass

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
        # Persist final state to SQLite
        self._run_store.upsert(
            run_id,
            status="completed",
            stage="completed",
            message="Run completed",
            stats=result.stats,
            exports=result.export_paths,
            report_path=result.report_path,
            docs_collected=state.docs_collected,
            docs_cleaned=state.docs_cleaned,
            source_stats=state.source_stats,
            query_plan=result.query_plan or {},
        )

    async def _update_state(self, run_id: str, **updates: Any) -> None:
        async with self._lock:
            state = self.runs[run_id]
            for key, value in updates.items():
                setattr(state, key, value)
            state.updated_at = datetime.now(timezone.utc).isoformat()
        # Persist key status fields (skip large document lists)
        _DB_FIELDS = {"status", "stage", "message", "error", "docs_collected", "docs_cleaned"}
        db_updates = {k: v for k, v in updates.items() if k in _DB_FIELDS}
        if db_updates:
            self._run_store.upsert(run_id, **db_updates)

    async def get_run(self, run_id: str) -> dict[str, Any]:
        async with self._lock:
            state = self.runs[run_id]
            mission = state.mission or {}
            collection = mission.get("collection", {}) if isinstance(mission, dict) else {}
            docs_collected = state.docs_collected or state.stats.get("collected", 0)
            docs_cleaned = state.docs_cleaned or state.stats.get("cleaned", 0)
            total_documents = docs_cleaned or docs_collected or len(state.documents)
            if state.status == "completed":
                progress = 100
            elif state.status in {"failed", "cancelled"}:
                progress = 100
            elif state.stage in {"export", "report", "export_done"}:
                progress = 90
            elif state.stage in {"knowledge_graph", "images", "kb_save", "score"}:
                progress = 80
            elif state.stage in {"cleaning", "clean_progress", "clean_done"}:
                progress = 65
            elif docs_collected:
                progress = 40
            elif state.status == "running":
                progress = 10
            else:
                progress = 0
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
                "docs_collected": docs_collected,
                "docs_cleaned": docs_cleaned,
                "topic": collection.get("topic") or state.stats.get("topic") or state.message,
                "sources_used": collection.get("sources", {}).get("enabled", []),
                "total_documents": total_documents,
                "progress": progress,
                "error": state.error,
                "output_dir": state.output_dir,
                # Intelligence outputs (lightweight summaries for main status call)
                "has_knowledge_graph": bool(state.knowledge_graph),
                "has_gap_analysis": bool(state.gap_analysis),
                "images_count": len(state.images),
                "contradictions_count": len((state.knowledge_graph or {}).get("contradictions", [])),
                "gaps_count": len((state.gap_analysis or {}).get("gaps", [])),
                "top_entities": (state.knowledge_graph or {}).get("top_entities", [])[:10],
                "source_stats": state.source_stats,
                "query_plan": state.query_plan,
            }
