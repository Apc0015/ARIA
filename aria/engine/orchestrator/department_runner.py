"""Department Runner — executes a CollectionPlan using domain-specific collectors."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

from aria.engine.domains.planner import CollectionPlan

logger = logging.getLogger("aria")

# Maps collector names → (module_path, class_name, supports_country_filter)
_COLLECTOR_REGISTRY: dict[str, tuple[str, str, bool]] = {
    # Existing collectors
    "web":               ("aria.engine.collectors.web.search",    "WebSearchCollector",      False),
    "pdf":               ("aria.engine.collectors.web.pdf",           "PDFCollector",            False),
    "academic":          ("aria.engine.collectors.academic.core",      "AcademicCollector",       False),
    "youtube":           ("aria.engine.collectors.media.youtube",       "YouTubeCollector",        False),
    "reddit":            ("aria.engine.collectors.web.reddit",        "RedditCollector",         False),
    "hackernews":        ("aria.engine.collectors.web.hackernews",    "HackerNewsCollector",     False),
    "wikipedia":         ("aria.engine.collectors.web.wikipedia",     "WikipediaCollector",      False),
    "stackoverflow":     ("aria.engine.collectors.web.stackoverflow", "StackOverflowCollector",  False),
    "medium":            ("aria.engine.collectors.web.medium",        "MediumCollector",         False),
    "devto":             ("aria.engine.collectors.web.devto",         "DevToCollector",          False),
    "substack":          ("aria.engine.collectors.web.substack",      "SubstackCollector",       False),
    "rss":               ("aria.engine.collectors.web.rss",           "RSSCollector",            False),
    "twitter":           ("aria.engine.collectors.social.twitter",       "TwitterCollector",        False),
    "slack":             ("aria.engine.collectors.social.slack",         "SlackCollector",          False),
    "zotero":            ("aria.engine.collectors.knowledge.zotero",        "ZoteroCollector",         False),
    "notion":            ("aria.engine.collectors.knowledge.notion",        "NotionCollector",         False),
    "podcast":           ("aria.engine.collectors.media.podcast",       "PodcastCollector",        False),
    "vimeo":             ("aria.engine.collectors.media.vimeo",         "VimeoCollector",          False),
    "github":            ("aria.engine.collectors.knowledge.github",        "GitHubCollector",         False),
    "government":        ("aria.engine.collectors.specialized.government",    "GovernmentCollector",     False),
    "multilingual":      ("aria.engine.collectors.specialized.multilingual",  "MultilingualCollector",   False),
    "news":              ("aria.engine.collectors.specialized.news",          "NewsCollector",           False),
    "academic_platforms":("aria.engine.collectors.academic.core_platforms", "AcademicPlatformsCollector", False),
    # New ARIA 5.0 collectors
    "world_bank":        ("aria.engine.collectors.data.world_bank",    "WorldBankCollector",      True),
    "un_data":           ("aria.engine.collectors.data.un_data",       "UNDataCollector",         True),
    "who":               ("aria.engine.collectors.data.who",           "WHOCollector",            True),
    "imf":               ("aria.engine.collectors.data.imf",           "IMFCollector",            True),
    "fred":              ("aria.engine.collectors.data.fred",          "FREDCollector",           False),
    "open_alex":         ("aria.engine.collectors.academic.open_alex",     "OpenAlexCollector",       False),
    "gdelt":             ("aria.engine.collectors.data.gdelt",         "GDELTCollector",          False),
    "clinical_trials":   ("aria.engine.collectors.data.clinical_trials","ClinicalTrialsCollector",True),
    "jobs_boards":       ("aria.engine.collectors.specialized.jobs_boards",   "JobsBoardsCollector",     True),
    "intl_gov":          ("aria.engine.collectors.specialized.intl_gov",      "IntlGovCollector",        True),
    "sec_edgar":         ("aria.engine.collectors.data.sec_edgar",     "SECEdgarCollector",       False),
    "eurostat":          ("aria.engine.collectors.data.eurostat",      "EurostatCollector",       True),
    # Aliases used in domain registry
    "pubmed_enhanced":   ("aria.engine.collectors.academic.core",      "AcademicCollector",       False),
}


class DepartmentRunner:
    """Executes a CollectionPlan by activating the right collectors per domain.

    Each domain = a "department". Multi-domain plans run departments in parallel.
    Country filters and priority weights are applied per-collector.
    """

    def __init__(
        self,
        config: Any,
        max_per_collector: int = 25,
        emit_callback: Optional[Callable] = None,
    ) -> None:
        self._config = config
        self._max_per = max_per_collector
        self._emit = emit_callback or (lambda *a, **kw: asyncio.sleep(0))

    async def run(
        self,
        plan: CollectionPlan,
        aggregator: Any,
    ) -> list[dict]:
        """Execute all collectors in the plan in parallel, return aggregated docs."""
        tasks: list[asyncio.Task] = []

        for collector_name in plan.active_collectors:
            country_codes = plan.country_filters.get(collector_name, [])
            weight = plan.priority_weights.get(collector_name, 1.0)
            max_results = max(5, int(self._max_per * weight))

            coro = self._run_collector(
                collector_name=collector_name,
                queries=plan.queries,
                max_results=max_results,
                country_codes=country_codes,
            )
            tasks.append(asyncio.create_task(coro))

        logger.debug(
            "DepartmentRunner: launching %d collectors for plan '%s'",
            len(tasks), plan.intent.topic,
        )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        batches: list[list[dict]] = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning("DepartmentRunner: collector failed: %s", r)
            elif isinstance(r, list) and r:
                batches.append(r)

        docs = await aggregator.aggregate(batches)

        # Citation enrichment if depth > 0
        if plan.citation_depth > 0 and docs:
            try:
                from aria.engine.citation.agent import CitationAgent
                citation_agent = CitationAgent(
                    max_depth=plan.citation_depth,
                    max_citations=min(100, len(docs) * 2),
                )
                docs = await citation_agent.enrich(docs)
                logger.debug(
                    "DepartmentRunner: citation enrichment added %d docs",
                    len(docs) - len(batches),
                )
            except Exception as exc:
                logger.debug("DepartmentRunner: citation enrichment failed: %s", exc)

        return docs

    async def _run_collector(
        self,
        collector_name: str,
        queries: list[str],
        max_results: int,
        country_codes: list[str],
    ) -> list[dict]:
        entry = _COLLECTOR_REGISTRY.get(collector_name)
        if not entry:
            logger.debug("DepartmentRunner: unknown collector '%s'", collector_name)
            return []

        module_path, class_name, supports_country = entry
        try:
            import importlib
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)

            # Build kwargs
            kwargs: dict[str, Any] = {"max_results": max_results}
            if supports_country and country_codes:
                kwargs["country_codes"] = country_codes

            collector = cls(**kwargs)
            docs: list[dict] = []
            async for doc in collector.collect(queries):
                docs.append(doc)
                if len(docs) >= max_results:
                    break

            logger.debug(
                "DepartmentRunner: %s → %d docs", collector_name, len(docs)
            )
            return docs

        except Exception as exc:
            logger.warning(
                "DepartmentRunner: collector '%s' failed: %s", collector_name, exc
            )
            return []
