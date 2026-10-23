"""Research Director Agent — conversational pre-research planner.

Talks to the user to understand context before any collection starts,
then builds a ResearchBrief that drives phased, targeted collection.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, AsyncGenerator, Optional

from aria.engine.intelligence.research_brief import ResearchBrief, ResearchPhase

logger = logging.getLogger("aria")

MAX_QUESTIONS = 10
CONSECUTIVE_SKIP_LIMIT = 3

# ── Prompts ────────────────────────────────────────────────────────────────────

_DIRECTOR_SYSTEM = """You are an expert research director. Your job is to understand
exactly what a user wants to research before any searching begins.

You think like a world-class librarian combined with a senior analyst:
- You disambiguate ambiguous topics
- You understand who is researching and why
- You build a precise research strategy
- You know which sources are best for which topic types

Always respond with valid JSON only."""

_DISAMBIGUATE_PROMPT = """The user wants to research: "{topic}"

First, determine if this topic is ambiguous (could mean multiple things).

Return JSON:
{{
  "is_ambiguous": true/false,
  "interpretations": [
    {{"label": "Mental health condition", "key": "mental_health"}},
    {{"label": "Economic recession", "key": "economic"}}
  ],
  "best_guess": "mental_health",
  "question": "This topic could mean different things. Which do you mean?",
  "skip_safe": false
}}

If not ambiguous, set is_ambiguous to false and interpretations to [].
topic: "{topic}"
"""

_QUESTIONS_PROMPT = """You are building a research plan for: "{resolved_topic}"
Known context so far: {context}

Generate the NEXT single clarifying question to ask the user.
Questions already asked: {asked}

Question categories to cover (in order of importance):
1. audience — who is this for?
2. purpose — why are they researching?
3. focus — what specific angle matters most?
4. time_range — historical, recent, or latest?
5. geography — global or specific region?
6. depth — surface overview or expert deep-dive?
7. exclude — anything to explicitly avoid?

Pick the most important uncovered category. If all covered, return done=true.

Return JSON:
{{
  "done": false,
  "category": "audience",
  "question": "Who is this research for?",
  "options": [
    {{"label": "General understanding (student/curious)", "key": "general"}},
    {{"label": "Medical/clinical professional", "key": "professional"}},
    {{"label": "Academic researcher", "key": "academic"}},
    {{"label": "Someone personally affected", "key": "personal"}}
  ],
  "allows_custom": true,
  "skippable": true
}}
"""

_BUILD_BRIEF_PROMPT = """Build a complete research brief for: "{resolved_topic}"

User context gathered:
{context}

Current year: {year}

Return JSON:
{{
  "resolved_topic": "precise description of what to research",
  "audience": "general|professional|academic|personal",
  "purpose": "informational|academic|investment|clinical|personal",
  "depth": "surface|medium|expert",
  "time_range": "latest|5years|all",
  "geography": "global or specific region",
  "language": "english",
  "focus": "the specific angle the user cares about most",
  "key_questions": [
    "5-10 precise research questions to answer, specific to this topic and focus"
  ],
  "entities": [
    "key people, organizations, concepts, drugs, companies relevant to this topic"
  ],
  "ambiguities_resolved": [
    "what was clarified during conversation"
  ],
  "must_have_sources": ["academic", "news"],
  "skip_sources": ["github", "youtube"],
  "excluded_angles": ["anything user said to exclude"]
}}

