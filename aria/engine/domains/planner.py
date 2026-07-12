"""Intent Agent + Strategy Planner — LLM-driven query understanding and collection planning."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from aria.engine.domains.registry import DOMAINS, DomainConfig, resolve_collectors, get_citation_depth
from aria.engine.domains.countries import COUNTRIES, REGIONS, resolve_countries, get_world_bank_codes

logger = logging.getLogger("aria")

# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class IntentResult:
    original_query: str
    topic: str
    domains: list[str]
    countries: list[str]
    data_types: list[str]
    time_range: str | None
    # 0.0–1.0 confidence per field
    confidence: dict[str, float] = field(default_factory=dict)
    # Questions to ask user if confidence is low
    pending_questions: list[str] = field(default_factory=list)
    ready: bool = False


@dataclass
class CollectionPlan:
    intent: IntentResult
    active_collectors: list[str]
    queries: list[str]
    # collector_name → list of country codes to filter
    country_filters: dict[str, list[str]]
    # collector_name → priority weight
    priority_weights: dict[str, float]
    citation_depth: int
    depth_level: int
    estimated_docs: int
    summary: str


# ── System prompts ────────────────────────────────────────────────────────────

_INTENT_SYSTEM = """You are an expert research query analyst.
Extract structured research intent from user queries.
Always respond with valid JSON only. No markdown, no explanation."""

_INTENT_PROMPT = """Analyze this research query and extract structured intent.

Query: "{query}"

Available domains: {domains}
Available countries: {countries}
Available regions: {regions}

Return ONLY valid JSON:
{{
  "topic": "clean topic phrase (3-8 words)",
  "domains": ["domain1", "domain2"],
  "countries": ["CC1", "CC2"],
  "data_types": ["vacancies|research|statistics|news|policy|reports|listings"],
  "time_range": "last_week|last_month|last_6_months|last_year|any|null",
  "confidence": {{
    "topic": 0.95,
    "domains": 0.8,
    "countries": 0.6,
    "data_types": 0.9
  }},
  "pending_questions": [
    "Which country or region are you targeting?",
    "Are you looking for job listings or industry research?"
  ]
}}

Rules:
- domains: only from the available list, pick all that apply
- countries: ISO codes or region names (GLOBAL if worldwide)
- pending_questions: only for fields with confidence < 0.65, max 4 questions
- If no country mentioned, use ["GLOBAL"] with confidence 0.4
- data_types: pick from [vacancies, research, statistics, news, policy, reports, listings, clinical, market_data]
"""

_PLAN_SYSTEM = """You are a research strategy expert.
Generate optimal search queries for a research plan.
Always respond with valid JSON only."""

_PLAN_PROMPT = """Generate a research collection plan.

Topic: {topic}
Domains: {domains}
Countries: {countries}
Data types: {data_types}
Time range: {time_range}
Current year: {year}

Return ONLY valid JSON:
{{
  "queries": [
    "query 1",
    "query 2",
    ... (20-35 diverse, targeted queries)
  ],
  "priority_sources": ["source1", "source2"],
  "depth_recommendation": 2,
  "estimated_docs": 300,
  "collection_summary": "One sentence description of what will be collected"
}}

