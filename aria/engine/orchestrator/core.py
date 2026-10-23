"""Core orchestration engine: thin coordinator that calls phase modules.

Phase modules (each exposes one primary async function):
  planning.py   — query expansion and sub-question generation
  collection.py — spawning collector tasks in parallel
  dedup.py      — URL-hash + content-fingerprint + semantic deduplication
  cleaning.py   — per-document LLM cleaning coordination
  enrichment.py — knowledge graph, gap detection, image extraction
  exporting.py  — writing JSON/CSV/Markdown/ZIP outputs to disk
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# ── Phase modules ─────────────────────────────────────────────────────────────
from aria.engine.orchestrator.planning import (
    _flatten_plan_queries,
    _heuristic_plan,
    run_planning_phase,
)
from aria.engine.orchestrator.collection import (
    CollectorDispatcher,
    run_collection_phase,
    run_phased_collection,
)
from aria.engine.orchestrator.dedup import _content_fingerprint
from aria.engine.orchestrator.cleaning import run_cleaning_phase
from aria.engine.orchestrator.enrichment import _score_documents, run_enrichment_phase
from aria.engine.orchestrator.exporting import run_export_phase
from aria.engine.orchestrator.citation_crawl import (
    citation_crawl_enabled,
    run_citation_crawl_phase,
)
from aria.engine.output.citation_exporter import CitationExporter
from aria.engine.output.bibtex import BibTeXExporter

from aria.utils.scrub import scrub_secrets as _scrub


from aria.engine.cleaner.llm_cleaner import LLMCleaner
from aria.engine.memory.shared_memory import SharedMemory
from aria.engine.storage.clean_store import CleanStore
from aria.engine.storage.raw_store import RawStore

logger = logging.getLogger("aria")


@dataclass
class RunResult:
    """Result of a completed collection run."""

    run_id: str
    stats: dict = field(default_factory=dict)
    raw_documents: list[dict] = field(default_factory=list)
    clean_documents: list[dict] = field(default_factory=list)
    export_paths: dict[str, str] = field(default_factory=dict)
    report_path: str = ""
    # Intelligence outputs
    knowledge_graph: dict = field(default_factory=dict)
    gap_analysis: dict = field(default_factory=dict)
    images: list[dict] = field(default_factory=list)
    query_plan: dict = field(default_factory=dict)
    # Collection methodology — how and where data was gathered
    methodology: dict = field(default_factory=dict)


class ResultAggregator:
    """Aggregates and deduplicates results from parallel collectors."""

    def __init__(
        self,
        shared_memory: SharedMemory,
        known_urls: Optional[set[str]] = None,
    ) -> None:
        self._memory = shared_memory
        from aria.utils.url import normalize_url

        self._known_urls = {
            normalize_url(url)
            for url in (known_urls or set())
            if url
        }  # KB-known URLs to skip

    async def aggregate(self, collector_results: list[list[dict]]) -> list[dict]:
        """Flatten, deduplicate, and return a unified document list."""
        unique_docs: list[dict] = []
        from aria.utils.url import normalize_url

        for batch in collector_results:
            if not batch:
                continue
            for doc in batch:
                raw_url = doc.get("url", "")
                url = normalize_url(raw_url) or raw_url.strip()
                text = doc.get("text") or doc.get("content") or doc.get("body") or ""

                if url and url in self._known_urls:
                    continue

                if url:
                    is_new_url = self._memory.add_url(url)
                    if not is_new_url:
                        continue

                if text and len(text.strip()) > 50:
                    fp = _content_fingerprint(text)
                    is_new_fp = self._memory.add_fingerprint(fp)
                    if not is_new_fp:
                        continue

                unique_docs.append(doc)

        return unique_docs


MeshAggregator = ResultAggregator  # backwards-compat alias


class InfoCollectorOrchestrator:
    """Main engine that runs a complete ARIA research collection pipeline.

    Pipeline:
    1. Parse mission
    2. Smart query planning (LLM decomposes topic → sub-questions + queries)
    3. KB lookup (skip already-collected URLs for incremental runs)
    4. Run collectors in parallel
    5. Aggregate + deduplicate (URL + fingerprint + semantic MinHash)
    6. Clean documents with LLM (streaming or batch)
    7. Multi-dimensional relevance scoring
    8. Gap detection → optional second-pass collection
    9. Knowledge graph (entities, relationships, contradictions)
    10. Image extraction
    11. Save to persistent KB
    12. Export results + report
    """

    def __init__(
        self,
        config: Any,
        logger: Optional[logging.Logger] = None,
        event_callback: Optional[Callable] = None,
        credential_scope: Optional[Any] = None,
    ) -> None:
        self._config = config
        self._log = logger or logging.getLogger("aria")
        self._event_callback = event_callback
        # Per-run credential scope — avoids os.environ mutation in concurrent runs.
        self._credential_scope = credential_scope

    def _get_key(self, env_name: str, scope_attr: str) -> str:
        """Return credential: scope override first, then os.environ fallback."""
        if self._credential_scope:
            return self._credential_scope.get(env_name, scope_attr)
        return os.getenv(env_name, "")

    async def run(
        self,
        mission: dict,
        collect_only: bool = False,
        clean_only: bool = False,
        validate_credentials: bool = False,
        authenticated_only: bool = False,
        public_only: bool = False,
        resume: bool = False,
        credentials_path: Optional[str] = None,
        raw_dir: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> RunResult:
        """Execute a full research collection run."""
        run_id = run_id or str(uuid.uuid4())[:8]
        topic = mission.get("collection", {}).get("topic", "research")
        await self._emit("init", f"Starting run {run_id}", run_id=run_id, topic=topic)

        # Full runs promise AI cleaning and intelligence enrichment. Refuse to
        # start when that promise cannot be kept instead of silently skipping it.
        if not collect_only and not validate_credentials:
            from aria.engine.ensemble.providers import ensure_llm_ready

            await ensure_llm_ready(self._config)

        runs_dir = Path(self._config.runs_dir)
        run_dir = runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        _failed_marker = run_dir / "FAILED"

        try:
            return await self._run_pipeline(
                run_id=run_id,
                run_dir=run_dir,
                mission=mission,
                collect_only=collect_only,
                clean_only=clean_only,
                validate_credentials=validate_credentials,
                authenticated_only=authenticated_only,
                public_only=public_only,
                resume=resume,
                credentials_path=credentials_path,
                raw_dir=raw_dir,
            )
        except Exception as exc:
            _failed_marker.write_text(_scrub(str(exc)), encoding="utf-8")
            await self._emit("error", f"Run failed: {_scrub(str(exc))}", run_id=run_id)
            raise

    async def _run_pipeline(
        self,
        run_id: str,
        run_dir: Path,
        mission: dict,
        collect_only: bool,
        clean_only: bool,
        validate_credentials: bool,
        authenticated_only: bool,
        public_only: bool,
        resume: bool,
        credentials_path: Optional[str],
        raw_dir: Optional[str],
    ) -> RunResult:
        """Inner pipeline body — delegates each phase to its module."""
        # Safe default so Python never treats topic as unbound
        # (assigned unconditionally below, but guard prevents NameError
        # if control flow ever changes in future refactors).
        topic = ""
        _pipeline_start = datetime.now(timezone.utc)
        raw_store = RawStore(Path(raw_dir) if raw_dir else run_dir / "raw")
        clean_store = CleanStore(run_dir / "clean")
        export_dir = run_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        shared_memory = SharedMemory(
            backend=self._config.shared_memory_backend,
            redis_url=self._config.redis_url,
            # Redis deduplication is isolated to this exact research run.
            # No tenant can influence another tenant's collection results.
            namespace=f"aria:run:{run_id}",
        )

        if validate_credentials:
            await self._emit("validate", "Validating credentials...")
            creds_file = credentials_path or str(self._config.credentials_file)
            if creds_file and Path(creds_file).exists():
                await self._emit("validate", "Credentials file found")
            else:
                await self._emit("validate", "No credentials file found (public sources only)")
            return RunResult(run_id=run_id, stats={"validated": True})

        collection_cfg = mission.get("collection", {})
        topic = collection_cfg.get("topic", "research")
        intent = collection_cfg.get("intent", "")
        max_docs = collection_cfg.get("max_documents", 500)
        max_per_source = collection_cfg.get("max_per_source", 50)

        # ARIA 5.0: auto-build domain plan from mission domains/countries
        if "_domain_plan" not in mission:
            domains_cfg = collection_cfg.get("domains", [])
            countries_cfg = collection_cfg.get("countries", [])
            if domains_cfg:
                try:
                    from aria.engine.domains.planner import build_collection_plan
                    await self._emit("query_plan", f"Building domain plan for domains={domains_cfg}, countries={countries_cfg}")
                    dp = await build_collection_plan(
                        query=topic or intent,
                        domains=domains_cfg,
                        countries=countries_cfg or None,
                    )
                    mission = dict(mission)
                    mission["_domain_plan"] = dp
                except Exception as exc:
                    self._log.debug("Auto domain plan failed (falling back to standard): %s", exc)

        # ── Citation Crawl (optional pre-collection phase) ────────────────────
        if citation_crawl_enabled(mission):
            await self._emit("citation_crawl", "Citation crawl phase starting…")
            try:
                citation_records = await run_citation_crawl_phase(
                    mission_config=mission,
                    output_dir=str(run_dir),
                    emit_fn=self._event_callback,
                    log=self._log,
                )
                if citation_records:
                    # Export corpus.json + bibtex + missing-full-text.md
                    citation_paths = CitationExporter(str(run_dir)).export(citation_records)
                    citation_paths["bibtex"] = BibTeXExporter(str(run_dir)).export(
                        citation_records,
                        filename="references-level0.bib",
                        level=1,
                    )
                    await self._emit(
                        "citation_crawl",
                        "Citation crawl outputs written: corpus.json, references-level0.bib, missing-full-text.md",
                        export_paths=citation_paths,
                    )
            except Exception as exc:
                self._log.warning("Citation crawl phase failed (non-fatal): %s", _scrub(str(exc)))

        # ── Planning ─────────────────────────────────────────────────────────
        research_brief = mission.get("_research_brief")
        if research_brief:
            resolved = research_brief.get("resolved_topic") or topic
            topic = resolved
            sub_questions = research_brief.get("key_questions", [])
            all_phase_queries: list[str] = []
            for ph in research_brief.get("phases", []):
                all_phase_queries.extend(ph.get("queries", []))
            queries = list(dict.fromkeys(all_phase_queries))[:20]
            query_plan = {
                "sub_questions": sub_questions,
                "queries": {"general": queries},
                "source_priorities": {},
                "entity_seeds": research_brief.get("entities", []),
            }
            await self._emit(
                "query_plan",
                f"Research Director plan: {len(research_brief.get('phases', []))} phases, "
                f"{len(sub_questions)} questions, {len(queries)} queries",
                queries=queries,
                sub_questions=sub_questions,
                research_brief=research_brief,
            )
        else:
            await self._emit("query_plan", f"Planning research strategy for: '{topic}'")
            query_plan = await self._plan_queries(topic, intent)
            sub_questions = query_plan.get("sub_questions", [])
            queries = _flatten_plan_queries(query_plan, max_total=20)
            await self._emit(
                "query_plan",
                f"Research plan: {len(sub_questions)} sub-questions, {len(queries)} queries",
                queries=queries,
                sub_questions=sub_questions,
            )

        # ── KB lookup ────────────────────────────────────────────────────────
        kb = self._init_kb()
        known_urls: set[str] = set()
        if kb and not clean_only:
            known_urls = kb.get_known_urls_for_topic(topic)
            if known_urls:
                await self._emit("kb_lookup", f"KB: skipping {len(known_urls)} already-collected URLs")

        if known_urls:
            from aria.utils.url import normalize_url
            known_urls = {normalize_url(u) for u in known_urls if u}

        aggregator = ResultAggregator(shared_memory, known_urls=known_urls)
        raw_docs: list[dict] = []

        # ── Collection ───────────────────────────────────────────────────────
        if clean_only:
            await self._emit("skip_collection", "clean_only=True, loading existing raw docs")
            raw_docs = raw_store.load()
            if not raw_docs:
                raise FileNotFoundError(
                    f"clean_only=True requires raw docs at {raw_store.path}"
                )

        if not clean_only:
            domain_plan = mission.get("_domain_plan")
            if domain_plan is not None:
                await self._emit("collect", f"Running domain plan: {domain_plan.summary}")
                from aria.engine.orchestrator.department_runner import DepartmentRunner
                runner = DepartmentRunner(
                    config=self._config,
                    max_per_collector=max_per_source,
                    emit_callback=self._emit,
                )
                raw_docs = await runner.run(domain_plan, aggregator)
                raw_docs = raw_docs[:max_docs]
                raw_store.save(raw_docs)
                await self._emit("collect_done", f"Collected {len(raw_docs)} unique documents (domain plan)", count=len(raw_docs))
            elif research_brief and research_brief.get("phases"):
                raw_docs = await run_phased_collection(
                    phases=research_brief["phases"],
                    max_per_source=max_per_source,
                    max_docs=max_docs,
                    mission=mission,
                    aggregator=aggregator,
                    config=self._config,
                    emit_fn=self._emit,
                    log=self._log,
                )
                raw_store.save(raw_docs)
            else:
                enabled_sources = collection_cfg.get("sources", {}).get("enabled", ["web", "pdf", "academic"])
                raw_docs = await run_collection_phase(
                    queries=queries,
                    enabled_sources=enabled_sources,
                    max_per_source=max_per_source,
                    max_docs=max_docs,
                    mission=mission,
                    aggregator=aggregator,
                    config=self._config,
                    emit_fn=self._emit,
                    log=self._log,
                )
                if self._config.semantic_dedup_enabled:
                    try:
                        from aria.engine.intelligence.semantic_dedup import SemanticDeduplicator
                        dedup = SemanticDeduplicator()
                        raw_docs, removed = dedup.filter_documents(raw_docs)
                        if removed:
                            await self._emit("dedup", f"Semantic dedup removed {removed} duplicate documents")
                    except Exception as exc:
                        self._log.debug("Semantic dedup failed: %s", exc)

                # ── Web link crawl (configurable depth) ───────────────────────
                if self._config.link_crawl_enabled and raw_docs:
                    try:
                        from aria.engine.collectors.web.link_crawler import crawl_links
                        from aria.utils.url import normalize_url

                        seen: set[str] = {
                            normalize_url(d.get("url", ""))
                            for d in raw_docs
                            if d.get("url")
                        }

                        # Depth-1: follow links from search results
                        link_docs = await crawl_links(
                            raw_docs,
                            max_per_doc=self._config.link_crawl_max_per_doc,
                            max_total=self._config.link_crawl_max_total,
                            seen_urls=seen,
                        )
                        if link_docs:
                            raw_docs = raw_docs + link_docs
                            await self._emit(
                                "link_crawl",
                                f"Link crawler depth-1: {len(link_docs)} pages",
                                count=len(link_docs),
                            )

                        # Depth-2: follow links from depth-1 pages
                        if link_docs and self._config.link_crawl_depth >= 2:
                            remaining = max(self._config.link_crawl_max_total - len(link_docs), 0)
                            if remaining <= 0:
                                depth2_max = 0
                            else:
                                depth2_max = min(remaining, max(5, self._config.link_crawl_max_total // 2))
                        else:
                            depth2_max = 0

                        if depth2_max > 0:
                            depth2_docs = await crawl_links(
                                link_docs,
                                max_per_doc=1,        # 1 link per depth-1 page keeps scope manageable
                                max_total=depth2_max,
                                seen_urls=seen,       # seen is already updated by depth-1
                            )
                            if depth2_docs:
                                raw_docs = raw_docs + depth2_docs
                                await self._emit(
                                    "link_crawl",
                                    f"Link crawler depth-2: {len(depth2_docs)} pages",
                                    count=len(depth2_docs),
                                )
                    except Exception as exc:
                        self._log.debug("Link crawl failed: %s", exc)

                raw_store.save(raw_docs)

        source_stats = _count_by_platform(raw_docs)
        cleaning_cfg = mission.get("cleaning", {})
        instructions = cleaning_cfg.get("instructions", "Extract key information.")
        output_schema = cleaning_cfg.get("output_schema", {})

        # ── Cleaning ─────────────────────────────────────────────────────────
        if collect_only:
            await self._emit("skip_clean", "collect_only=True, skipping cleaning")
            clean_docs = raw_docs
        else:
            clean_docs = await run_cleaning_phase(
                raw_docs, instructions, output_schema, self._config,
                emit_fn=self._emit, log=self._log,
            )

        # ── Citation following ────────────────────────────────────────────────
        if self._config.citation_following_enabled and clean_docs and not collect_only:
            try:
                from aria.engine.citation.agent import CitationAgent
                agent = CitationAgent(
                    max_depth=self._config.citation_depth,
                    max_citations=self._config.citation_max,
                )
                enriched = await agent.enrich(clean_docs)
                n_new = len(enriched) - len(clean_docs)
                if n_new > 0:
                    clean_docs = enriched
                    await self._emit(
                        "citation_follow",
                        f"CitationAgent: {n_new} cited papers added (depth={self._config.citation_depth})",
                        count=n_new,
                    )
            except Exception as exc:
                self._log.debug("CitationAgent failed: %s", exc)

        # ── Score + sort ──────────────────────────────────────────────────────
        await self._emit("score", "Scoring document relevance...")
        clean_docs = _score_documents(clean_docs, topic, intent, self._log)
        output_cfg = mission.get("output", {})
        sort_by = output_cfg.get("sort_by", "relevance_score")
        sort_order = output_cfg.get("sort_order", "desc")
        if sort_by:
            clean_docs = sorted(
                clean_docs,
                key=lambda d: d.get(sort_by, 0) or 0,
                reverse=(sort_order == "desc"),
            )
        if not collect_only:
            clean_store.save(clean_docs)

        # ── Enrichment ────────────────────────────────────────────────────────
        # All intelligence behavior lives in one phase module. This prevents
        # graph/gap/image behavior from silently diverging between code paths.
        async def _gap_followup(follow_up_queries: list[str], _gap_result: dict) -> list[dict]:
            return await self._run_gap_followup(
                follow_up_queries=follow_up_queries,
                enabled_sources=collection_cfg.get("sources", {}).get("enabled", ["web", "academic"]),
                max_per_source=max(5, max_per_source // 3),
                aggregator=aggregator,
                instructions=instructions,
                output_schema=output_schema,
                topic=topic,
                intent=intent,
            )

        enrichment = await run_enrichment_phase(
            clean_docs,
            topic,
            intent,
            sub_questions,
            self._config.model_copy(
                update={
                    "gap_detection_enabled": self._config.gap_detection_enabled and not collect_only,
                    "knowledge_graph_enabled": self._config.knowledge_graph_enabled and not collect_only,
                    "image_extraction_enabled": self._config.image_extraction_enabled and not collect_only,
                }
            ),
            emit_fn=self._emit,
            log=self._log,
            gap_followup_fn=None if collect_only else _gap_followup,
        )
        gap_result = enrichment["gap_result"]
        kg_data = enrichment["kg_data"]
        images = enrichment["images"]
        extra_docs = enrichment["extra_docs"]
        if extra_docs:
            clean_docs.extend(extra_docs)
            if sort_by:
                clean_docs = sorted(clean_docs, key=lambda d: d.get(sort_by, 0) or 0, reverse=(sort_order == "desc"))
            clean_store.save(clean_docs)
            await self._emit("gap_done", f"Added {len(extra_docs)} docs from gap follow-up")

        # ── KB save ───────────────────────────────────────────────────────────
        if kb and clean_docs:
            added, skipped = kb.add_documents_batch(clean_docs, topic=topic, run_id=run_id)
            await self._emit("kb_save", f"KB: saved {added} new docs ({skipped} already known)")

        # ── Stats + methodology ───────────────────────────────────────────────
        relevant_count = sum(1 for d in clean_docs if d.get("is_relevant", True))
        stats = {
            "collected": len(raw_docs),
            "cleaned": 0 if collect_only else len(clean_docs),
            "relevant": relevant_count,
            "sources": source_stats,
            "run_id": run_id,
            "topic": topic,
            "has_contradictions": bool(kg_data.get("contradictions")),
            "total_entities": kg_data.get("total_entities", 0),
            "gaps_found": len(gap_result.get("gaps", [])),
            "images_found": len(images),
            "kb_topic_total": kb.stats().get("total_documents", 0) if kb else 0,
        }
        _pipeline_end = datetime.now(timezone.utc)
        domain_plan = mission.get("_domain_plan")
        _method = "domain_plan" if domain_plan else "standard"
        _domains = list(domain_plan.intent.domains) if domain_plan else collection_cfg.get("domains", [])
        _countries = list(domain_plan.intent.countries) if domain_plan else collection_cfg.get("countries", [])
        _sources_used = (
            list(domain_plan.active_collectors)
            if domain_plan
            else collection_cfg.get("sources", {}).get("enabled", [])
        )
        _citation_depth = domain_plan.citation_depth if domain_plan else 0
        _citation_docs = sum(1 for d in clean_docs if d.get("is_citation"))
        try:
            from aria.engine.ensemble.providers import resolve_cleaning_llm
            _provider, _model, _, _ = resolve_cleaning_llm(None)
        except Exception:
            _provider, _model = "unknown", "unknown"
        _dedup_parts = ["URL", "content fingerprint"]
        if self._config.semantic_dedup_enabled:
            _dedup_parts.append("semantic MinHash")
        methodology = {
            "collection_method": _method,
            "domains": _domains,
            "countries": _countries,
            "sources_used": _sources_used,
            "queries": queries,
            "query_count": len(queries),
            "citation_depth": _citation_depth,
            "citation_docs_fetched": _citation_docs,
            "llm_provider": _provider,
            "llm_model": _model,
            "cleaning_method": "not_run" if collect_only else ("llm" if _provider != "unknown" else "fallback"),
            "dedup_method": " + ".join(_dedup_parts),
            "started_at": _pipeline_start.isoformat(),
            "completed_at": _pipeline_end.isoformat(),
            "duration_seconds": (_pipeline_end - _pipeline_start).total_seconds(),
        }

        # ── Export + report ───────────────────────────────────────────────────
        formats = output_cfg.get("formats", ["json", "csv", "markdown", "html", "zip"])
        export_paths, report_path = await run_export_phase(
            raw_docs=raw_docs,
            clean_docs=clean_docs,
            topic=topic,
            export_dir=export_dir,
            formats=formats,
            stats=stats,
            kg_data=kg_data,
            images=images,
            gap_result=gap_result,
            methodology=methodology,
            report_documents=clean_docs if collect_only else None,
            include_clean_exports=not collect_only,
            emit_fn=self._emit,
            log=self._log,
        )
        await self._emit("done", "Run complete", stats=stats)

        return RunResult(
            run_id=run_id,
            stats=stats,
            raw_documents=raw_docs,
            clean_documents=[] if collect_only else clean_docs,
            export_paths=export_paths,
            report_path=report_path,
            knowledge_graph=kg_data,
            gap_analysis=gap_result,
            images=images,
            query_plan=query_plan,
            methodology=methodology,
        )

    async def _plan_queries(self, topic: str, intent: str) -> dict:
        """Use smart query planner (LLM) or fall back to heuristic."""
        if self._config.smart_query_planning:
            try:
                from aria.engine.intelligence.query_planner import plan_queries
                from aria.engine.utils.retry import with_retry

                max_attempts = int(getattr(self._config, "llm_retry_max_attempts", 3))
                base_delay = float(getattr(self._config, "llm_retry_base_delay", 1.0))
                max_delay = float(getattr(self._config, "llm_retry_max_delay", 20.0))

                return await with_retry(
                    plan_queries,
                    topic,
                    intent,
                    max_attempts=max_attempts,
                    base_delay=base_delay,
                    max_delay=max_delay,
                )
            except Exception as exc:
                self._log.debug("Smart query planner failed: %s", exc)
        return _heuristic_plan(topic, intent)

    def _init_kb(self):
        """Init persistent knowledge base. Returns None if disabled."""
        if not self._config.kb_enabled:
            return None
        try:
            from aria.engine.knowledge_base.kb import KnowledgeBase
            return KnowledgeBase(db_path=self._config.kb_path)
        except Exception as exc:
            self._log.debug("KB init failed (skipping): %s", exc)
            return None

    async def _run_gap_followup(
        self,
        follow_up_queries: list[str],
        enabled_sources: list[str],
        max_per_source: int,
        aggregator: ResultAggregator,
        instructions: str,
        output_schema: dict,
        topic: str,
        intent: str,
    ) -> list[dict]:
        """Second-pass collection on detected gaps, with optional cleaning."""
        gap_sources = [s for s in enabled_sources if s in ("web", "academic", "news", "pdf")]
        if not gap_sources:
            gap_sources = ["web"]
        dispatcher = CollectorDispatcher(config=self._config, log=self._log, emit_fn=self._emit)
        tasks = [
            asyncio.create_task(dispatcher.dispatch(src, follow_up_queries, max_per_source))
            for src in gap_sources
        ]
        all_batches = await asyncio.gather(*tasks, return_exceptions=True)
        batches = [b for b in all_batches if isinstance(b, list) and b]
        extra_raw = await aggregator.aggregate(batches)
        if not extra_raw or not instructions:
            return extra_raw
        try:
            from aria.engine.utils.retry import with_retry
            timeout = float(getattr(self._config, "llm_timeout_seconds", 60.0))
            max_attempts = int(getattr(self._config, "llm_retry_max_attempts", 3))
            base_delay = float(getattr(self._config, "llm_retry_base_delay", 1.0))
            max_delay = float(getattr(self._config, "llm_retry_max_delay", 20.0))

            cleaner = LLMCleaner(config=self._config, logger=self._log)

            async def _attempt_clean() -> list[dict]:
                return await asyncio.wait_for(
                    cleaner.clean_batch(extra_raw, instructions, output_schema),
                    timeout=timeout,
                )

            extra_clean = await with_retry(
                _attempt_clean,
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
            )
            return _score_documents(extra_clean, topic, intent, self._log)
        except Exception as exc:
            self._log.debug("Gap follow-up cleaning failed: %s", exc)
            return extra_raw

    # ------------------------------------------------------------------
    # Thin collector wrappers — delegate to CollectorDispatcher.
    # These exist so external callers that reference _collect_* methods
    # by name (e.g. tests, department_runner) continue to work.
    # ------------------------------------------------------------------

    async def _collect_via_dispatcher(self, source_name: str, queries: list[str], max_per_source: int) -> list[dict]:
        dispatcher = CollectorDispatcher(config=self._config, log=self._log, emit_fn=self._emit)
        return await dispatcher.dispatch(source_name, queries, max_per_source)

    async def _collect_crossref(self, queries: list[str], max_per_source: int) -> list[dict]:
        return await self._collect_via_dispatcher("crossref", queries, max_per_source)

    async def _collect_core_ac(self, queries: list[str], max_per_source: int) -> list[dict]:
        return await self._collect_via_dispatcher("core_ac", queries, max_per_source)

    async def _collect_europe_pmc(self, queries: list[str], max_per_source: int) -> list[dict]:
        return await self._collect_via_dispatcher("europe_pmc", queries, max_per_source)

    async def _collect_ssrn(self, queries: list[str], max_per_source: int) -> list[dict]:
        return await self._collect_via_dispatcher("ssrn", queries, max_per_source)

    async def _collect_base_search(self, queries: list[str], max_per_source: int) -> list[dict]:
        return await self._collect_via_dispatcher("base_search", queries, max_per_source)

    async def _collect_wikidata(self, queries: list[str], max_per_source: int) -> list[dict]:
        return await self._collect_via_dispatcher("wikidata", queries, max_per_source)

    async def _collect_internet_archive(self, queries: list[str], max_per_source: int) -> list[dict]:
        return await self._collect_via_dispatcher("internet_archive", queries, max_per_source)

    async def _collect_propublica(self, queries: list[str], max_per_source: int) -> list[dict]:
        return await self._collect_via_dispatcher("propublica", queries, max_per_source)

    async def _collect_mastodon(self, queries: list[str], max_per_source: int) -> list[dict]:
        return await self._collect_via_dispatcher("mastodon", queries, max_per_source)

    async def _emit(self, stage: str, message: str, **data: Any) -> None:
        self._log.info("[%s] %s", stage, message)
        if self._event_callback:
            try:
                payload = {"stage": stage, "message": message, **data}
                result = self._event_callback(payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                self._log.debug("Event callback error: %s", exc)


def _count_by_platform(docs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for doc in docs:
        platform = doc.get("platform", "unknown")
        counts[platform] = counts.get(platform, 0) + 1
    return counts


# Re-exported from phase modules for backwards compatibility
# _heuristic_plan, _flatten_plan_queries → planning.py
# _content_fingerprint → dedup.py

# Alias so `from aria.engine.orchestrator.core import MasterOrchestrator` works
MasterOrchestrator = InfoCollectorOrchestrator