Make key_questions highly specific — not generic. For '{resolved_topic}' the questions
should be exactly what an expert researcher would want answered.
"""


class ResearchDirector:
    """Conversational agent that builds a ResearchBrief before collection starts."""

    def __init__(
        self,
        llm_caller: Optional[Any] = None,
        llm_overrides: Optional[dict[str, str]] = None,
    ):
        self._llm = llm_caller or self._default_llm_caller(llm_overrides)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def run_conversation(
        self, topic: str
    ) -> AsyncGenerator[dict[str, Any], str | None]:
        """
        Async generator that yields questions and receives user answers.

        Usage:
            gen = director.run_conversation(topic)
            event = await gen.asend(None)          # start
            while event["type"] != "done":
                answer = await get_user_input()
                event = await gen.asend(answer)
            brief = event["brief"]
        """
        brief = ResearchBrief(original_topic=topic)
        consecutive_skips = 0
        asked_categories: list[str] = []

        # Step 1 — disambiguate
        disambiguation = await self._disambiguate(topic)
        if disambiguation.get("is_ambiguous"):
            answer = yield {
                "type": "question",
                "category": "disambiguation",
                "question": disambiguation.get("question", f"What do you mean by '{topic}'?"),
                "options": disambiguation.get("interpretations", []),
                "allows_custom": True,
                "skippable": False,
            }
            brief.questions_asked += 1

            if answer and answer.lower() not in ("skip", ""):
                resolved = self._resolve_disambiguation(answer, disambiguation)
                brief.resolved_topic = resolved
                brief.ambiguities_resolved.append(f"'{topic}' = {resolved}")
                brief.answers["disambiguation"] = answer
            else:
                # Use best guess
                brief.resolved_topic = disambiguation.get("best_guess", topic)
        else:
            brief.resolved_topic = topic

        # Step 2 — clarifying questions loop
        while (
            brief.questions_asked < MAX_QUESTIONS
            and consecutive_skips < CONSECUTIVE_SKIP_LIMIT
        ):
            q_data = await self._next_question(brief, asked_categories)

            if q_data.get("done"):
                break

            category = q_data.get("category", "")
            asked_categories.append(category)

            answer = yield {
                "type": "question",
                "category": category,
                "question": q_data.get("question", ""),
                "options": q_data.get("options", []),
                "allows_custom": q_data.get("allows_custom", True),
                "skippable": True,
            }
            brief.questions_asked += 1

            if answer is None or answer.lower() in ("skip", ""):
                consecutive_skips += 1
                brief.skips += 1
            elif answer.lower() == "start":
                break
            else:
                consecutive_skips = 0
                self._apply_answer(brief, category, answer, q_data)

        # Step 3 — build full brief via LLM
        await self._build_brief(brief)

        yield {"type": "done", "brief": brief}

    async def build_brief_silent(self, topic: str) -> ResearchBrief:
        """Build brief without any conversation — infer everything from topic."""
        brief = ResearchBrief(original_topic=topic, resolved_topic=topic)
        await self._build_brief(brief)
        return brief

    # ── Internal ───────────────────────────────────────────────────────────────

    async def _disambiguate(self, topic: str) -> dict[str, Any]:
        prompt = _DISAMBIGUATE_PROMPT.format(topic=topic)
        response = await self._call_llm(prompt)
        parsed = self._parse_json(response)
        if parsed is None:
            raise RuntimeError("The AI model returned an invalid planning response.")
        return parsed

    async def _next_question(
        self, brief: ResearchBrief, asked: list[str]
    ) -> dict[str, Any]:
        context = json.dumps(brief.answers, indent=2)
        asked_str = ", ".join(asked) if asked else "none"
        prompt = _QUESTIONS_PROMPT.format(
            resolved_topic=brief.resolved_topic,
            context=context,
            asked=asked_str,
        )
        response = await self._call_llm(prompt)
        parsed = self._parse_json(response)
        if parsed is None:
            raise RuntimeError("The AI model returned an invalid planning response.")
        return parsed

    async def _build_brief(self, brief: ResearchBrief) -> None:
        context = json.dumps(
            {
                "answers": brief.answers,
                "resolved_topic": brief.resolved_topic,
                "ambiguities_resolved": brief.ambiguities_resolved,
            },
            indent=2,
        )
        prompt = _BUILD_BRIEF_PROMPT.format(
            resolved_topic=brief.resolved_topic or brief.original_topic,
            context=context,
            year=datetime.now().year,
        )
        response = await self._call_llm(prompt)
        data = self._parse_json(response)
        if data is None:
            raise RuntimeError("The AI model returned an invalid research brief.")
        self._apply_brief_data(brief, data)

    def _apply_answer(
        self,
        brief: ResearchBrief,
        category: str,
        answer: str,
        q_data: dict[str, Any],
    ) -> None:
        # Resolve option key if user picked a number or label
        options = q_data.get("options", [])
        resolved = answer
        for opt in options:
            if answer == opt.get("key") or answer.lower() == opt.get("label", "").lower():
                resolved = opt.get("key", answer)
                break

        brief.answers[category] = resolved

        if category == "audience":
            brief.audience = resolved
        elif category == "purpose":
            brief.purpose = resolved
        elif category == "focus":
            brief.focus = resolved
        elif category == "time_range":
            brief.time_range = resolved
        elif category == "geography":
            brief.geography = resolved
        elif category == "depth":
            brief.depth = resolved
        elif category == "exclude":
            brief.excluded_angles.append(resolved)

    def _resolve_disambiguation(
        self, answer: str, disambiguation: dict[str, Any]
    ) -> str:
        interpretations = disambiguation.get("interpretations", [])
        for interp in interpretations:
            if (
                answer == interp.get("key")
                or answer.lower() in interp.get("label", "").lower()
            ):
                return interp.get("label", answer)
        return answer

    def _apply_brief_data(self, brief: ResearchBrief, data: dict[str, Any]) -> None:
        if data.get("resolved_topic"):
            brief.resolved_topic = data["resolved_topic"]
        brief.audience = data.get("audience", brief.audience)
        brief.purpose = data.get("purpose", brief.purpose)
        brief.depth = data.get("depth", brief.depth)
        brief.time_range = data.get("time_range", brief.time_range)
        brief.geography = data.get("geography", brief.geography)
        brief.language = data.get("language", brief.language)
        brief.focus = data.get("focus", brief.focus)
        brief.key_questions = data.get("key_questions", [])
        brief.entities = data.get("entities", [])
        brief.ambiguities_resolved += data.get("ambiguities_resolved", [])
        brief.must_have_sources = data.get("must_have_sources", [])
        brief.skip_sources = data.get("skip_sources", [])
        brief.excluded_angles += data.get("excluded_angles", [])

    async def _call_llm(self, prompt: str) -> str:
        if self._llm:
            return await self._llm(prompt, _DIRECTOR_SYSTEM)
        raise RuntimeError("No LLM caller configured")

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any] | None:
        if not text:
            return None
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _default_llm_caller(llm_overrides: Optional[dict[str, str]] = None) -> Any:
        async def caller(prompt: str, system: str) -> str:
            from aria.engine.ensemble.providers import resolve_cleaning_llm
            from aria.engine.cleaner.llm_cleaner import _call_anthropic, _call_openai_compat

            provider, model_id, base_url, api_key = resolve_cleaning_llm(
                None, overrides=llm_overrides
            )
            if provider == "anthropic":
                return await _call_anthropic(
                    prompt, model_id, api_key, system,
                    max_tokens=1500, temperature=0.3,
                )
            return await _call_openai_compat(
                prompt, model_id, api_key, base_url,
                system, max_tokens=1500, temperature=0.3,
            )
        return caller
