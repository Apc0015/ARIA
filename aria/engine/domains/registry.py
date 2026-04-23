"""Domain registry — maps each research domain to its collector set and metadata."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DomainConfig:
    id: str
    label: str
    description: str
    icon: str
    # Collector names — must match source_map keys in orchestrator
    collectors: list[str]
    # Always add these to every domain run (general fallbacks)
    always_include: list[str] = field(default_factory=lambda: ["web", "pdf"])
    # Added to LLM-generated queries to sharpen results
    query_modifiers: list[str] = field(default_factory=list)
    # What kind of output this domain produces
    data_types: list[str] = field(default_factory=list)
    # Whether results should be filtered by country
    country_aware: bool = True
    # How deep to follow citation chains (0 = off)
    citation_depth: int = 1
    # Suggested depth level (1-5) for this domain
    default_depth: int = 2


DOMAINS: dict[str, DomainConfig] = {

    "jobs": DomainConfig(
        id="jobs",
        label="Jobs & Careers",
        description="Job listings, vacancies, internships, career opportunities",
        icon="💼",
        collectors=["jobs_boards", "linkedin", "reddit", "web"],
        always_include=["web"],
        query_modifiers=["job vacancy hiring", "career opportunity"],
        data_types=["vacancies", "listings"],
        country_aware=True,
        citation_depth=0,
        default_depth=2,
    ),

    "health": DomainConfig(
        id="health",
        label="Health & Medicine",
        description="Medical research, clinical data, public health, WHO statistics",
        icon="🏥",
        collectors=["who", "clinical_trials", "academic", "academic_platforms",
                    "pubmed_enhanced", "news", "reddit", "youtube", "web", "pdf"],
        query_modifiers=["medical clinical health research"],
        data_types=["research", "statistics", "policy", "clinical"],
        country_aware=True,
        citation_depth=2,
        default_depth=3,
    ),

    "finance": DomainConfig(
        id="finance",
        label="Finance & Economics",
        description="Economic data, financial markets, World Bank, IMF, company filings",
        icon="💰",
        collectors=["world_bank", "imf", "fred", "eurostat", "sec_edgar",
                    "news", "web", "pdf", "reddit"],
        query_modifiers=["financial economic data statistics"],
        data_types=["statistics", "filings", "reports", "market_data"],
        country_aware=True,
        citation_depth=1,
        default_depth=2,
    ),

    "government": DomainConfig(
        id="government",
        label="Government & Policy",
        description="Government portals, legislation, policy documents, regulations",
        icon="🏛️",
        collectors=["government", "intl_gov", "un_data", "web", "pdf", "news"],
        query_modifiers=["government policy regulation official"],
        data_types=["policy", "legislation", "statistics", "reports"],
        country_aware=True,
        citation_depth=1,
        default_depth=2,
    ),

    "science": DomainConfig(
        id="science",
        label="Science & Research",
        description="Academic papers, preprints, datasets — 450M+ sources",
        icon="🔬",
        collectors=["open_alex", "academic", "academic_platforms",
                    "clinical_trials", "web", "pdf", "youtube"],
        query_modifiers=["research paper study findings"],
        data_types=["research", "papers", "datasets"],
        country_aware=False,
        citation_depth=2,
        default_depth=3,
    ),

    "technology": DomainConfig(
        id="technology",
        label="Technology",
        description="GitHub, Stack Overflow, tech news, developer resources",
        icon="💻",
        collectors=["github", "stackoverflow", "devto", "medium",
                    "hackernews", "reddit", "academic", "web", "youtube"],
        query_modifiers=["technology software development technical"],
        data_types=["technical", "code", "documentation", "discussion"],
        country_aware=False,
        citation_depth=1,
        default_depth=2,
    ),

    "legal": DomainConfig(
        id="legal",
        label="Legal",
        description="Court opinions, patents, legislation, regulatory documents",
        icon="⚖️",
        collectors=["government", "intl_gov", "web", "pdf", "news", "academic"],
        query_modifiers=["legal law regulation court ruling legislation"],
        data_types=["legal", "policy", "legislation"],
        country_aware=True,
        citation_depth=2,
        default_depth=2,
    ),

    "news": DomainConfig(
        id="news",
        label="News & Media",
        description="Global news in 100+ languages via GDELT, RSS, and major outlets",
        icon="📰",
        collectors=["gdelt", "news", "rss", "reddit", "hackernews",
                    "twitter", "web", "substack"],
        query_modifiers=["news latest current events"],
        data_types=["news", "opinion", "analysis"],
        country_aware=True,
        citation_depth=0,
        default_depth=2,
    ),

    "environment": DomainConfig(
        id="environment",
        label="Environment & Climate",
        description="Climate data, environmental policy, satellite data, UN Environment",
        icon="🌍",
        collectors=["world_bank", "un_data", "who", "news",
                    "academic", "web", "pdf", "reddit", "open_alex"],
        query_modifiers=["environment climate ecology sustainability"],
        data_types=["statistics", "research", "policy", "data"],
        country_aware=True,
        citation_depth=2,
        default_depth=3,
    ),

    "education": DomainConfig(
        id="education",
        label="Education",
        description="Academic content, open courseware, research in education",
        icon="📚",
        collectors=["wikipedia", "youtube", "open_alex", "web",
                    "pdf", "academic", "reddit"],
        query_modifiers=["education learning academic curriculum"],
        data_types=["educational", "research", "courses"],
        country_aware=True,
        citation_depth=1,
        default_depth=2,
    ),

    "social": DomainConfig(
        id="social",
        label="Social & Community",
        description="Social media, forums, community discussions",
        icon="👥",
        collectors=["reddit", "twitter", "linkedin", "hackernews",
                    "web", "youtube", "substack"],
        query_modifiers=["community discussion opinion social"],
        data_types=["social", "discussion", "opinion"],
        country_aware=True,
        citation_depth=0,
        default_depth=1,
    ),

    "business": DomainConfig(
        id="business",
        label="Business & Market Intelligence",
        description="Company data, market trends, startups, industry analysis",
        icon="📊",
        collectors=["web", "news", "reddit", "hackernews", "sec_edgar",
                    "linkedin", "medium", "devto", "open_alex"],
        query_modifiers=["business market industry company analysis"],
        data_types=["market_data", "analysis", "reports"],
        country_aware=True,
        citation_depth=1,
        default_depth=2,
    ),
}


def get_domain(domain_id: str) -> DomainConfig | None:
    return DOMAINS.get(domain_id)


def get_all_domains() -> list[DomainConfig]:
    return list(DOMAINS.values())


def resolve_collectors(domain_ids: list[str]) -> list[str]:
    """Return deduplicated collector list for a set of domains."""
    seen: set[str] = set()
    result: list[str] = []
    for did in domain_ids:
        cfg = DOMAINS.get(did)
        if not cfg:
            continue
        for col in cfg.collectors + cfg.always_include:
            if col not in seen:
                seen.add(col)
                result.append(col)
    return result


def get_citation_depth(domain_ids: list[str]) -> int:
    """Return max citation depth across selected domains."""
    if not domain_ids:
        return 0
    return max((DOMAINS[d].citation_depth for d in domain_ids if d in DOMAINS), default=0)


def get_query_modifiers(domain_ids: list[str]) -> list[str]:
    mods: list[str] = []
    for did in domain_ids:
        cfg = DOMAINS.get(did)
        if cfg:
            mods.extend(cfg.query_modifiers)
    return list(set(mods))
