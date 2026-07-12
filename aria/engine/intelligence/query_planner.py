"""
Smart Query Planner — decomposes research topics into structured sub-questions
and generates targeted queries per source type.

Replaces the simple keyword-variant approach with LLM-driven research strategy.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("aria")

_PLANNER_SYSTEM = (
    "You are an expert research strategist. "
    "You decompose research topics into precise, diverse search queries "
    "covering all important angles: technical, practical, historical, current, policy, and criticism."
)

_PLANNER_PROMPT = """Research topic: "{topic}"
Research intent: "{intent}"

Your task: Generate a structured research plan with high-quality search queries.

Return ONLY valid JSON in this exact format:
{{
  "sub_questions": [
    "What is the current state of {topic}?",
    "What are the key technical approaches?",
    "What are real-world applications and case studies?",
    "What are the limitations, risks, and criticisms?",
    "What does the latest research say ({year})?",
    "Who are the key organizations/researchers in this space?"
  ],
  "queries": {{
    "general": [
      "{topic} overview",
      "{topic} explained",
      "how does {topic} work"
    ],
    "academic": [
      "{topic} research paper {year}",
      "{topic} systematic review",
      "{topic} empirical study"
    ],
    "technical": [
      "{topic} implementation",
      "{topic} architecture",
      "{topic} benchmark comparison"
    ],
    "news": [
      "{topic} latest news {year}",
      "{topic} breakthrough {year}",
      "{topic} industry adoption"
    ],
    "critical": [
      "{topic} problems limitations",
      "{topic} criticism failure",
      "{topic} risks concerns"
    ],
    "policy": [
      "{topic} regulation policy",
      "{topic} government standards",
      "{topic} ethics guidelines"
    ]
  }},
  "source_priorities": {{
    "academic": 9,
    "news": 7,
    "web": 8,
    "github": 6,
    "government": 5,
    "youtube": 4
  }},
  "entity_seeds": [
    "key person or org name 1",
    "key person or org name 2"
  ]
}}

Generate queries specific to: "{topic}"
Focus: "{intent}"
Current year: {year}
"""


async def plan_queries(
    topic: str,
    intent: str = "",
    llm_caller: Optional[Any] = None,
) -> dict[str, Any]:
    """
    Generate a structured research plan for a topic.

    Args:
        topic: Research topic.
        intent: What the user wants to learn.
        llm_caller: Optional async callable(prompt, system) -> str.

    Returns:
        Dict with sub_questions, queries (by type), source_priorities, entity_seeds.
        Falls back to heuristic plan if LLM unavailable.
    """
    year = datetime.now().year
    prompt = _PLANNER_PROMPT.format(topic=topic, intent=intent or topic, year=year)

    if llm_caller:
        try:
            response = await llm_caller(prompt, _PLANNER_SYSTEM)
            plan = _parse_plan(response)
            if plan:
                logger.info("Query planner: LLM plan generated (%d sub-questions)", len(plan.get("sub_questions", [])))
                return plan
        except Exception as exc:
            logger.debug("Query planner LLM failed: %s", exc)

    # Try built-in LLM
    plan = await _llm_plan(topic, intent, year)
    if plan:
        return plan

    # Heuristic fallback
    return _heuristic_plan(topic, intent, year)


async def _llm_plan(topic: str, intent: str, year: int) -> Optional[dict[str, Any]]:
    """Try available LLM APIs to generate plan."""
    from aria.engine.ensemble.providers import resolve_cleaning_llm
    from aria.engine.cleaner.llm_cleaner import _call_anthropic, _call_openai_compat
    from aria.engine.utils.retry import with_retry
    import os

    provider, model_id, base_url, api_key = resolve_cleaning_llm(None)
    prompt = _PLANNER_PROMPT.format(topic=topic, intent=intent or topic, year=year)

    try:
        timeout = float(os.getenv("ARIA_LLM_TIMEOUT", "60"))
        max_attempts = int(os.getenv("ARIA_LLM_RETRY_MAX", "3"))
        base_delay = float(os.getenv("ARIA_LLM_RETRY_BASE", "1.0"))
        max_delay = float(os.getenv("ARIA_LLM_RETRY_MAX_DELAY", "20.0"))

        async def _call() -> str:
            if provider == "anthropic":
                return await asyncio.wait_for(
                    _call_anthropic(
                        prompt, model_id, api_key, _PLANNER_SYSTEM,
                        max_tokens=1200, temperature=0.3,
                    ),
                    timeout=timeout,
                )
            return await asyncio.wait_for(
                _call_openai_compat(
                    prompt, model_id, api_key, base_url,
                    _PLANNER_SYSTEM, max_tokens=1200, temperature=0.3,
                ),
                timeout=timeout,
            )

        response_text = await with_retry(
            _call,
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
        )
    except Exception as exc:
        logger.debug("LLM plan call failed: %s", exc)
        return None

    return _parse_plan(response_text) if response_text else None


def _parse_plan(text: str) -> Optional[dict[str, Any]]:
    """Extract JSON plan from LLM response."""
    if not text:
        return None
    # Find JSON block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        plan = json.loads(match.group(0))
        if "queries" in plan or "sub_questions" in plan:
            return plan
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _heuristic_plan(topic: str, intent: str, year: int) -> dict[str, Any]:
    """Generate a solid heuristic plan without LLM."""
    t = topic.strip()
    return {
        "sub_questions": [
            f"What is {t} and how does it work?",
            f"What are the main applications of {t}?",
            f"What are recent advances in {t} ({year})?",
            f"What are the limitations and challenges of {t}?",
            f"Who are the key researchers and organizations in {t}?",
            f"What does the research say about {t}?",
        ],
        "queries": {
            "general": [t, f"{t} explained", f"{t} overview", f"what is {t}"],
            "academic": [
                f"{t} research {year}", f"{t} study paper", f"{t} systematic review",
                f"{t} empirical analysis",
            ],
            "technical": [
                f"{t} implementation", f"{t} technical details", f"{t} architecture",
            ],
            "news": [
                f"{t} news {year}", f"{t} latest developments", f"{t} industry update",
            ],
            "critical": [
                f"{t} limitations problems", f"{t} criticism risks", f"{t} failure cases",
            ],
            "policy": [
                f"{t} policy regulation", f"{t} ethics guidelines",
            ],
        },
        "source_priorities": {
            "academic": 9, "web": 8, "news": 7, "github": 6,
            "government": 5, "youtube": 4, "reddit": 3,
        },
        "entity_seeds": [],
    }


def flatten_queries(plan: dict[str, Any], max_total: int = 20) -> list[str]:
    """
    Flatten a plan's queries dict into a deduplicated list.
    Prioritises academic > general > technical > news > critical > policy.
    """
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
