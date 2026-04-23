"""Domain registry, country registry, and planning for ARIA 5.0."""

from aria.engine.domains.registry import (
    DOMAINS,
    DomainConfig,
    get_all_domains,
    get_citation_depth,
    get_domain,
    get_query_modifiers,
    resolve_collectors,
)
from aria.engine.domains.countries import (
    COUNTRIES,
    REGIONS,
    CountryConfig,
    expand_region,
    get_country,
    get_gov_search_query,
    get_world_bank_codes,
    resolve_countries,
)
from aria.engine.domains.planner import (
    CollectionPlan,
    IntentAgent,
    IntentResult,
    StrategyPlanner,
    build_collection_plan,
)

__all__ = [
    "DOMAINS", "DomainConfig", "get_all_domains", "get_citation_depth",
    "get_domain", "get_query_modifiers", "resolve_collectors",
    "COUNTRIES", "REGIONS", "CountryConfig", "expand_region",
    "get_country", "get_gov_search_query", "get_world_bank_codes", "resolve_countries",
    "CollectionPlan", "IntentAgent", "IntentResult", "StrategyPlanner",
    "build_collection_plan",
]
