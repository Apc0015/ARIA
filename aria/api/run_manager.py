"""Run manager for the canonical ARIA API surface."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from aria.access.credentials import CredentialManager
from aria.config import load_config
from aria.mission import load_mission_text
from aria.engine.orchestrator import MasterOrchestrator, RunResult
from aria.types.credentials import CredentialScope, credential_environment_keys, scoped_environ
from aria.utils.logger import configure_logging
from aria.engine.ensemble.providers import build_provider_catalog, default_llm_source_models, describe_cleaning_brain

_logger = logging.getLogger("aria")

_MAX_CONCURRENT_RUNS = int(os.environ.get("ARIA_MAX_CONCURRENT_RUNS", "20"))
_RUN_STATE_FILE = "run_state.json"
_LLM_ENV_KEYS = {
    "LLM_PROVIDER",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
}
_SAAS_CREDENTIAL_KEYS = credential_environment_keys() | {
    "LLM_PROVIDER",
    "ANTHROPIC_MODEL",
    "OPENAI_MODEL",
    "OPENROUTER_MODEL",
    "LLM_ENSEMBLE_ENABLED",
    "LLM_ENSEMBLE_MODELS",
    "LLM_ENSEMBLE_STRATEGY",
}

from aria.utils.scrub import scrub_secrets as _scrub_secrets

import re as _re

_TOPIC_JUNK = {"mission:", "collection:", "research", "null", "none", "topic:"}


def clean_topic(topic: str | None, run_id: str) -> str | None:
    """Return a human research topic, or None if only a machine string exists.

    Rejects the run-id hash, YAML/JSON fragments left by malformed pastes,
    and anything without a real word — so the UI never shows an identifier
    as a title. Single source of truth used by every run-listing endpoint.
    """
    if not topic:
        return None
    t = str(topic).strip()
    if len(t) < 4 or t == run_id or t.lower() in _TOPIC_JUNK:
        return None
    if t.startswith("Hydrated from") or t.endswith(":") or t[0] in "{}[]\"'":
        return None
    if not _re.search(r"[A-Za-z]{3,}", t):  # must contain at least one word
        return None
    return t


def run_progress(state: "RunState") -> int:
    """Return the same honest stage-based progress on every API surface."""
    docs_collected = state.docs_collected or state.stats.get("collected", 0)
    if state.status in {"completed", "completed_with_failures", "collection_completed", "failed", "cancelled"}:
        return 100
    if state.stage in {"export", "report", "export_done"}:
        return 90
    if state.stage in {"knowledge_graph", "images", "kb_save", "score"}:
        return 80
    if state.stage in {"cleaning", "clean_progress", "clean_done"}:
        return 65
    if docs_collected:
        return 40
    return 10 if state.status == "running" else 0


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
    # Intelligence outputs
    knowledge_graph: dict[str, Any] = field(default_factory=dict)
    gap_analysis: dict[str, Any] = field(default_factory=dict)
    images: list[dict[str, Any]] = field(default_factory=list)
    query_plan: dict[str, Any] = field(default_factory=dict)
    source_status: dict[str, dict[str, Any]] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)
    workflow: str = "full_research"
    tenant_id: str = ""
    user_id: str = ""
    approved_findings: list[dict[str, Any]] = field(default_factory=list)
    # Non-secret run behavior contract, required to safely restart interrupted
    # work without changing collection-only/full-research semantics.
    flags: dict[str, Any] = field(default_factory=dict)


class RunManager:
    """Manage validation, credential persistence, and background runs."""

    def __init__(self) -> None:
        self.base_settings = load_config()
        self.runs: dict[str, RunState] = {}
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()
        # Limit simultaneous heavy research tasks
        self._run_semaphore = asyncio.Semaphore(
            int(os.environ.get("ARIA_MAX_CONCURRENT_RUNS", "20"))
        )
        self._load_persisted_runs()

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

    def _credentials_file_for_tenant(self, tenant_id: str) -> Path:
        if not tenant_id:
            raise ValueError("Tenant ID is required for customer credentials.")
        return self.base_settings.credentials_file.parent / "tenants" / tenant_id / "credentials.json"

    def get_credentials(self, tenant_id: str) -> dict[str, Any]:
        manager = CredentialManager(self._credentials_file_for_tenant(tenant_id))
        raw = manager.credentials
        masked = {
            k: self._mask(v) if isinstance(v, str) and v else v
            for k, v in raw.items()
        }
        return {"platforms": masked}

    def save_credentials(self, tenant_id: str, credentials_payload: dict[str, Any]) -> Path:
        if os.getenv("ARIA_SAAS_MODE", "true").lower() in {"true", "1", "yes"} and not os.getenv("ARIA_CREDENTIALS_KEY"):
            raise ValueError("ARIA_CREDENTIALS_KEY must be configured before storing customer credentials.")
        credentials = credentials_payload.get("platforms", credentials_payload)
        if not isinstance(credentials, dict):
            raise ValueError("Credentials must be an object.")
        self._validate_tenant_credentials(credentials)
        # Settings submits only fields changed in the active section. Merge
        # with this tenant's existing encrypted values so changing one source
        # cannot silently erase every other connection.
        existing = self._load_saved_credentials(tenant_id)
        if self._managed_saas():
            # Drop legacy arbitrary environment fields rather than carrying
            # them into the next tenant-controlled research process.
            existing = {
                key: value
                for key, value in existing.items()
                if str(key).upper() in _SAAS_CREDENTIAL_KEYS
            }
        credentials = {**existing, **credentials}
        self._validate_tenant_credentials(credentials)
        manager = CredentialManager()
        manager.credentials = credentials
        return manager.save(self._credentials_file_for_tenant(tenant_id))

    def _load_saved_credentials(self, tenant_id: str) -> dict[str, Any]:
        manager = CredentialManager(self._credentials_file_for_tenant(tenant_id))
        credentials = manager.credentials
        if self._managed_saas():
            return {
                key: value
                for key, value in credentials.items()
                if str(key).upper() in _SAAS_CREDENTIAL_KEYS
            }
        return credentials

    @staticmethod
    def _managed_saas() -> bool:
        return os.getenv("ARIA_SAAS_MODE", "true").lower() in {"true", "1", "yes"}

    def _validate_tenant_credentials(self, credentials: dict[str, Any]) -> None:
        """Prevent tenant settings from turning the API into an SSRF proxy."""
        if self._managed_saas() and any(
            key in credentials and credentials[key]
            for key in ("OLLAMA_BASE_URL", "OLLAMA_MODEL")
        ):
            raise ValueError(
                "Local Ollama connections are not available in managed ARIA. "
                "Connect a supported cloud AI provider instead."
            )
        if self._managed_saas():
            unknown = sorted(
                str(key)
                for key in credentials
                if str(key).upper() not in _SAAS_CREDENTIAL_KEYS
            )
            if unknown:
                raise ValueError(
                    "Unsupported credential field(s): " + ", ".join(unknown[:5])
                )

    def get_tenant_llm_overrides(self, tenant_id: str) -> dict[str, str]:
        """Translate a tenant's saved credential fields into LLM resolver input."""
        credentials = self._load_saved_credentials(tenant_id)
        provider = str(credentials.get("LLM_PROVIDER") or "").strip().lower()
        if not provider or (self._managed_saas() and provider == "ollama"):
            return {}
        prefix = provider.upper()
        return {
            "provider": provider,
            "model": str(credentials.get(f"{prefix}_MODEL") or "").strip(),
            "api_key": str(credentials.get(f"{prefix}_API_KEY") or "").strip(),
            "base_url": str(credentials.get("OLLAMA_BASE_URL") or "").strip(),
        }

    def _build_credential_scope(self, payload: dict[str, Any], tenant_id: str) -> CredentialScope:
        """Merge env, saved UI credentials, and launch overrides for one run."""
        # A managed customer run starts from no deployment credentials at all.
        # Source tokens are as sensitive and tenant-specific as AI keys; only
        # saved tenant connections and validated launch credentials may enter.
        env: dict[str, str] = {} if self._managed_saas() else CredentialScope.from_env().to_env()

        credential_sources: list[dict[str, Any]] = []
        saved = self._load_saved_credentials(tenant_id)
        if saved:
            credential_sources.append(saved)
        if payload.get("credentials"):
            credential_sources.append(payload["credentials"])
        if payload.get("auth_tokens"):
            credential_sources.append(payload["auth_tokens"])

        zotero_cfg = payload.get("zotero_config") or {}
        if zotero_cfg:
            credential_sources.append(
                {
                    "ZOTERO_API_KEY": zotero_cfg.get("api_key"),
                    "ZOTERO_LIBRARY_ID": str(zotero_cfg.get("library_id") or ""),
                    "ZOTERO_LIBRARY_TYPE": zotero_cfg.get("library_type"),
                }
            )

        for source in credential_sources:
            env.update(
                CredentialScope.from_dict(
                    source,
                    include_process_env=not self._managed_saas(),
                ).to_env()
            )

        if self._managed_saas():
            # Quarantine legacy local-model settings saved before managed SaaS
            # enforcement was introduced. They must not alter a customer run.
            for key in ("OLLAMA_BASE_URL", "OLLAMA_MODEL"):
                env.pop(key, None)
            if env.get("LLM_PROVIDER", "").lower() == "ollama":
                env.pop("LLM_PROVIDER", None)

        launch_provider = payload.get("provider") or {}
        if not isinstance(launch_provider, dict):
            raise ValueError("Provider configuration must be an object.")
        if self._managed_saas() and (
            str(launch_provider.get("provider") or "").lower() == "ollama"
            or launch_provider.get("base_url")
        ):
            raise ValueError(
                "Local Ollama connections are not available in managed ARIA. "
                "Connect a supported cloud AI provider instead."
            )
        for provider_cfg in (launch_provider,):
            provider = (provider_cfg.get("provider") or "").strip()
            model = (provider_cfg.get("model") or provider_cfg.get("model_id") or "").strip()
            api_key = (provider_cfg.get("api_key") or "").strip()
            base_url = (provider_cfg.get("base_url") or "").strip()
            if provider:
                env["LLM_PROVIDER"] = provider
                prefix = provider.upper()
                if model:
                    env[f"{prefix}_MODEL"] = model
                if api_key:
                    env[f"{prefix}_API_KEY"] = api_key
            if base_url:
                env["OLLAMA_BASE_URL"] = base_url

        # ``CredentialScope.from_dict`` deliberately inherits the process
        # environment for legacy CLI callers. The API has already assembled a
        # tenant-specific environment above, so inheriting again would leak
        # deployment-level AI keys into a customer run.
        return CredentialScope._from_env_dict(env)

    def _state_path(self, state: RunState) -> Path:
        return Path(state.output_dir) / _RUN_STATE_FILE

    def _persist_state(self, state: RunState) -> None:
        """Persist non-secret run state so API restarts keep history/downloads."""
        if not state.output_dir:
            return
        path = self._state_path(state)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)

    def _load_persisted_runs(self) -> None:
        runs_dir = self.base_settings.runs_dir
        if not runs_dir.exists():
            return
        for run_dir in sorted(
            (path.parent for path in runs_dir.rglob(_RUN_STATE_FILE)),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            state = self._load_state_file(run_dir) or self._hydrate_run_dir(run_dir)
            if not state:
                continue
            if state.status in {"queued", "pending", "running"}:
                state.status = "interrupted"
                state.stage = "interrupted"
                state.message = "Run interrupted by API restart"
                state.error = state.error or "API restarted before this run completed. Restart this run to continue."
                state.updated_at = datetime.now(timezone.utc).isoformat()
                self._persist_state(state)
            self.runs[state.run_id] = state

    def _load_state_file(self, run_dir: Path) -> RunState | None:
        path = run_dir / _RUN_STATE_FILE
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            allowed = {f.name for f in fields(RunState)}
            state_data = {k: v for k, v in data.items() if k in allowed}
            state_data.setdefault("run_id", run_dir.name)
            state_data.setdefault("output_dir", str(run_dir))
            return RunState(**state_data)
        except Exception as exc:
            _logger.warning("Could not load run state %s: %s", path, exc)
            return None

    def _hydrate_run_dir(self, run_dir: Path) -> RunState | None:
        """Best-effort history for runs created before run_state.json existed."""
        if not (run_dir / "raw").exists() and not (run_dir / "exports").exists():
            return None

        raw_docs = self._load_docs(
            run_dir / "raw" / "raw_documents.jsonl",
            run_dir / "exports" / "raw_documents.json",
        )
        clean_docs = self._load_docs(
            run_dir / "clean" / "clean_documents.jsonl",
            run_dir / "exports" / "clean_documents.json",
        )

        export_dir = run_dir / "exports"
        export_map = {
            "raw_json": export_dir / "raw_documents.json",
            "raw_csv": export_dir / "raw_documents.csv",
            "clean_json": export_dir / "clean_documents.json",
            "clean_csv": export_dir / "clean_documents.csv",
            "csv": export_dir / "clean_documents.csv",
            "markdown": export_dir / "research_digest.md",
            "html": export_dir / "report.html",
            "zip": export_dir / "research_export.zip",
            "knowledge_graph": export_dir / "knowledge_graph.json",
            "images": export_dir / "images.json",
        }
        exports = {key: str(path) for key, path in export_map.items() if path.exists()}
        failed_marker = run_dir / "FAILED"
        status = "failed" if failed_marker.exists() else "completed"
        created_at = datetime.fromtimestamp(run_dir.stat().st_mtime, timezone.utc).isoformat()
        report_path = exports.get("markdown") or exports.get("html") or ""
        topic = self._recover_topic(run_dir, clean_docs)
        return RunState(
            run_id=run_dir.name,
            status=status,
            stage=status,
            message=topic or "Untitled run",
            created_at=created_at,
            updated_at=created_at,
            stats={
                "collected": len(raw_docs),
                "cleaned": len(clean_docs),
                # Real research topic recovered from the run's own outputs —
                # never the run-id hash (that made the UI show hashes as titles).
                "topic": topic,
            },
            docs_collected=len(raw_docs),
            docs_cleaned=len(clean_docs),
            exports=exports,
            report_path=report_path,
            documents=(clean_docs or raw_docs)[:100],
            raw_documents=raw_docs[:100],
            error=failed_marker.read_text(encoding="utf-8")[:400] if failed_marker.exists() else None,
            output_dir=str(run_dir),
        )

    @staticmethod
    def _recover_topic(run_dir: Path, clean_docs: list[dict[str, Any]]) -> str:
        """Recover a run's human topic from its own persisted outputs.

        Tried in order: the research-digest header, then the mission the
        engine saved, then the first cleaned document's topic hint. Returns
        "" when nothing human is available — callers show "Untitled run".
        """
        digest = run_dir / "exports" / "research_digest.md"
        if digest.exists():
            try:
                for line in digest.read_text(encoding="utf-8").splitlines():
                    if line.startswith("# Research Digest:"):
                        return line.split(":", 1)[1].strip()
                    if line.startswith("# "):
                        return line[2:].strip()
            except OSError:
                pass
        for name in ("mission.yaml", "mission.json"):
            path = run_dir / name
            if path.exists():
                try:
                    import yaml

                    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                    topic = (data.get("collection") or {}).get("topic")
                    if topic:
                        return str(topic)
                except Exception:
                    pass
        for doc in clean_docs[:1]:
            hint = doc.get("topic") or doc.get("research_topic")
            if hint:
                return str(hint)
        return ""

    @staticmethod
    def _load_docs(*paths: Path, limit: int = 100) -> list[dict[str, Any]]:
        for path in paths:
            if not path.exists():
                continue
            try:
                if path.suffix == ".jsonl":
                    docs = []
                    for line in path.read_text(encoding="utf-8").splitlines():
                        if line.strip():
                            docs.append(json.loads(line))
                        if len(docs) >= limit:
                            break
                    return docs
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return [d for d in data if isinstance(d, dict)][:limit]
            except Exception as exc:
                _logger.debug("Could not load run docs %s: %s", path, exc)
        return []

    def validate_mission(self, mission_yaml: str) -> dict[str, Any]:
        return load_mission_text(mission_yaml)

    def get_llm_sources(self) -> dict[str, Any]:
        return {
            "providers": build_provider_catalog(self.base_settings),
            "default_models": default_llm_source_models(self.base_settings),
            "cleaning_brain": describe_cleaning_brain(self.base_settings),
        }

    async def start_run(self, payload: dict[str, Any], *, tenant_id: str = "", user_id: str = "") -> RunState:
        # Advisory capacity check — not atomic, but provides fast UX feedback.
        # True enforcement is the semaphore inside _execute_run.
        active_runs = sum(1 for s in self.runs.values() if s.status == "running")
        max_runs = int(os.environ.get("ARIA_MAX_CONCURRENT_RUNS", "20"))
        if active_runs >= max_runs:
            raise ValueError(
                f"Server at capacity ({active_runs}/{max_runs} runs active). "
                f"Try again when a run finishes."
            )

        flags = payload.get("flags", {})
        if not isinstance(flags, dict):
            raise ValueError("Run flags must be an object.")
        for key in ("credentials", "auth_tokens"):
            submitted = payload.get(key)
            if submitted:
                if not isinstance(submitted, dict):
                    raise ValueError(f"{key} must be an object.")
                self._validate_tenant_credentials(submitted)
        # Reject a full run before creating background state. The old behavior
        # accepted it, then quietly produced an incomplete research result.
        if not bool(flags.get("collect_only", False)) and not bool(flags.get("validate_credentials", False)):
            from aria.engine.ensemble.providers import ensure_llm_ready

            credential_scope = self._build_credential_scope(payload, tenant_id)
            async with scoped_environ(
                credential_scope.to_env(),
                unset=_LLM_ENV_KEYS if self._managed_saas() else None,
            ):
                await ensure_llm_ready(self.base_settings)

        run_id = uuid4().hex[:12]
        if not tenant_id:
            raise ValueError("Tenant ID is required to start a research run.")
        output_dir = self.base_settings.runs_dir / tenant_id / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        mission = load_mission_text(payload["mission_yaml"])

        # Store any submitted source credentials before creating visible run
        # state. A rejected credential save must not leave an unstartable job
        # behind in the tenant's run history.
        credentials = payload.get("credentials")
        if credentials:
            self.save_credentials(tenant_id, credentials)

        # Attach research brief from Research Director (enables phased collection)
        research_brief = payload.get("research_brief")
        if research_brief:
            mission = dict(mission)
            mission["_research_brief"] = research_brief

        workflow = "collection_only" if bool(flags.get("collect_only", False)) else "full_research"
        state = RunState(
            run_id=run_id,
            mission=mission,
            output_dir=str(output_dir),
            workflow=workflow,
            tenant_id=tenant_id,
            user_id=user_id,
            flags=dict(flags),
            message="Queued collection-only job" if workflow == "collection_only" else "Queued",
        )
        async with self._lock:
            self.runs[run_id] = state
            self._persist_state(state)
        task = asyncio.create_task(self._execute_run(state, payload))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return state

    async def _execute_run(self, state: RunState, payload: dict[str, Any]) -> None:
        async with self._run_semaphore:  # acquire slot — released when run finishes
            credential_scope = self._build_credential_scope(payload, state.tenant_id)
            run_env = credential_scope.to_env()

            try:
                async with scoped_environ(
                    run_env,
                    unset=_LLM_ENV_KEYS if self._managed_saas() else None,
                ):
                    flags = state.flags or payload.get("flags", {})
                    output_dir = Path(state.output_dir)
                    settings = load_config(output_dir=output_dir)
                    # Point runs_dir at the parent so the engine stores files directly
                    # inside output_dir (data/runs/<run_id>/) rather than the default
                    # data/runs/<run_id>/runs/<inner_id>/ double-nesting.
                    settings = settings.model_copy(update={"runs_dir": output_dir.parent})
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
                        credentials_path=str(self._credentials_file_for_tenant(state.tenant_id)),
                    )
                await self._complete_run(state.run_id, result)
            except asyncio.CancelledError:
                # Deployments and local restarts cancel in-process jobs. Keep
                # a durable, honest state that the user can explicitly restart.
                await self._update_state(
                    state.run_id,
                    status="interrupted",
                    stage="interrupted",
                    message="Run interrupted by API shutdown",
                    error="API shut down before this run completed. Restart this run to continue.",
                )
                raise
            except Exception as exc:
                _logger.exception("Run %s failed", state.run_id)
                safe_error = f"{type(exc).__name__}: {_scrub_secrets(str(exc))[:400]}"
                await self._update_state(state.run_id, status="failed", stage="failed", message="Run failed", error=safe_error)

    async def shutdown(self) -> None:
        """Cancel local work and persist an explicit restartable state."""
        tasks = tuple(task for task in self._tasks if not task.done())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        async with self._lock:
            for state in self.runs.values():
                if state.status in {"queued", "pending", "running"}:
                    state.status = "interrupted"
                    state.stage = "interrupted"
                    state.message = "Run interrupted by API shutdown"
                    state.error = state.error or "API shut down before this run completed. Restart this run to continue."
                    state.updated_at = datetime.now(timezone.utc).isoformat()
                    self._persist_state(state)

    async def record_event(self, run_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            state = self.runs[run_id]
            state.logs.append(event)
            stage = event.get("stage", "")
            state.stage = stage or state.stage
            state.message = event.get("message", state.message)
            # Update live counters so clients see progress during the run
            if stage in ("collect_done", "source_done") and "count" in event:
                state.docs_collected = max(state.docs_collected, int(event["count"]))
            elif stage in ("clean_progress", "clean_done") and "count" in event:
                state.docs_cleaned = int(event["count"])
            elif stage == "clean_failed":
                state.failures.append(
                    {
                        "scope": "cleaning",
                        "message": event.get("message", "AI cleaning failed"),
                        "error": _scrub_secrets(str(event.get("error", "")))[:400],
                    }
                )
            source = event.get("source")
            if source and stage in {"source_started", "source_done", "source_failed"}:
                source_state = state.source_status.setdefault(str(source), {"source": source})
                source_state.update(
                    {
                        "status": {
                            "source_started": "running",
                            "source_done": "completed",
                            "source_failed": "failed",
                        }[stage],
                        "message": event.get("message", ""),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                if stage == "source_started":
                    source_state["started_at"] = source_state["updated_at"]
                if "count" in event:
                    source_state["documents"] = int(event["count"])
                if stage == "source_failed":
                    source_state["error"] = _scrub_secrets(str(event.get("error", "Collector failed")))[:400]
                    state.failures.append({"scope": "source", **source_state})
            state.updated_at = datetime.now(timezone.utc).isoformat()
            self._persist_state(state)

    async def _complete_run(self, run_id: str, result: RunResult) -> None:
        async with self._lock:
            state = self.runs[run_id]
            required_failures = [failure for failure in state.failures if failure.get("scope") in {"source", "cleaning"}]
            if state.workflow == "collection_only":
                state.status = "collection_completed"
                state.message = "Collection completed. Run full research to clean and analyze these sources."
                # Collection-only preserves raw evidence for inspection. It
                # must not present those records as AI-cleaned output.
                state.docs_cleaned = 0
                state.stats = {**result.stats, "cleaned": 0}
                state.documents = result.raw_documents[:100]
            else:
                state.status = "completed_with_failures" if required_failures else "completed"
                state.message = "Run completed with failures" if required_failures else "Run completed"
                state.stats = result.stats
                state.documents = (result.clean_documents or result.raw_documents)[:100]
            state.stage = state.status
            state.exports = result.export_paths
            state.report_path = result.report_path
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
            self._persist_state(state)

    async def _update_state(self, run_id: str, **updates: Any) -> None:
        async with self._lock:
            state = self.runs[run_id]
            for key, value in updates.items():
                setattr(state, key, value)
            state.updated_at = datetime.now(timezone.utc).isoformat()
            self._persist_state(state)

    async def get_run(self, run_id: str) -> dict[str, Any]:
        async with self._lock:
            state = self.runs[run_id]
            mission = state.mission or {}
            collection = mission.get("collection", {}) if isinstance(mission, dict) else {}
            docs_collected = state.docs_collected or state.stats.get("collected", 0)
            docs_cleaned = state.docs_cleaned or state.stats.get("cleaned", 0)
            total_documents = docs_cleaned or docs_collected or len(state.documents)
            progress = run_progress(state)
            return {
                "run_id": state.run_id,
                "status": state.status,
                "stage": state.stage,
                "message": state.message,
                "created_at": state.created_at,
                "updated_at": state.updated_at,
                "logs": state.logs[-200:],
                "stats": state.stats,
                # Internal artifact paths stay server-side. Export endpoints
                # expose only a controlled download URL and filename.
                "available_exports": sorted(state.exports),
                "documents": state.documents,
                "raw_documents": state.raw_documents,
                "ensemble_documents": state.ensemble_documents,
                "docs_collected": docs_collected,
                "docs_cleaned": docs_cleaned,
                "topic": clean_topic(
                    collection.get("topic") or state.stats.get("topic"), state.run_id
                ),
                "sources_used": collection.get("sources", {}).get("enabled", []),
                "total_documents": total_documents,
                "progress": progress,
                "error": state.error,
                # Intelligence outputs (lightweight summaries for main status call)
                "has_knowledge_graph": bool(state.knowledge_graph),
                "has_gap_analysis": bool(state.gap_analysis),
                "images_count": len(state.images),
                "contradictions_count": len((state.knowledge_graph or {}).get("contradictions", [])),
                "gaps_count": len((state.gap_analysis or {}).get("gaps", [])),
                "top_entities": (state.knowledge_graph or {}).get("top_entities", [])[:10],
                "query_plan": state.query_plan,
                "source_status": list(state.source_status.values()),
                "failures": state.failures[-100:],
                "workflow": state.workflow,
                "approved_findings": state.approved_findings,
            }
