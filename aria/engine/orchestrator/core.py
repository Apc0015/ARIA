"""Core orchestration engine: coordinates collection, cleaning, and export."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}"
    r"|sk-ant-[A-Za-z0-9_-]{20,}"
    r"|Bearer\s+[A-Za-z0-9._~+/-]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|[A-Za-z0-9_-]{40,})",
    re.IGNORECASE,
)


def _scrub(msg: str) -> str:
    return _SECRET_RE.sub("[REDACTED]", msg)

from aria.engine.cleaner.llm_cleaner import LLMCleaner
from aria.engine.memory.shared_memory import SharedMemory
from aria.engine.output.exporter import Exporter
from aria.engine.output.report import generate_report
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
        self._known_urls = known_urls or set()  # KB-known URLs to skip

    async def aggregate(self, collector_results: list[list[dict]]) -> list[dict]:
        """Flatten, deduplicate, and return a unified document list."""
        unique_docs: list[dict] = []

        for batch in collector_results:
            if not batch:
                continue
            for doc in batch:
                url = doc.get("url", "")
                text = doc.get("text", "")

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
    ) -> None:
        self._config = config
        self._log = logger or logging.getLogger("aria")
        self._event_callback = event_callback

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
    ) -> RunResult:
        """Execute a full research collection run."""
        run_id = str(uuid.uuid4())[:8]
        topic = mission.get("collection", {}).get("topic", "research")
        await self._emit("init", f"Starting run {run_id}", run_id=run_id, topic=topic)

        # Setup directories
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
    ) -> RunResult:
        """Inner pipeline body — separated so the outer run() can catch & mark failures."""
        _pipeline_start = datetime.now(timezone.utc)
        raw_store = RawStore(run_dir / "raw")
        clean_store = CleanStore(run_dir / "clean")
        export_dir = run_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        shared_memory = SharedMemory(
            backend=self._config.shared_memory_backend,
            redis_url=self._config.redis_url,
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
                    domain_plan = await build_collection_plan(
                        query=topic or intent,
                        domains=domains_cfg,
                        countries=countries_cfg or None,
                    )
                    mission = dict(mission)
                    mission["_domain_plan"] = domain_plan
                except Exception as exc:
                    self._log.debug("Auto domain plan failed (falling back to standard): %s", exc)

        # ── Research Director phased path ─────────────────────────────────────
        research_brief = mission.get("_research_brief")  # set by API when director was used

        if research_brief:
            # Brief already built by director — use its queries and override topic
            resolved = research_brief.get("resolved_topic") or topic
            topic = resolved
            sub_questions = research_brief.get("key_questions", [])
            # Flatten phase queries into the legacy query_plan shape for stats/export
            all_phase_queries: list[str] = []
            for ph in research_brief.get("phases", []):
                all_phase_queries.extend(ph.get("queries", []))
            queries = list(dict.fromkeys(all_phase_queries))[:20]  # dedupe, cap
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

        kb = self._init_kb()
        known_urls: set[str] = set()
        if kb and not clean_only:
            known_urls = kb.get_known_urls_for_topic(topic)
            if known_urls:
                await self._emit(
                    "kb_lookup",
                    f"KB: skipping {len(known_urls)} already-collected URLs",
                )

        aggregator = ResultAggregator(shared_memory, known_urls=known_urls)

        raw_docs: list[dict] = []

        if clean_only:
            await self._emit("skip_collection", "clean_only=True, loading existing raw docs")
            raw_docs = raw_store.load()
            if not raw_docs:
                await self._emit("warning", "No raw docs found; running collection anyway")
                clean_only = False

        if not clean_only:
            domain_plan = mission.get("_domain_plan")

            if domain_plan is not None:
                # ARIA 5.0 domain-plan path
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
                await self._emit("collect_done", f"Collected {len(raw_docs)} unique documents (domain plan)")

            elif research_brief and research_brief.get("phases"):
                # Research Director phased collection path
                raw_docs = await self._run_phased_collection(
                    phases=research_brief["phases"],
                    max_per_source=max_per_source,
                    max_docs=max_docs,
                    mission=mission,
                    aggregator=aggregator,
                    authenticated_only=authenticated_only,
                    public_only=public_only,
                    credentials_path=credentials_path,
                )
                raw_store.save(raw_docs)

            else:
                enabled_sources = collection_cfg.get("sources", {}).get("enabled", ["web", "pdf", "academic"])
                await self._emit("collect", f"Starting collectors: {enabled_sources}")

                collector_tasks = await self._run_collectors(
                    queries=queries,
                    enabled_sources=enabled_sources,
                    max_per_source=max_per_source,
                    mission=mission,
                    authenticated_only=authenticated_only,
                    public_only=public_only,
                    credentials_path=credentials_path,
                )

                all_batches = await asyncio.gather(*collector_tasks, return_exceptions=True)
                batches: list[list[dict]] = []
                for b in all_batches:
                    if isinstance(b, Exception):
                        self._log.warning("Collector task failed: %s", _scrub(str(b)))
                    elif b:
                        batches.append(b)

                llm_cfg = mission.get("llm_sources", {})
                if llm_cfg.get("enabled", False) and not authenticated_only:
                    llm_docs = await self._run_llm_sources(mission, queries)
                    if llm_docs:
                        batches.append(llm_docs)
                        await self._emit("llm_sources", f"LLM sources: {len(llm_docs)} documents")

                raw_docs = await aggregator.aggregate(batches)

                if self._config.semantic_dedup_enabled:
                    raw_docs = await self._semantic_dedup(raw_docs)

                raw_docs = raw_docs[:max_docs]
                raw_store.save(raw_docs)
                await self._emit("collect_done", f"Collected {len(raw_docs)} unique documents")

        source_stats = _count_by_platform(raw_docs)

        clean_docs: list[dict] = []

        if collect_only:
            await self._emit("skip_clean", "collect_only=True, skipping cleaning")
            clean_docs = raw_docs
        else:
            cleaning_cfg = mission.get("cleaning", {})
            instructions = cleaning_cfg.get("instructions", "Extract key information.")
            output_schema = cleaning_cfg.get("output_schema", {})

            await self._emit("clean", f"Cleaning {len(raw_docs)} documents with LLM...")
            cleaner = LLMCleaner(config=self._config, logger=self._log)
            clean_docs = await cleaner.clean_batch(raw_docs, instructions, output_schema)
            await self._emit("clean_done", f"Cleaned {len(clean_docs)} documents")

        await self._emit("score", "Scoring document relevance...")
        clean_docs = self._score_documents(clean_docs, topic, intent)

        output_cfg = mission.get("output", {})
        sort_by = output_cfg.get("sort_by", "relevance_score")
        sort_order = output_cfg.get("sort_order", "desc")
        if sort_by:
            clean_docs = sorted(
                clean_docs,
                key=lambda d: d.get(sort_by, 0) or 0,
                reverse=(sort_order == "desc"),
            )

        clean_store.save(clean_docs)

        gap_result: dict = {}
        if (
            self._config.gap_detection_enabled
            and not collect_only
            and clean_docs
        ):
            await self._emit("gap_detect", "Detecting research gaps...")
            gap_result = await self._detect_gaps(clean_docs, topic, intent, sub_questions)

            if gap_result.get("has_gaps") and gap_result.get("follow_up_queries"):
                follow_ups = gap_result["follow_up_queries"]
                await self._emit(
                    "gap_detect",
                    f"Found {len(gap_result['gaps'])} gaps — running follow-up collection "
                    f"({len(follow_ups)} queries)",
                )
                extra_docs = await self._gap_followup_collection(
                    follow_up_queries=follow_ups,
                    enabled_sources=collection_cfg.get("sources", {}).get("enabled", ["web", "academic"]),
                    max_per_source=max(5, max_per_source // 3),
                    mission=mission,
                    aggregator=aggregator,
                    cleaner_cfg=(instructions, output_schema) if not collect_only else ("", {}),
                    topic=topic,
                    intent=intent,
                )
                if extra_docs:
                    clean_docs.extend(extra_docs)
                    # Re-sort
                    clean_docs = sorted(
                        clean_docs,
                        key=lambda d: d.get(sort_by, 0) or 0,
                        reverse=(sort_order == "desc"),
                    )
                    clean_store.save(clean_docs)
                    await self._emit("gap_done", f"Added {len(extra_docs)} docs from gap follow-up")

        kg_data: dict = {}
        if (
            self._config.knowledge_graph_enabled
            and not collect_only
            and clean_docs
        ):
            await self._emit("knowledge_graph", "Building knowledge graph...")
            kg_data = await self._build_knowledge_graph(clean_docs, topic)
            contradictions = kg_data.get("contradictions", [])
            await self._emit(
                "knowledge_graph",
                f"Graph: {kg_data.get('total_entities', 0)} entities, "
                f"{len(contradictions)} contradictions",
                has_contradictions=bool(contradictions),
            )

        images: list[dict] = []
        if self._config.image_extraction_enabled and clean_docs:
            images = self._extract_images(clean_docs, topic)
            if images:
                await self._emit("images", f"Extracted {len(images)} images")

        if kb and clean_docs:
            added, skipped = kb.add_documents_batch(clean_docs, topic=topic, run_id=run_id)
            await self._emit("kb_save", f"KB: saved {added} new docs ({skipped} already known)")

        formats = output_cfg.get("formats", ["json", "csv", "markdown"])
        await self._emit("export", f"Exporting in formats: {formats}")
        exporter = Exporter(export_dir)
        export_paths = exporter.export_all(
            raw_docs=raw_docs,
            clean_docs=clean_docs,
            formats=formats,
            topic=topic,
        )
        if kg_data:
            try:
                import json
                kg_path = export_dir / "knowledge_graph.json"
                kg_path.write_text(json.dumps(kg_data, indent=2, default=str))
                export_paths["knowledge_graph"] = str(kg_path)
            except Exception:
                pass

        if images:
            try:
                import json
                img_path = export_dir / "images.json"
                img_path.write_text(json.dumps(images, indent=2, default=str))
                export_paths["images"] = str(img_path)
            except Exception:
                pass

        await self._emit("export_done", "Export complete", paths=export_paths)

        relevant_count = sum(1 for d in clean_docs if d.get("is_relevant", True))
        stats = {
            "collected": len(raw_docs),
            "cleaned": len(clean_docs),
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
        # ── Build collection methodology record ───────────────────────────
        _pipeline_end = datetime.now(timezone.utc)
        domain_plan = mission.get("_domain_plan")
        _method = "domain_plan" if domain_plan else "standard"
        _domains = list(domain_plan.intent.domains) if domain_plan else collection_cfg.get("domains", [])
        _countries = list(domain_plan.intent.countries) if domain_plan else collection_cfg.get("countries", [])
        _sources_used = list(domain_plan.active_collectors) if domain_plan else collection_cfg.get("sources", {}).get("enabled", [])
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
            "cleaning_method": "llm" if _provider != "unknown" else "fallback",
            "dedup_method": " + ".join(_dedup_parts),
            "started_at": _pipeline_start.isoformat(),
            "completed_at": _pipeline_end.isoformat(),
            "duration_seconds": (_pipeline_end - _pipeline_start).total_seconds(),
        }

        await self._emit("report", "Generating HTML report...")
        report_path = generate_report(
            documents=clean_docs,
            topic=topic,
            output_dir=export_dir,
            stats=stats,
            knowledge_graph=kg_data or None,
            gap_analysis=gap_result or None,
            images=images or None,
            methodology=methodology,
        )
        await self._emit("done", "Run complete", stats=stats)

        return RunResult(
            run_id=run_id,
            stats=stats,
            raw_documents=raw_docs,
            clean_documents=clean_docs,
            export_paths={k: str(v) for k, v in export_paths.items()},
            report_path=str(report_path),
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
                return await plan_queries(topic, intent)
            except Exception as exc:
                self._log.debug("Smart query planner failed: %s", exc)
        # Heuristic fallback — build minimal plan
        return _heuristic_plan(topic, intent)

    def _init_kb(self):
        """Init persistent knowledge base. Returns None if disabled."""
        if not self._config.kb_enabled:
            return None
        try:
            from aria.engine.knowledge_base.kb import KnowledgeBase
            kb_path = self._config.kb_path
            return KnowledgeBase(db_path=kb_path)
        except Exception as exc:
            self._log.debug("KB init failed (skipping): %s", exc)
            return None

    async def _semantic_dedup(self, docs: list[dict]) -> list[dict]:
        """Apply MinHash + embedding semantic deduplication."""
        try:
            from aria.engine.intelligence.semantic_dedup import SemanticDeduplicator
            dedup = SemanticDeduplicator()
            unique, removed = dedup.filter_documents(docs)
            if removed:
                await self._emit("dedup", f"Semantic dedup removed {removed} duplicate documents")
            return unique
        except Exception as exc:
            self._log.debug("Semantic dedup failed (using raw list): %s", exc)
            return docs

    def _score_documents(
        self, docs: list[dict], topic: str, intent: str
    ) -> list[dict]:
        """Annotate docs with multi-dimensional relevance scores."""
        try:
            from aria.engine.intelligence.relevance_scorer import score_and_annotate
            return score_and_annotate(docs, topic, intent)
        except Exception as exc:
            self._log.debug("Relevance scoring failed: %s", exc)
            return docs

    async def _detect_gaps(
        self,
        docs: list[dict],
        topic: str,
        intent: str,
        sub_questions: list[str],
    ) -> dict:
        """Run gap detector against collected docs."""
        try:
            from aria.engine.intelligence.gap_detector import detect_gaps
            return await detect_gaps(
                docs=docs,
                topic=topic,
                intent=intent,
                sub_questions=sub_questions,
            )
        except Exception as exc:
            self._log.debug("Gap detection failed: %s", exc)
            return {}

    async def _gap_followup_collection(
        self,
        follow_up_queries: list[str],
        enabled_sources: list[str],
        max_per_source: int,
        mission: dict,
        aggregator: ResultAggregator,
        cleaner_cfg: tuple[str, dict],
        topic: str,
        intent: str,
    ) -> list[dict]:
        """Run a second collection pass with gap follow-up queries."""
        # Limit sources for follow-up (faster: web + academic only)
        gap_sources = [s for s in enabled_sources if s in ("web", "academic", "news", "pdf")]
        if not gap_sources:
            gap_sources = ["web"]

        tasks = await self._run_collectors(
            queries=follow_up_queries,
            enabled_sources=gap_sources,
            max_per_source=max_per_source,
            mission=mission,
            authenticated_only=False,
            public_only=True,
            credentials_path=None,
        )
        all_batches = await asyncio.gather(*tasks, return_exceptions=True)
        batches = [b for b in all_batches if isinstance(b, list) and b]
        extra_raw = await aggregator.aggregate(batches)

        if not extra_raw or not cleaner_cfg[0]:
            return extra_raw

        try:
            instructions, output_schema = cleaner_cfg
            cleaner = LLMCleaner(config=self._config, logger=self._log)
            extra_clean = await cleaner.clean_batch(extra_raw, instructions, output_schema)
            return self._score_documents(extra_clean, topic, intent)
        except Exception as exc:
            self._log.debug("Gap follow-up cleaning failed: %s", exc)
            return extra_raw

    async def _build_knowledge_graph(
        self, docs: list[dict], topic: str
    ) -> dict:
        """Build knowledge graph from documents."""
        try:
            from aria.engine.intelligence.knowledge_graph import KnowledgeGraph
            kg = KnowledgeGraph()
            await kg.build_from_documents(docs, topic, max_docs_to_extract=80)
            self._log.info(kg.summary())
            return kg.to_dict()
        except Exception as exc:
            self._log.debug("Knowledge graph failed: %s", exc)
            return {}

    def _extract_images(self, docs: list[dict], topic: str) -> list[dict]:
        """Extract images from collected documents."""
        try:
            from aria.engine.intelligence.image_extractor import extract_images_from_docs
            return extract_images_from_docs(docs, max_total=50, max_per_doc=5)
        except Exception as exc:
            self._log.debug("Image extraction failed: %s", exc)
            return []

    async def _run_phased_collection(
        self,
        phases: list[dict],
        max_per_source: int,
        max_docs: int,
        mission: dict,
        aggregator: "ResultAggregator",
        authenticated_only: bool,
        public_only: bool,
        credentials_path: Optional[str],
    ) -> list[dict]:
        """Run phased collection: landscape → deep_dive → critical → latest."""
        all_docs: list[dict] = []
        phase_cap = max_docs // max(1, len(phases))  # spread cap across phases

        for phase in phases:
            name = phase.get("name", "phase")
            goal = phase.get("goal", "")
            queries = phase.get("queries", [])
            source_types = phase.get("source_types", ["web", "academic"])
            phase_max = phase.get("max_docs", phase_cap)

            await self._emit(
                "phase_start",
                f"[{name}] {goal}",
                phase=name,
                queries=queries,
                sources=source_types,
            )

            if not queries:
                await self._emit("phase_done", f"[{name}] No queries — skipping", phase=name)
                continue

            tasks = await self._run_collectors(
                queries=queries,
                enabled_sources=source_types,
                max_per_source=max(5, min(max_per_source, phase_max // max(1, len(source_types)))),
                mission=mission,
                authenticated_only=authenticated_only,
                public_only=public_only,
                credentials_path=credentials_path,
            )

            all_batches = await asyncio.gather(*tasks, return_exceptions=True)
            batches: list[list[dict]] = []
            for b in all_batches:
                if isinstance(b, Exception):
                    self._log.warning("[%s] Collector error: %s", name, _scrub(str(b)))
                elif b:
                    batches.append(b)

            phase_docs = await aggregator.aggregate(batches)
            phase_docs = phase_docs[:phase_max]

            for doc in phase_docs:
                doc["_phase"] = name  # tag for reporting

            all_docs.extend(phase_docs)
            await self._emit(
                "phase_done",
                f"[{name}] {len(phase_docs)} docs",
                phase=name,
                count=len(phase_docs),
                total_so_far=len(all_docs),
            )

            if len(all_docs) >= max_docs:
                break

        await self._emit("collect_done", f"Phased collection: {len(all_docs)} total docs across {len(phases)} phases")
        return all_docs[:max_docs]

    # ------------------------------------------------------------------
    # Collectors
    # ------------------------------------------------------------------

    async def _run_collectors(
        self,
        queries: list[str],
        enabled_sources: list[str],
        max_per_source: int,
        mission: dict,
        authenticated_only: bool,
        public_only: bool,
        credentials_path: Optional[str],
    ) -> list[asyncio.Task]:
        """Build and start collector coroutines for all enabled sources."""
        tasks = []

        source_map = {
            "web":                self._collect_web,
            "pdf":                self._collect_pdf,
            "academic":           self._collect_academic,
            "youtube":            self._collect_youtube,
            "reddit":             self._collect_reddit,
            "hackernews":         self._collect_hackernews,
            "wikipedia":          self._collect_wikipedia,
            "stackoverflow":      self._collect_stackoverflow,
            "medium":             self._collect_medium,
            "devto":              self._collect_devto,
            "substack":           self._collect_substack,
            "rss":                self._collect_rss,
            "twitter":            self._collect_twitter,
            "linkedin":           self._collect_linkedin,
            "slack":              self._collect_slack,
            "zotero":             self._collect_zotero,
            "notion":             self._collect_notion,
            "podcast":            self._collect_podcast,
            "vimeo":              self._collect_vimeo,
            "github":             self._collect_github,
            "government":         self._collect_government,
            "multilingual":       self._collect_multilingual,
            "news":               self._collect_news,
            "academic_platforms": self._collect_academic_platforms,
            # ARIA 5.0 new collectors
            "world_bank":         self._collect_world_bank,
            "un_data":            self._collect_un_data,
            "who":                self._collect_who,
            "imf":                self._collect_imf,
            "fred":               self._collect_fred,
            "open_alex":          self._collect_open_alex,
            "gdelt":              self._collect_gdelt,
            "clinical_trials":    self._collect_clinical_trials,
            "jobs_boards":        self._collect_jobs_boards,
            "intl_gov":           self._collect_intl_gov,
            "sec_edgar":          self._collect_sec_edgar,
            "eurostat":           self._collect_eurostat,
        }

        for source_name in enabled_sources:
            if source_name not in source_map:
                self._log.debug("Unknown source: %s, skipping", source_name)
                continue
            coro = source_map[source_name](queries, max_per_source)
            tasks.append(asyncio.create_task(coro))

        return tasks

    async def _run_llm_sources(self, mission: dict, queries: list[str]) -> list[dict]:
        from aria.engine.ensemble.agent import LLMEnsembleAgent
        llm_cfg = mission.get("llm_sources", {})
        models = llm_cfg.get("models", [])
        if not models:
            from aria.engine.ensemble.providers import default_llm_source_models
            models = default_llm_source_models(self._config)

        agent = LLMEnsembleAgent(models=models)
        return await agent.collect(queries[:3])

    async def _collect_web(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.web.search import WebSearchCollector
        collector = WebSearchCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Web collector error: %s", exc)
        await self._emit("source_done", f"Web search: {len(docs)} docs")
        return docs

    async def _collect_pdf(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.web.pdf import PDFCollector
        collector = PDFCollector(max_results=max(3, max_per_source // 3))
        docs = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("PDF collector error: %s", exc)
        await self._emit("source_done", f"PDF: {len(docs)} docs")
        return docs

    async def _collect_academic(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.academic.core import AcademicCollector
        collector = AcademicCollector(max_per_source=max(5, max_per_source // 3))
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Academic collector error: %s", exc)
        await self._emit("source_done", f"Academic: {len(docs)} docs")
        return docs

    async def _collect_youtube(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.media.youtube import YouTubeCollector
        collector = YouTubeCollector(max_results=max(3, max_per_source // 3))
        docs = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("YouTube collector error: %s", exc)
        await self._emit("source_done", f"YouTube: {len(docs)} docs")
        return docs

    async def _collect_reddit(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.web.reddit import RedditCollector
        collector = RedditCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Reddit collector error: %s", exc)
        await self._emit("source_done", f"Reddit: {len(docs)} docs")
        return docs

    async def _collect_hackernews(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.web.hackernews import HackerNewsCollector
        collector = HackerNewsCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("HackerNews collector error: %s", exc)
        await self._emit("source_done", f"HackerNews: {len(docs)} docs")
        return docs

    async def _collect_wikipedia(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.web.wikipedia import WikipediaCollector
        collector = WikipediaCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Wikipedia collector error: %s", exc)
        await self._emit("source_done", f"Wikipedia: {len(docs)} docs")
        return docs

    async def _collect_stackoverflow(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.web.stackoverflow import StackOverflowCollector
        collector = StackOverflowCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("StackOverflow collector error: %s", exc)
        await self._emit("source_done", f"StackOverflow: {len(docs)} docs")
        return docs

    async def _collect_medium(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.web.medium import MediumCollector
        collector = MediumCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Medium collector error: %s", exc)
        await self._emit("source_done", f"Medium: {len(docs)} docs")
        return docs

    async def _collect_devto(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.web.devto import DevToCollector
        collector = DevToCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("DevTo collector error: %s", exc)
        await self._emit("source_done", f"dev.to: {len(docs)} docs")
        return docs

    async def _collect_substack(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.web.substack import SubstackCollector
        collector = SubstackCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Substack collector error: %s", exc)
        await self._emit("source_done", f"Substack: {len(docs)} docs")
        return docs

    async def _collect_rss(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.web.rss import RSSCollector
        collector = RSSCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("RSS collector error: %s", exc)
        await self._emit("source_done", f"RSS: {len(docs)} docs")
        return docs

    async def _collect_twitter(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.social.twitter import TwitterCollector
        collector = TwitterCollector()
        docs = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Twitter collector error: %s", exc)
        await self._emit("source_done", f"Twitter: {len(docs)} docs")
        return docs

    async def _collect_linkedin(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.social.linkedin import LinkedInCollector
        collector = LinkedInCollector()
        docs = []
        try:
            async for doc in collector.collect(queries):
                docs.append(doc)
        except Exception as exc:
            self._log.warning("LinkedIn collector error: %s", exc)
        await self._emit("source_done", f"LinkedIn: {len(docs)} docs")
        return docs

    async def _collect_slack(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.social.slack import SlackCollector
        collector = SlackCollector()
        docs = []
        try:
            async for doc in collector.collect(queries):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Slack collector error: %s", exc)
        await self._emit("source_done", f"Slack: {len(docs)} docs")
        return docs

    async def _collect_zotero(self, queries: list[str], max_per_source: int) -> list[dict]:
        import os
        from aria.engine.collectors.knowledge.zotero import ZoteroCollector
        mode = (os.getenv("ZOTERO_MODE") or "").strip().lower()
        if mode not in {"local", "cloud"}:
            mode = "cloud" if os.getenv("ZOTERO_API_KEY") else "local"
        library_type = (os.getenv("ZOTERO_LIBRARY_TYPE") or "user").strip().lower()
        if library_type not in {"user", "group"}:
            library_type = "user"
        collector = ZoteroCollector(
            mode=mode,
            library_id=os.getenv("ZOTERO_LIBRARY_ID") or None,
            api_key=os.getenv("ZOTERO_API_KEY") or None,
            library_type=library_type,
            max_items=max_per_source,
        )
        docs = []
        try:
            async for doc in collector.collect(queries):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Zotero collector error: %s", exc)
        await self._emit("source_done", f"Zotero: {len(docs)} docs ({mode})")
        return docs

    async def _collect_notion(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.knowledge.notion import NotionCollector
        collector = NotionCollector()
        docs = []
        try:
            async for doc in collector.collect(queries):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Notion collector error: %s", exc)
        await self._emit("source_done", f"Notion: {len(docs)} docs")
        return docs

    async def _collect_podcast(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.media.podcast import PodcastCollector
        collector = PodcastCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Podcast collector error: %s", exc)
        await self._emit("source_done", f"Podcast: {len(docs)} docs")
        return docs

    async def _collect_vimeo(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.media.vimeo import VimeoCollector
        collector = VimeoCollector()
        docs = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Vimeo collector error: %s", exc)
        await self._emit("source_done", f"Vimeo: {len(docs)} docs")
        return docs

    async def _collect_github(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.knowledge.github import GitHubCollector
        collector = GitHubCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("GitHub collector error: %s", exc)
        await self._emit("source_done", f"GitHub: {len(docs)} docs")
        return docs

    async def _collect_government(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.specialized.government import GovernmentCollector
        collector = GovernmentCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Government collector error: %s", exc)
        await self._emit("source_done", f"Government: {len(docs)} docs")
        return docs

    async def _collect_multilingual(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.specialized.multilingual import MultilingualCollector
        collector = MultilingualCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Multilingual collector error: %s", exc)
        await self._emit("source_done", f"Multilingual: {len(docs)} docs")
        return docs

    async def _collect_news(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.specialized.news import NewsCollector
        collector = NewsCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("News collector error: %s", exc)
        await self._emit("source_done", f"News: {len(docs)} docs")
        return docs

    async def _collect_academic_platforms(
        self, queries: list[str], max_per_source: int
    ) -> list[dict]:
        from aria.engine.collectors.academic.core_platforms import AcademicPlatformsCollector
        collector = AcademicPlatformsCollector(max_results=max_per_source)
        if not await collector.validate():
            self._log.info(
                "AcademicPlatforms: no credentials set, skipping "
                "(set IEEE_API_KEY, ELSEVIER_API_KEY, SPRINGER_API_KEY, "
                "JSTOR_SESSION_COOKIE, or ACM_SESSION_COOKIE)"
            )
            return []
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("AcademicPlatforms collector error: %s", exc)
        await self._emit("source_done", f"AcademicPlatforms: {len(docs)} docs")
        return docs

    # ------------------------------------------------------------------
    # ARIA 5.0 new collectors
    # ------------------------------------------------------------------

    async def _collect_world_bank(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.data.world_bank import WorldBankCollector
        collector = WorldBankCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("WorldBank collector error: %s", exc)
        await self._emit("source_done", f"World Bank: {len(docs)} docs")
        return docs

    async def _collect_un_data(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.data.un_data import UNDataCollector
        collector = UNDataCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("UN Data collector error: %s", exc)
        await self._emit("source_done", f"UN Data: {len(docs)} docs")
        return docs

    async def _collect_who(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.data.who import WHOCollector
        collector = WHOCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("WHO collector error: %s", exc)
        await self._emit("source_done", f"WHO: {len(docs)} docs")
        return docs

    async def _collect_imf(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.data.imf import IMFCollector
        collector = IMFCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("IMF collector error: %s", exc)
        await self._emit("source_done", f"IMF: {len(docs)} docs")
        return docs

    async def _collect_fred(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.data.fred import FREDCollector
        collector = FREDCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("FRED collector error: %s", exc)
        await self._emit("source_done", f"FRED: {len(docs)} docs")
        return docs

    async def _collect_open_alex(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.academic.open_alex import OpenAlexCollector
        collector = OpenAlexCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:5]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("OpenAlex collector error: %s", exc)
        await self._emit("source_done", f"OpenAlex: {len(docs)} docs")
        return docs

    async def _collect_gdelt(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.data.gdelt import GDELTCollector
        collector = GDELTCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("GDELT collector error: %s", exc)
        await self._emit("source_done", f"GDELT: {len(docs)} docs")
        return docs

    async def _collect_clinical_trials(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.data.clinical_trials import ClinicalTrialsCollector
        collector = ClinicalTrialsCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("ClinicalTrials collector error: %s", exc)
        await self._emit("source_done", f"ClinicalTrials: {len(docs)} docs")
        return docs

    async def _collect_jobs_boards(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.specialized.jobs_boards import JobsBoardsCollector
        collector = JobsBoardsCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("JobsBoards collector error: %s", exc)
        await self._emit("source_done", f"Jobs Boards: {len(docs)} docs")
        return docs

    async def _collect_intl_gov(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.specialized.intl_gov import IntlGovCollector
        collector = IntlGovCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("IntlGov collector error: %s", exc)
        await self._emit("source_done", f"IntlGov: {len(docs)} docs")
        return docs

    async def _collect_sec_edgar(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.data.sec_edgar import SECEdgarCollector
        collector = SECEdgarCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("SEC EDGAR collector error: %s", exc)
        await self._emit("source_done", f"SEC EDGAR: {len(docs)} docs")
        return docs

    async def _collect_eurostat(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.data.eurostat import EurostatCollector
        collector = EurostatCollector(max_results=max_per_source)
        docs = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Eurostat collector error: %s", exc)
        await self._emit("source_done", f"Eurostat: {len(docs)} docs")
        return docs

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


def _content_fingerprint(text: str) -> str:
    sample = text.strip()[:500]
    combined = f"{len(text)}:{sample}"
    return hashlib.sha256(combined.encode()).hexdigest()


def _count_by_platform(docs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for doc in docs:
        platform = doc.get("platform", "unknown")
        counts[platform] = counts.get(platform, 0) + 1
    return counts


def _heuristic_plan(topic: str, intent: str) -> dict:
    """Minimal query plan without LLM."""
    t = topic.strip()
    year = datetime.now().year
    return {
        "sub_questions": [
            f"What is {t} and how does it work?",
            f"What are the main applications of {t}?",
            f"What are recent advances in {t} ({year})?",
            f"What are the limitations and challenges of {t}?",
            f"What does the research say about {t}?",
        ],
        "queries": {
            "general": [t, f"{t} explained", f"{t} overview", f"what is {t}"],
            "academic": [f"{t} research {year}", f"{t} study", f"{t} systematic review"],
            "technical": [f"{t} implementation", f"{t} architecture"],
            "news": [f"{t} news {year}", f"{t} latest"],
            "critical": [f"{t} limitations", f"{t} risks"],
            "policy": [f"{t} policy regulation"],
        },
        "source_priorities": {
            "academic": 9, "web": 8, "news": 7, "github": 6,
            "government": 5, "youtube": 4, "reddit": 3,
        },
        "entity_seeds": [],
    }


def _flatten_plan_queries(plan: dict, max_total: int = 20) -> list[str]:
    """Flatten plan queries dict → deduplicated list."""
    order = ["general", "academic", "technical", "news", "critical", "policy"]
    seen: set[str] = set()
    result: list[str] = []
    for category in order:
        for q in plan.get("queries", {}).get(category, []):
            q = q.strip()
            if q and q.lower() not in seen:
                seen.add(q.lower())
                result.append(q)
                if len(result) >= max_total:
                    return result
    return result
