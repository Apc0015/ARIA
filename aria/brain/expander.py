"""Query expansion helpers.

Two paths:
- expand()           → LLM-powered (8 diverse queries) with heuristic fallback
- expand_for_source() → source-type-specific query variants
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("aria")

# Prompt used by the LLM expander
_EXPAND_PROMPT = """\
You are a research query planner. Given a topic, produce exactly 8 distinct \
search queries that together cover the topic from different angles:
- Core definition / overview
- Recent developments (2022-2025)
- Technical deep-dive
- Comparative / alternatives
- Use cases / applications
- Criticism / limitations
- Academic / scientific angle
- Policy / societal implications

Topic: {topic}

Reply with ONLY a JSON array of 8 strings (no explanations, no markdown fences):
["query1","query2","query3","query4","query5","query6","query7","query8"]
"""

# Per-source query suffix/prefix hints
_SOURCE_HINTS: dict[str, str] = {
    "academic":           "{topic} research study",
    "open_alex":          "{topic} peer reviewed paper",
    "arxiv":              "{topic} arxiv preprint",
    "pubmed":             "{topic} clinical study",
    "pdf":                "{topic} filetype:pdf",
    "reddit":             "{topic} reddit discussion",
    "hackernews":         "{topic} hacker news",
    "stackoverflow":      "{topic} stackoverflow solution",
    "medium":             "{topic} medium article",
    "devto":              "{topic} dev.to tutorial",
    "substack":           "{topic} newsletter",
    "news":               "{topic} latest news",
    "youtube":            "{topic} video tutorial",
    "github":             "{topic} github repository",
    "twitter":            "{topic} twitter thread",
    "wikipedia":          "{topic} wikipedia",
    "government":         "{topic} government report",
    "world_bank":         "{topic} world bank data",
    "who":                "{topic} WHO report",
    "clinical_trials":    "{topic} clinical trial results",
    "sec_edgar":          "{topic} SEC filing",
    "jobs_boards":        "{topic} job posting requirements",
}


class QueryExpander:
    """Expand a topic into search queries.

    LLM path (preferred): calls the configured LLM for 8 diverse queries.
    Heuristic fallback: uses the engine's built-in heuristic planner.
    """

    def __init__(self, settings: Any = None, logger: Any = None) -> None:
        self.settings = settings
        self._log = logger or logging.getLogger("aria")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def expand(
        self,
        topic: str,
        collection_config: dict[str, Any] | None = None,
        use_llm: bool = True,
    ) -> list[str]:
        """Return up to 8 diverse queries for *topic*.

        Tries the LLM expander first; falls back to the heuristic planner.
        """
        if use_llm:
            queries = self._expand_with_llm(topic)
            if queries:
                return queries
        return self._expand_heuristic(topic)

    def expand_for_source(self, topic: str, source_type: str) -> list[str]:
        """Return source-specific query variants for *topic*.

        Combines the LLM/heuristic base queries with a source-specific
        reformulation of the topic as the first item.
        """
        base_queries = self.expand(topic)
        hint_template = _SOURCE_HINTS.get(source_type)
        if hint_template:
            source_query = hint_template.format(topic=topic)
            # Prepend so the source-specific query runs first
            queries = [source_query] + [q for q in base_queries if q != source_query]
        else:
            queries = base_queries
        return queries[:8]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _expand_with_llm(self, topic: str) -> list[str]:
        """Try to generate 8 queries via the LLM router. Returns [] on failure."""
        import json
        try:
            from aria.engine.ensemble.providers import get_llm_router
            router = get_llm_router(self.settings)
            prompt = _EXPAND_PROMPT.format(topic=topic)
            response = router.complete(prompt, max_tokens=512, temperature=0.4)
            text = (response or "").strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                text = "\n".join(
                    line for line in text.splitlines()
                    if not line.strip().startswith("```")
                ).strip()
            queries = json.loads(text)
            if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
                return [q.strip() for q in queries if q.strip()][:8]
        except Exception as exc:
            self._log.debug("LLM query expansion failed, using heuristic: %s", exc)
        return []

    def _expand_heuristic(self, topic: str) -> list[str]:
        """Heuristic expansion using the engine's built-in planner."""
        from aria.engine.orchestrator.planning import _flatten_plan_queries, _heuristic_plan
        plan = _heuristic_plan(topic, "")
        return _flatten_plan_queries(plan)
