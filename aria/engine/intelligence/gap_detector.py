"""
Gap Detector — analyses collected documents and identifies unanswered
sub-questions, then generates targeted follow-up queries.

This is what makes ARIA agentic: after initial collection, it asks
"what did we miss?" and goes back for a second pass.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger("aria")

_GAP_SYSTEM = (
    "You are an expert research analyst. "
    "You identify what's missing from a research corpus and generate targeted follow-up queries."
)

_GAP_PROMPT = """You are reviewing collected research documents on the topic: "{topic}"
Research intent: "{intent}"

The original sub-questions were:
{sub_questions}

Here is a summary of what was collected ({doc_count} documents):
Platform breakdown: {platform_breakdown}
Sample titles:
{sample_titles}

Your task: Identify research gaps and generate follow-up queries.

Return ONLY valid JSON:
{{
  "answered_questions": [
    "Sub-question that IS well covered by the collected docs"
  ],
  "gaps": [
    {{
      "question": "Sub-question that is NOT answered or poorly covered",
      "reason": "Why this is a gap (e.g., no academic sources, only 1 doc, missing perspective)",
      "follow_up_queries": ["targeted query 1", "targeted query 2"]
    }}
  ],
  "missing_perspectives": [
    "A viewpoint or angle not represented in collected docs"
  ],
  "recommended_sources": ["source type most likely to fill gaps, e.g. academic, government"]
}}
"""


async def detect_gaps(
    docs: list[dict[str, Any]],
    topic: str,
    intent: str = "",
    sub_questions: Optional[list[str]] = None,
    max_follow_up_queries: int = 10,
) -> dict[str, Any]:
    """
    Analyse collected documents and find research gaps.

    Returns:
        Dict with gaps list, follow_up_queries, missing_perspectives.
        Returns empty gap result if LLM unavailable.
    """
    if not docs:
        return _empty_result()

    summary = _summarise_corpus(docs)
    sq_text = "\n".join(f"- {q}" for q in (sub_questions or [])) or "No sub-questions defined"
    titles = "\n".join(f"- {d.get('title', d.get('url', ''))[:100]}" for d in docs[:30])

    prompt = _GAP_PROMPT.format(
        topic=topic,
        intent=intent or topic,
        sub_questions=sq_text,
        doc_count=len(docs),
        platform_breakdown=json.dumps(summary["platforms"]),
        sample_titles=titles,
    )

    response_text = await _call_llm(prompt)
    if not response_text:
        logger.debug("Gap detection: no LLM available, skipping")
        return _empty_result()

    result = _parse_gap_response(response_text)

    # Flatten follow-up queries
    follow_ups: list[str] = []
    for gap in result.get("gaps", []):
        follow_ups.extend(gap.get("follow_up_queries", []))

    result["follow_up_queries"] = list(dict.fromkeys(follow_ups))[:max_follow_up_queries]
    result["has_gaps"] = bool(result.get("gaps"))

    if result["has_gaps"]:
        logger.info(
            "Gap detector found %d gaps, generated %d follow-up queries",
            len(result["gaps"]),
            len(result["follow_up_queries"]),
        )

    return result


def _summarise_corpus(docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Quick stats about the collected corpus."""
    platforms: dict[str, int] = {}
    source_types: dict[str, int] = {}
    for doc in docs:
        p = doc.get("platform", "unknown")
        platforms[p] = platforms.get(p, 0) + 1
        s = doc.get("source_type", "unknown")
        source_types[s] = source_types.get(s, 0) + 1
    return {"platforms": platforms, "source_types": source_types}


async def _call_llm(prompt: str) -> Optional[str]:
    """Call best available LLM."""
    ant_key = os.getenv("ANTHROPIC_API_KEY")
    or_key = os.getenv("OPENROUTER_API_KEY")
    oai_key = os.getenv("OPENAI_API_KEY")

    try:
        if ant_key:
            from aria.engine.cleaner.llm_cleaner import _call_anthropic
            return await _call_anthropic(
                prompt, "claude-3-haiku-20240307", ant_key, _GAP_SYSTEM,
                max_tokens=1500, temperature=0.2,
            )
        elif or_key:
            from aria.engine.cleaner.llm_cleaner import _call_openai_compat
            return await _call_openai_compat(
                prompt, "openai/gpt-4o-mini", or_key, "https://openrouter.ai/api/v1",
                _GAP_SYSTEM, max_tokens=1500, temperature=0.2,
            )
        elif oai_key:
            from aria.engine.cleaner.llm_cleaner import _call_openai_compat
            return await _call_openai_compat(
                prompt, "gpt-4o-mini", oai_key, "https://api.openai.com/v1",
                _GAP_SYSTEM, max_tokens=1500, temperature=0.2,
            )
    except Exception as exc:
        logger.debug("Gap detection LLM call failed: %s", exc)
    return None


def _parse_gap_response(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(0))
            if "gaps" in result:
                return result
        except (json.JSONDecodeError, ValueError):
            pass
    return _empty_result()


def _empty_result() -> dict[str, Any]:
    return {
        "answered_questions": [],
        "gaps": [],
        "missing_perspectives": [],
        "recommended_sources": [],
        "follow_up_queries": [],
        "has_gaps": False,
    }
