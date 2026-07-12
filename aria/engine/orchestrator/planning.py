"""Query planning phase — topic → sub-questions + per-source search queries."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Optional

logger = logging.getLogger("aria")


async def run_planning_phase(
    topic: str,
    intent: str,
    config: Any,
    emit_fn: Optional[Callable] = None,
    research_brief: Optional[dict] = None,
) -> dict:
    """Resolve the query plan for a research run.

    Returns a dict with keys: topic, sub_questions, queries, query_plan.
    If *research_brief* is provided (Research Director path) it is used
    directly; otherwise smart or heuristic planning is attempted.
    """
    async def _emit(stage: str, msg: str, **kw: Any) -> None:
        if emit_fn:
            await emit_fn(stage, msg, **kw)

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
        await _emit(
            "query_plan",
            f"Research Director plan: {len(research_brief.get('phases', []))} phases, "
            f"{len(sub_questions)} questions, {len(queries)} queries",
            queries=queries,
            sub_questions=sub_questions,
            research_brief=research_brief,
        )
        return {"topic": topic, "sub_questions": sub_questions, "queries": queries, "query_plan": query_plan}

    await _emit("query_plan", f"Planning research strategy for: '{topic}'")
    query_plan = await _plan_queries(topic, intent, config)
    sub_questions = query_plan.get("sub_questions", [])
    queries = _flatten_plan_queries(query_plan, max_total=20)
    await _emit(
        "query_plan",
        f"Research plan: {len(sub_questions)} sub-questions, {len(queries)} queries",
        queries=queries,
        sub_questions=sub_questions,
    )
    return {"topic": topic, "sub_questions": sub_questions, "queries": queries, "query_plan": query_plan}


async def _plan_queries(topic: str, intent: str, config: Any) -> dict:
    """Use smart query planner (LLM) or fall back to heuristic."""
    if getattr(config, "smart_query_planning", True):
        try:
            from aria.engine.intelligence.query_planner import plan_queries
            from aria.engine.utils.retry import with_retry

            max_attempts = int(getattr(config, "llm_retry_max_attempts", 3))
            base_delay = float(getattr(config, "llm_retry_base_delay", 1.0))
            max_delay = float(getattr(config, "llm_retry_max_delay", 20.0))

            return await with_retry(
                plan_queries,
                topic,
                intent,
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
            )
        except Exception as exc:
            logger.debug("Smart query planner failed: %s", exc)
    return _heuristic_plan(topic, intent)


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