Query rules:
- Mix general + specific + location-specific queries
- Include year {year} in time-sensitive queries
- For jobs: include job titles, seniority levels, locations
- For research: include methodology terms, paper types
- For policy: include legislation names, agency names
- Cover all angles: current state, trends, challenges, opportunities
"""


# ── Intent Agent ──────────────────────────────────────────────────────────────

class IntentAgent:
    """Parses natural language queries into structured research intent.

    Uses LLM to extract domains, countries, data types, and confidence.
    Generates clarifying questions for low-confidence fields.
    """

    CONFIDENCE_THRESHOLD = 0.65

    def __init__(self) -> None:
        self._domain_ids = list(DOMAINS.keys())
        self._country_codes = list(COUNTRIES.keys())
        self._region_codes = list(REGIONS.keys())

    async def analyze(self, query: str) -> IntentResult:
        """Parse a natural language query into structured intent."""
        prompt = _INTENT_PROMPT.format(
            query=query,
            domains=", ".join(self._domain_ids),
            countries=", ".join(self._country_codes[:30]) + "... (ISO codes)",
            regions=", ".join(self._region_codes),
        )
        try:
            text = await self._call_llm(prompt, _INTENT_SYSTEM)
            if text:
                data = self._parse_json(text)
                if data:
                    return self._build_intent(query, data)
        except Exception as exc:
            logger.debug("IntentAgent LLM failed: %s", exc)

        return self._heuristic_intent(query)

    async def clarify(self, intent: IntentResult, user_answer: str) -> IntentResult:
        """Refine intent based on user's answer to a clarifying question."""
        combined = f"Original: {intent.original_query}\nUser clarification: {user_answer}"
        return await self.analyze(combined)

    def _build_intent(self, query: str, data: dict) -> IntentResult:
        domains = [d for d in data.get("domains", []) if d in self._domain_ids]
        countries = data.get("countries", ["GLOBAL"])
        confidence = data.get("confidence", {})

        # Build pending questions only for low-confidence fields
        questions = [
            q for q in data.get("pending_questions", [])
            if isinstance(q, str) and q.strip()
        ]

        ready = all(
            confidence.get(f, 0) >= self.CONFIDENCE_THRESHOLD
            for f in ("domains", "countries")
        ) or not questions

        return IntentResult(
            original_query=query,
            topic=data.get("topic", query[:60]),
            domains=domains or ["science"],
            countries=countries or ["GLOBAL"],
            data_types=data.get("data_types", []),
            time_range=data.get("time_range"),
            confidence=confidence,
            pending_questions=questions[:4],
            ready=ready,
        )

    def _heuristic_intent(self, query: str) -> IntentResult:
        """Fallback: keyword-based domain detection."""
        q = query.lower()
        domains: list[str] = []

        keyword_map = {
            "jobs": ["job", "vacancy", "hiring", "career", "recruitment", "employ", "position", "opening"],
            "health": ["health", "medical", "clinical", "disease", "hospital", "patient", "drug", "medicine", "who", "pharma"],
            "finance": ["finance", "economic", "gdp", "imf", "world bank", "market", "stock", "investment", "monetary"],
            "government": ["government", "policy", "regulation", "legislation", "law", "ministry", "official", "gov"],
            "science": ["research", "paper", "study", "academic", "arxiv", "journal", "findings", "experiment"],
            "technology": ["tech", "software", "code", "developer", "github", "programming", "ai", "machine learning"],
            "legal": ["legal", "court", "law", "patent", "litigation", "contract", "compliance", "regulatory"],
            "news": ["news", "current events", "latest", "breaking", "report", "media"],
            "environment": ["climate", "environment", "carbon", "pollution", "biodiversity", "sustainability", "ecology"],
            "education": ["education", "university", "school", "learn", "course", "curriculum", "student"],
            "social": ["social media", "reddit", "twitter", "community", "discussion", "opinion", "forum"],
            "business": ["business", "startup", "company", "market", "industry", "commerce", "entrepreneur"],
        }

        for domain, keywords in keyword_map.items():
            if any(kw in q for kw in keywords):
                domains.append(domain)

        if not domains:
            domains = ["science", "news"]

        # Heuristic country detection
        countries = ["GLOBAL"]
        country_hints = {
            "india": "IN", "indian": "IN",
            "us ": "US", "usa": "US", "america": "US", "united states": "US",
            "uk ": "UK", "britain": "UK", "england": "UK", "united kingdom": "UK",
            "germany": "DE", "german": "DE",
            "france": "FR", "french": "FR",
            "china": "CN", "chinese": "CN",
            "japan": "JP", "japanese": "JP",
            "australia": "AU", "australian": "AU",
            "canada": "CA", "canadian": "CA",
            "brazil": "BR", "brazilian": "BR",
            "singapore": "SG",
            "pakistan": "PK",
            "bangladesh": "BD",
            "nigeria": "NG", "nigerian": "NG",
            "kenya": "KE", "kenyan": "KE",
        }
        detected = [code for hint, code in country_hints.items() if hint in q]
        if detected:
            countries = detected

        return IntentResult(
            original_query=query,
            topic=query[:60],
            domains=domains[:3],
            countries=countries,
            data_types=[],
            time_range=None,
            confidence={"domains": 0.5, "countries": 0.5},
            pending_questions=[],
            ready=True,
        )

    async def _call_llm(self, prompt: str, system: str) -> str | None:
        from aria.engine.ensemble.providers import resolve_cleaning_llm
        from aria.engine.cleaner.llm_cleaner import _call_anthropic, _call_openai_compat
        provider, model_id, base_url, api_key = resolve_cleaning_llm(None)
        if provider == "anthropic":
            return await _call_anthropic(prompt, model_id, api_key, system, max_tokens=800, temperature=0.1)
        return await _call_openai_compat(prompt, model_id, api_key, base_url, system, max_tokens=800, temperature=0.1)

    def _parse_json(self, text: str) -> dict | None:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


# ── Strategy Planner ──────────────────────────────────────────────────────────

