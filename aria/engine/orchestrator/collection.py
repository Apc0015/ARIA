"""Collection phase — spawns collector tasks in parallel and aggregates results.

CollectorDispatcher owns all the _collect_* methods so core.py stays thin.
Each source entry in _COLLECTOR_REGISTRY maps to (import_path, class_name,
max_queries, label). The generic _run_source() handles the standard
instantiate → collect → cap → emit pattern.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable, Optional

logger = logging.getLogger("aria")


# ---------------------------------------------------------------------------
# Collector registry — (module_path, class_name, max_queries, label)
# max_queries: how many queries to pass to the collector (None = all)
# ---------------------------------------------------------------------------
_COLLECTOR_REGISTRY: dict[str, tuple[str, str, Optional[int], str]] = {
    # Web
    "web":                ("aria.engine.collectors.web.search",              "WebSearchCollector",        None, "Web search"),
    "pdf":                ("aria.engine.collectors.web.pdf",                 "PDFCollector",              3,    "PDF"),
    "reddit":             ("aria.engine.collectors.web.reddit",              "RedditCollector",           3,    "Reddit"),
    "hackernews":         ("aria.engine.collectors.web.hackernews",          "HackerNewsCollector",       3,    "HackerNews"),
    "wikipedia":          ("aria.engine.collectors.web.wikipedia",           "WikipediaCollector",        3,    "Wikipedia"),
    "stackoverflow":      ("aria.engine.collectors.web.stackoverflow",       "StackOverflowCollector",    4,    "StackOverflow"),
    "medium":             ("aria.engine.collectors.web.medium",              "MediumCollector",           3,    "Medium"),
    "devto":              ("aria.engine.collectors.web.devto",               "DevToCollector",            4,    "dev.to"),
    "substack":           ("aria.engine.collectors.web.substack",            "SubstackCollector",         None, "Substack"),
    "rss":                ("aria.engine.collectors.web.rss",                 "RSSCollector",              None, "RSS"),
    # Academic
    "academic":           ("aria.engine.collectors.academic.core",           "AcademicCollector",         4,    "Academic"),
    "arxiv":              ("aria.engine.collectors.academic.core",           "AcademicCollector",         4,    "arXiv"),
    "pubmed":             ("aria.engine.collectors.academic.core",           "AcademicCollector",         4,    "PubMed"),
    "semantic_scholar":   ("aria.engine.collectors.academic.core",           "AcademicCollector",         4,    "Semantic Scholar"),
    "open_alex":          ("aria.engine.collectors.academic.open_alex",      "OpenAlexCollector",         5,    "OpenAlex"),
    # Social
    "twitter":            ("aria.engine.collectors.social.twitter",          "TwitterCollector",          3,    "Twitter"),
    "slack":              ("aria.engine.collectors.social.slack",            "SlackCollector",            None, "Slack"),
    # Media
    "youtube":            ("aria.engine.collectors.media.youtube",           "YouTubeCollector",          3,    "YouTube"),
    "vimeo":              ("aria.engine.collectors.media.vimeo",             "VimeoCollector",            3,    "Vimeo"),
    "podcast":            ("aria.engine.collectors.media.podcast",           "PodcastCollector",          None, "Podcast"),
    # Knowledge
    "notion":             ("aria.engine.collectors.knowledge.notion",        "NotionCollector",           None, "Notion"),
    "github":             ("aria.engine.collectors.knowledge.github",        "GitHubCollector",           4,    "GitHub"),
    "zotero":             ("aria.engine.collectors.knowledge.zotero",        "ZoteroCollector",           None, "Zotero"),
    # Specialized
    "government":         ("aria.engine.collectors.specialized.government",  "GovernmentCollector",       4,    "Government"),
    "multilingual":       ("aria.engine.collectors.specialized.multilingual","MultilingualCollector",     3,    "Multilingual"),
    "news":               ("aria.engine.collectors.specialized.news",        "NewsCollector",             4,    "News"),
    "jobs_boards":        ("aria.engine.collectors.specialized.jobs_boards", "JobsBoardsCollector",       4,    "Jobs Boards"),
    "intl_gov":           ("aria.engine.collectors.specialized.intl_gov",    "IntlGovCollector",          4,    "IntlGov"),
    # Data & Statistics
    "world_bank":         ("aria.engine.collectors.data.world_bank",         "WorldBankCollector",        4,    "World Bank"),
    "un_data":            ("aria.engine.collectors.data.un_data",            "UNDataCollector",           4,    "UN Data"),
    "who":                ("aria.engine.collectors.data.who",                "WHOCollector",              4,    "WHO"),
    "imf":                ("aria.engine.collectors.data.imf",                "IMFCollector",              3,    "IMF"),
    "fred":               ("aria.engine.collectors.data.fred",               "FREDCollector",             3,    "FRED"),
    "gdelt":              ("aria.engine.collectors.data.gdelt",              "GDELTCollector",            4,    "GDELT"),
    "clinical_trials":    ("aria.engine.collectors.data.clinical_trials",    "ClinicalTrialsCollector",   4,    "ClinicalTrials"),
    "sec_edgar":          ("aria.engine.collectors.data.sec_edgar",          "SECEdgarCollector",         3,    "SEC EDGAR"),
    "eurostat":           ("aria.engine.collectors.data.eurostat",           "EurostatCollector",         3,    "Eurostat"),
    "internet_archive":   ("aria.engine.collectors.data.internet_archive",   "InternetArchiveCollector",  3,    "Internet Archive"),
    # Academic (new)
    "crossref":           ("aria.engine.collectors.academic.crossref",       "CrossRefCollector",         4,    "CrossRef"),
    "core_ac":            ("aria.engine.collectors.academic.core_ac",        "CoreAcCollector",           4,    "CORE AC"),
    "europe_pmc":         ("aria.engine.collectors.academic.europe_pmc",     "EuropePMCCollector",        4,    "Europe PMC"),
    "ssrn":               ("aria.engine.collectors.academic.ssrn",           "SSRNCollector",             3,    "SSRN"),
    "base_search":        ("aria.engine.collectors.academic.base_search",    "BaseSearchCollector",       4,    "BASE Search"),
    # Knowledge (new)
    "wikidata":           ("aria.engine.collectors.knowledge.wikidata",      "WikidataCollector",         3,    "Wikidata"),
    # Specialized (new)
    "propublica":         ("aria.engine.collectors.specialized.propublica",  "ProPublicaCollector",       4,    "ProPublica"),
    # Social (new)
    "mastodon":           ("aria.engine.collectors.social.mastodon",         "MastodonCollector",         3,    "Mastodon"),
}


class CollectorDispatcher:
    """Instantiates and runs collectors; owns all source-specific logic.

    The generic _run_source() handles the standard boilerplate:
      import class → instantiate → collect with cap → emit "source_done".
    Special-cased sources (zotero, academic_platforms) have their own methods.
    """

    def __init__(
        self,
        config: Any,
        log: Optional[logging.Logger] = None,
        emit_fn: Optional[Callable] = None,
    ) -> None:
        self._config = config
        self._log = log or logger
        self._emit_fn = emit_fn

    async def _emit(self, stage: str, msg: str, **kw: Any) -> None:
        if self._emit_fn:
            await self._emit_fn(stage, msg, **kw)

    async def _run_source(
        self,
        source_name: str,
        queries: list[str],
        max_per_source: int,
        *,
        ctor_kwargs: Optional[dict] = None,
    ) -> list[dict]:
        """Generic collect: import → instantiate → iterate → cap → emit."""
        entry = _COLLECTOR_REGISTRY.get(source_name)
        if not entry:
            self._log.debug("Unknown source: %s", source_name)
            return []
        module_path, class_name, max_q, label = entry
        import importlib
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
        except Exception as exc:
            self._log.debug("Cannot import %s.%s: %s", module_path, class_name, exc)
            return []

        kwargs = ctor_kwargs or {}
        if "max_results" in cls.__init__.__code__.co_varnames:
            kwargs.setdefault("max_results", max_per_source)
        elif "max_per_source" in cls.__init__.__code__.co_varnames:
            kwargs.setdefault("max_per_source", max_per_source)
        collector = cls(**kwargs)

        from datetime import datetime, timezone
        effective_queries = queries[:max_q] if max_q else queries
        docs: list[dict] = []
        try:
            async for doc in collector.collect(effective_queries):
                # Attach provenance so every document has a full audit trail
                if "_provenance" not in doc:
                    doc["_provenance"] = {
                        "collector": source_name,
                        "collector_label": label,
                        "queries_used": effective_queries,
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                    }
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("%s collector error: %s", label, exc)
        await self._emit("source_done", f"{label}: {len(docs)} docs")
        return docs

    async def dispatch(
        self,
        source_name: str,
        queries: list[str],
        max_per_source: int,
    ) -> list[dict]:
        """Route a source name to the correct collector method."""
        if source_name == "zotero":
            return await self._collect_zotero(queries, max_per_source)
        if source_name == "academic_platforms":
            return await self._collect_academic_platforms(queries, max_per_source)
        return await self._run_source(source_name, queries, max_per_source)

    # ------------------------------------------------------------------
    # Special-cased collectors (require env-var logic or validate() check)
    # ------------------------------------------------------------------

    async def _collect_zotero(self, queries: list[str], max_per_source: int) -> list[dict]:
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
        docs: list[dict] = []
        try:
            async for doc in collector.collect(queries[:3]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("Zotero collector error: %s", exc)
        await self._emit("source_done", f"Zotero: {len(docs)} docs ({mode})")
        return docs

    async def _collect_academic_platforms(self, queries: list[str], max_per_source: int) -> list[dict]:
        from aria.engine.collectors.academic.core_platforms import AcademicPlatformsCollector
        collector = AcademicPlatformsCollector(max_results=max_per_source)
        if not await collector.validate():
            self._log.info(
                "AcademicPlatforms: no credentials set, skipping "
                "(set IEEE_API_KEY, ELSEVIER_API_KEY, SPRINGER_API_KEY, "
                "JSTOR_SESSION_COOKIE, or ACM_SESSION_COOKIE)"
            )
            return []
        docs: list[dict] = []
        try:
            async for doc in collector.collect(queries[:4]):
                docs.append(doc)
                if len(docs) >= max_per_source:
                    break
        except Exception as exc:
            self._log.warning("AcademicPlatforms collector error: %s", exc)
        await self._emit("source_done", f"AcademicPlatforms: {len(docs)} docs")
        return docs


async def run_collection_phase(
    queries: list[str],
    enabled_sources: list[str],
    max_per_source: int,
    max_docs: int,
    mission: dict,
    aggregator: Any,
    config: Any,
    emit_fn: Optional[Callable] = None,
    log: Optional[logging.Logger] = None,
) -> list[dict]:
    """Run all enabled collectors in parallel and return aggregated docs."""
    _log = log or logger
    dispatcher = CollectorDispatcher(config=config, log=_log, emit_fn=emit_fn)

    async def _dispatch_fn(
        queries: list[str],
        enabled_sources: list[str],
        max_per_source: int,
        mission: dict,
    ) -> list[asyncio.Task]:
        tasks = []
        for source_name in enabled_sources:
            coro = dispatcher.dispatch(source_name, queries, max_per_source)
            tasks.append(asyncio.create_task(coro))
        return tasks

    if emit_fn:
        await emit_fn("collect", f"Starting collectors: {enabled_sources}")

    tasks = await _dispatch_fn(queries, enabled_sources, max_per_source, mission)
    all_batches = await asyncio.gather(*tasks, return_exceptions=True)
    batches: list[list[dict]] = []
    for b in all_batches:
        if isinstance(b, Exception):
            _log.warning("Collector task failed: %s", b)
        elif b:
            batches.append(b)

    llm_cfg = mission.get("llm_sources", {})
    if llm_cfg.get("enabled", False):
        try:
            from aria.engine.ensemble.agent import LLMEnsembleAgent
            from aria.engine.ensemble.providers import default_llm_source_models
            models = llm_cfg.get("models") or default_llm_source_models(config)
            agent = LLMEnsembleAgent(models=models)
            llm_docs = await agent.collect(queries[:3])
            if llm_docs:
                batches.append(llm_docs)
                if emit_fn:
                    await emit_fn("llm_sources", f"LLM sources: {len(llm_docs)} documents")
        except Exception as exc:
            _log.debug("LLM sources failed: %s", exc)

    total_before_dedup = sum(len(b) for b in batches)
    raw_docs = await aggregator.aggregate(batches)
    dupes_removed = total_before_dedup - len(raw_docs)
    raw_docs = raw_docs[:max_docs]
    if emit_fn:
        await emit_fn(
            "collect_done",
            f"Collected {len(raw_docs)} unique documents "
            f"({total_before_dedup} total, {dupes_removed} duplicates removed)",
            count=len(raw_docs),
            total_before_dedup=total_before_dedup,
            duplicates_removed=dupes_removed,
        )
    return raw_docs


async def run_phased_collection(
    phases: list[dict],
    max_per_source: int,
    max_docs: int,
    mission: dict,
    aggregator: Any,
    config: Any,
    emit_fn: Optional[Callable] = None,
    log: Optional[logging.Logger] = None,
) -> list[dict]:
    """Run phased collection: landscape → deep_dive → critical → latest."""
    _log = log or logger
    dispatcher = CollectorDispatcher(config=config, log=_log, emit_fn=emit_fn)

    async def _emit(stage: str, msg: str, **kw: Any) -> None:
        if emit_fn:
            await emit_fn(stage, msg, **kw)

    all_docs: list[dict] = []
    phase_cap = max_docs // max(1, len(phases))

    for phase in phases:
        name = phase.get("name", "phase")
        goal = phase.get("goal", "")
        queries = phase.get("queries", [])
        source_types = phase.get("source_types", ["web", "academic"])
        phase_max = phase.get("max_docs", phase_cap)

        await _emit("phase_start", f"[{name}] {goal}", phase=name, queries=queries, sources=source_types)
        if not queries:
            await _emit("phase_done", f"[{name}] No queries — skipping", phase=name)
            continue

        tasks = [
            asyncio.create_task(
                dispatcher.dispatch(src, queries, max(5, min(max_per_source, phase_max // max(1, len(source_types)))))
            )
            for src in source_types
        ]
        all_batches = await asyncio.gather(*tasks, return_exceptions=True)
        batches = [b for b in all_batches if isinstance(b, list) and b]

        phase_docs = await aggregator.aggregate(batches)
        phase_docs = phase_docs[:phase_max]
        for doc in phase_docs:
            doc["_phase"] = name
        all_docs.extend(phase_docs)

        await _emit("phase_done", f"[{name}] {len(phase_docs)} docs", phase=name, count=len(phase_docs), total_so_far=len(all_docs))
        if len(all_docs) >= max_docs:
            break

    await _emit("collect_done", f"Phased collection: {len(all_docs)} total docs across {len(phases)} phases", count=len(all_docs))
    return all_docs[:max_docs]