class StrategyPlanner:
    """Builds an optimized CollectionPlan from a resolved IntentResult."""

    _DEPTH_DOCS = {1: 50, 2: 200, 3: 500, 4: 1500, 5: 5000}

    async def build_plan(self, intent: IntentResult) -> CollectionPlan:
        collectors = resolve_collectors(intent.domains)
        country_filters = self._build_country_filters(collectors, intent.countries)
        priority_weights = self._build_priority_weights(intent.domains, collectors)
        queries = await self._generate_queries(intent)
        depth = self._recommend_depth(intent)
        citation_depth = get_citation_depth(intent.domains)

        return CollectionPlan(
            intent=intent,
            active_collectors=collectors,
            queries=queries,
            country_filters=country_filters,
            priority_weights=priority_weights,
            citation_depth=citation_depth,
            depth_level=depth,
            estimated_docs=self._DEPTH_DOCS.get(depth, 200),
            summary=self._summarize(intent, collectors),
        )

    def _build_country_filters(
        self, collectors: list[str], country_codes: list[str]
    ) -> dict[str, list[str]]:
        if "GLOBAL" in country_codes:
            return {}
        country_aware = {
            "jobs_boards", "intl_gov", "world_bank", "imf",
            "fred", "eurostat", "gdelt", "un_data",
        }
        return {col: country_codes for col in collectors if col in country_aware}

    def _build_priority_weights(
        self, domains: list[str], collectors: list[str]
    ) -> dict[str, float]:
        weights: dict[str, float] = {c: 1.0 for c in collectors}
        domain_boosts: dict[str, dict[str, float]] = {
            "jobs":        {"jobs_boards": 2.0},
            "health":      {"who": 2.0, "clinical_trials": 1.8, "academic": 1.5},
            "finance":     {"world_bank": 2.0, "imf": 1.8, "fred": 1.6},
            "government":  {"intl_gov": 1.8, "government": 1.8, "un_data": 1.5},
            "science":     {"open_alex": 2.0, "academic": 1.8, "academic_platforms": 1.5},
            "technology":  {"github": 1.8, "stackoverflow": 1.6},
            "news":        {"gdelt": 2.0, "news": 1.8},
            "environment": {"world_bank": 1.5, "un_data": 1.5},
            "legal":       {"government": 1.8, "intl_gov": 1.6},
        }
        for domain in domains:
            boosts = domain_boosts.get(domain, {})
            for col, boost in boosts.items():
                if col in weights:
                    weights[col] = max(weights[col], boost)
        return weights

    async def _generate_queries(self, intent: IntentResult) -> list[str]:
        year = datetime.now().year
        country_str = ", ".join(intent.countries) if "GLOBAL" not in intent.countries else "global"
        prompt = _PLAN_PROMPT.format(
            topic=intent.topic,
            domains=", ".join(intent.domains),
            countries=country_str,
            data_types=", ".join(intent.data_types or ["general"]),
            time_range=intent.time_range or "any",
            year=year,
        )
        try:
            text = await self._call_llm(prompt, _PLAN_SYSTEM)
            if text:
                data = self._parse_json(text)
                if data and "queries" in data:
                    return [str(q) for q in data["queries"][:40] if q]
        except Exception as exc:
            logger.debug("StrategyPlanner LLM failed: %s", exc)

        return self._heuristic_queries(intent.topic, intent.countries, year)

    def _heuristic_queries(self, topic: str, countries: list[str], year: int) -> list[str]:
        base = [
            topic,
            f"{topic} {year}",
            f"{topic} research",
            f"{topic} overview",
            f"{topic} latest news",
            f"{topic} statistics data",
            f"{topic} report analysis",
            f"{topic} challenges opportunities",
        ]
        if "GLOBAL" not in countries:
            for cc in countries[:3]:
                base.extend([f"{topic} {cc}", f"{topic} in {cc} {year}"])
        return base

    def _recommend_depth(self, intent: IntentResult) -> int:
        if "jobs" in intent.domains:
            return 2
        if any(d in intent.domains for d in ("science", "health", "legal")):
            return 3
        return 2

    def _summarize(self, intent: IntentResult, collectors: list[str]) -> str:
        country_str = ", ".join(intent.countries[:3])
        if len(intent.countries) > 3:
            country_str += f" +{len(intent.countries)-3} more"
        return (
            f"Collecting '{intent.topic}' across {len(collectors)} sources "
            f"in domains [{', '.join(intent.domains)}] "
            f"for countries [{country_str}]."
        )

    async def _call_llm(self, prompt: str, system: str) -> str | None:
        from aria.engine.ensemble.providers import resolve_cleaning_llm
        from aria.engine.cleaner.llm_cleaner import _call_anthropic, _call_openai_compat
        provider, model_id, base_url, api_key = resolve_cleaning_llm(None)
        if provider == "anthropic":
            return await _call_anthropic(prompt, model_id, api_key, system, max_tokens=1000, temperature=0.2)
        return await _call_openai_compat(prompt, model_id, api_key, base_url, system, max_tokens=1000, temperature=0.2)

    def _parse_json(self, text: str) -> dict | None:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


# ── Convenience function ──────────────────────────────────────────────────────

async def build_collection_plan(
    query: str,
    domains: list[str] | None = None,
    countries: list[str] | None = None,
) -> CollectionPlan:
    """One-shot: parse intent + build plan. Skip clarification."""
    agent = IntentAgent()
    intent = await agent.analyze(query)

    # Override with explicit selections if provided
    if domains:
        intent.domains = [d for d in domains if d in DOMAINS]
        intent.confidence["domains"] = 1.0
    if countries:
        intent.countries = countries
        intent.confidence["countries"] = 1.0
    intent.ready = True

    planner = StrategyPlanner()
    return await planner.build_plan(intent)
