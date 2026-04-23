"""Country registry — per-country source configs, gov domains, job boards, API codes."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CountryConfig:
    code: str                            # ISO 3166-1 alpha-2 or special code
    name: str
    flag: str
    gov_domain: str                      # e.g. .gov, .gov.uk, .gov.in
    open_data_url: str                   # official open data portal
    job_board_collectors: list[str]      # collector keys for jobs in this country
    language: str                        # primary BCP-47 language code
    world_bank_code: str                 # World Bank API country code
    imf_code: str                        # IMF country code
    region: str                          # AMERICAS / EUROPE / ASIA / AFRICA / MENA / GLOBAL
    search_tld: str = ""                 # Google/DDG country TLD (e.g. .co.in, .co.uk)
    extra_gov_domains: list[str] = field(default_factory=list)  # additional gov TLDs


COUNTRIES: dict[str, CountryConfig] = {

    # ── Americas ──────────────────────────────────────────────────────────────
    "US": CountryConfig("US", "United States", "🇺🇸", ".gov", "data.gov",
                        ["usajobs", "indeed", "linkedin_jobs"], "en", "US", "US", "AMERICAS"),
    "CA": CountryConfig("CA", "Canada", "🇨🇦", ".gc.ca", "open.canada.ca",
                        ["jobbank", "indeed_ca", "linkedin_jobs"], "en", "CAN", "CA", "AMERICAS"),
    "BR": CountryConfig("BR", "Brazil", "🇧🇷", ".gov.br", "dados.gov.br",
                        ["catho", "infojobs_br", "linkedin_jobs"], "pt", "BRA", "BR", "AMERICAS"),
    "MX": CountryConfig("MX", "Mexico", "🇲🇽", ".gob.mx", "datos.gob.mx",
                        ["occ_mundial", "indeed_mx", "linkedin_jobs"], "es", "MEX", "MX", "AMERICAS"),
    "AR": CountryConfig("AR", "Argentina", "🇦🇷", ".gob.ar", "datos.gob.ar",
                        ["bumeran", "computrabajo_ar"], "es", "ARG", "AR", "AMERICAS"),
    "CL": CountryConfig("CL", "Chile", "🇨🇱", ".gob.cl", "datos.gob.cl",
                        ["laborum", "linkedin_jobs"], "es", "CHL", "CL", "AMERICAS"),
    "CO": CountryConfig("CO", "Colombia", "🇨🇴", ".gov.co", "datos.gov.co",
                        ["computrabajo_co", "linkedin_jobs"], "es", "COL", "CO", "AMERICAS"),

    # ── Europe ───────────────────────────────────────────────────────────────
    "UK": CountryConfig("UK", "United Kingdom", "🇬🇧", ".gov.uk", "data.gov.uk",
                        ["reed", "jobs_ac_uk", "indeed_uk", "linkedin_jobs"], "en",
                        "GBR", "GBR", "EUROPE", ".co.uk"),
    "EU": CountryConfig("EU", "European Union", "🇪🇺", ".europa.eu", "data.europa.eu",
                        ["eures", "linkedin_jobs"], "multi", "EUU", "EU", "EUROPE"),
    "DE": CountryConfig("DE", "Germany", "🇩🇪", ".de", "govdata.de",
                        ["stepstone_de", "xing", "linkedin_jobs"], "de",
                        "DEU", "DEU", "EUROPE", ".de",
                        extra_gov_domains=["bundesregierung.de"]),
    "FR": CountryConfig("FR", "France", "🇫🇷", ".gouv.fr", "data.gouv.fr",
                        ["pole_emploi", "apec_fr", "linkedin_jobs"], "fr",
                        "FRA", "FR", "EUROPE", ".fr"),
    "ES": CountryConfig("ES", "Spain", "🇪🇸", ".gob.es", "datos.gob.es",
                        ["infojobs_es", "linkedin_jobs"], "es",
                        "ESP", "ES", "EUROPE", ".es"),
    "IT": CountryConfig("IT", "Italy", "🇮🇹", ".gov.it", "dati.gov.it",
                        ["infojobs_it", "linkedin_jobs"], "it",
                        "ITA", "IT", "EUROPE", ".it"),
    "NL": CountryConfig("NL", "Netherlands", "🇳🇱", ".nl", "data.overheid.nl",
                        ["indeed_nl", "linkedin_jobs"], "nl",
                        "NLD", "NL", "EUROPE", ".nl"),
    "SE": CountryConfig("SE", "Sweden", "🇸🇪", ".se", "oppnadata.se",
                        ["arbetsformedlingen", "linkedin_jobs"], "sv",
                        "SWE", "SE", "EUROPE", ".se"),
    "PL": CountryConfig("PL", "Poland", "🇵🇱", ".gov.pl", "dane.gov.pl",
                        ["pracuj_pl", "linkedin_jobs"], "pl",
                        "POL", "PL", "EUROPE", ".pl"),
    "CH": CountryConfig("CH", "Switzerland", "🇨🇭", ".admin.ch", "opendata.swiss",
                        ["jobs_ch", "linkedin_jobs"], "de", "CHE", "CH", "EUROPE"),

    # ── Asia-Pacific ─────────────────────────────────────────────────────────
    "IN": CountryConfig("IN", "India", "🇮🇳", ".gov.in", "data.gov.in",
                        ["naukri", "shine", "foundit", "linkedin_jobs"], "hi",
                        "IND", "IN", "ASIA", ".co.in",
                        extra_gov_domains=["india.gov.in"]),
    "CN": CountryConfig("CN", "China", "🇨🇳", ".gov.cn", "data.stats.gov.cn",
                        ["zhaopin", "liepin", "51job"], "zh",
                        "CHN", "CN", "ASIA", ".cn"),
    "JP": CountryConfig("JP", "Japan", "🇯🇵", ".go.jp", "e-stat.go.jp",
                        ["indeed_jp", "doda", "rikunabi"], "ja",
                        "JPN", "JP", "ASIA", ".co.jp"),
    "AU": CountryConfig("AU", "Australia", "🇦🇺", ".gov.au", "data.gov.au",
                        ["seek", "indeed_au", "linkedin_jobs"], "en",
                        "AUS", "AU", "ASIA", ".com.au"),
    "SG": CountryConfig("SG", "Singapore", "🇸🇬", ".gov.sg", "data.gov.sg",
                        ["jobstreet_sg", "indeed_sg", "linkedin_jobs"], "en",
                        "SGP", "SG", "ASIA"),
    "KR": CountryConfig("KR", "South Korea", "🇰🇷", ".go.kr", "data.go.kr",
                        ["saramin", "incruit", "linkedin_jobs"], "ko",
                        "KOR", "KR", "ASIA", ".co.kr"),
    "ID": CountryConfig("ID", "Indonesia", "🇮🇩", ".go.id", "data.go.id",
                        ["jobstreet_id", "indeed_id"], "id",
                        "IDN", "ID", "ASIA"),
    "PH": CountryConfig("PH", "Philippines", "🇵🇭", ".gov.ph", "data.gov.ph",
                        ["jobstreet_ph", "indeed_ph"], "en",
                        "PHL", "PH", "ASIA"),
    "MY": CountryConfig("MY", "Malaysia", "🇲🇾", ".gov.my", "data.gov.my",
                        ["jobstreet_my", "linkedin_jobs"], "ms",
                        "MYS", "MY", "ASIA"),
    "TH": CountryConfig("TH", "Thailand", "🇹🇭", ".go.th", "data.go.th",
                        ["jobtopgun", "linkedin_jobs"], "th",
                        "THA", "TH", "ASIA"),
    "PK": CountryConfig("PK", "Pakistan", "🇵🇰", ".gov.pk", "data.gov.pk",
                        ["rozee_pk", "linkedin_jobs"], "ur",
                        "PAK", "PK", "ASIA"),
    "BD": CountryConfig("BD", "Bangladesh", "🇧🇩", ".gov.bd", "data.gov.bd",
                        ["bdjobs", "linkedin_jobs"], "bn",
                        "BGD", "BD", "ASIA"),
    "VN": CountryConfig("VN", "Vietnam", "🇻🇳", ".gov.vn", "data.gov.vn",
                        ["topdev", "linkedin_jobs"], "vi",
                        "VNM", "VN", "ASIA"),
    "NZ": CountryConfig("NZ", "New Zealand", "🇳🇿", ".govt.nz", "data.govt.nz",
                        ["seek_nz", "linkedin_jobs"], "en",
                        "NZL", "NZ", "ASIA"),

    # ── Africa ───────────────────────────────────────────────────────────────
    "ZA": CountryConfig("ZA", "South Africa", "🇿🇦", ".gov.za", "data.gov.za",
                        ["pnet", "careers24", "linkedin_jobs"], "en",
                        "ZAF", "ZA", "AFRICA"),
    "NG": CountryConfig("NG", "Nigeria", "🇳🇬", ".gov.ng", "data.gov.ng",
                        ["jobberman", "ngcareers"], "en",
                        "NGA", "NG", "AFRICA"),
    "KE": CountryConfig("KE", "Kenya", "🇰🇪", ".go.ke", "opendata.go.ke",
                        ["brightermonday", "fuzu"], "en",
                        "KEN", "KE", "AFRICA"),
    "ET": CountryConfig("ET", "Ethiopia", "🇪🇹", ".gov.et", "",
                        ["ethiojobs"], "am",
                        "ETH", "ET", "AFRICA"),
    "GH": CountryConfig("GH", "Ghana", "🇬🇭", ".gov.gh", "data.gov.gh",
                        ["jobsinghana", "linkedin_jobs"], "en",
                        "GHA", "GH", "AFRICA"),
    "EG": CountryConfig("EG", "Egypt", "🇪🇬", ".gov.eg", "data.gov.eg",
                        ["wuzzuf", "bayt_eg"], "ar",
                        "EGY", "EG", "MENA"),
    "TZ": CountryConfig("TZ", "Tanzania", "🇹🇿", ".go.tz", "",
                        ["fuzu_tz", "linkedin_jobs"], "sw",
                        "TZA", "TZ", "AFRICA"),

    # ── MENA ─────────────────────────────────────────────────────────────────
    "AE": CountryConfig("AE", "UAE", "🇦🇪", ".gov.ae", "bayanat.ae",
                        ["bayt_ae", "gulftalent", "linkedin_jobs"], "ar",
                        "ARE", "AE", "MENA"),
    "SA": CountryConfig("SA", "Saudi Arabia", "🇸🇦", ".gov.sa", "data.gov.sa",
                        ["bayt_sa", "gulftalent", "linkedin_jobs"], "ar",
                        "SAU", "SA", "MENA"),
    "QA": CountryConfig("QA", "Qatar", "🇶🇦", ".gov.qa", "",
                        ["bayt_qa", "linkedin_jobs"], "ar",
                        "QAT", "QA", "MENA"),
    "TR": CountryConfig("TR", "Turkey", "🇹🇷", ".gov.tr", "data.gov.tr",
                        ["kariyer_net", "linkedin_jobs"], "tr",
                        "TUR", "TR", "MENA"),
    "IL": CountryConfig("IL", "Israel", "🇮🇱", ".gov.il", "data.gov.il",
                        ["drushim", "linkedin_jobs"], "he",
                        "ISR", "IL", "MENA"),

    # ── Special / Global ─────────────────────────────────────────────────────
    "GLOBAL": CountryConfig("GLOBAL", "Global", "🌍", "", "",
                            ["linkedin_jobs", "un_careers", "worldbank_jobs", "indeed"], "en",
                            "WLD", "WLD", "GLOBAL"),
}


REGIONS: dict[str, list[str]] = {
    "AMERICAS": ["US", "CA", "BR", "MX", "AR", "CL", "CO"],
    "EUROPE":   ["UK", "EU", "DE", "FR", "ES", "IT", "NL", "SE", "PL", "CH"],
    "ASIA":     ["IN", "CN", "JP", "AU", "SG", "KR", "ID", "PH", "MY", "TH", "PK", "BD", "VN", "NZ"],
    "AFRICA":   ["ZA", "NG", "KE", "ET", "GH", "TZ"],
    "MENA":     ["AE", "SA", "QA", "TR", "IL", "EG"],
    "GLOBAL":   ["GLOBAL"],
}


def get_country(code: str) -> CountryConfig | None:
    return COUNTRIES.get(code.upper())


def expand_region(code: str) -> list[str]:
    """Expand a region code to country codes, or return [code] if it's already a country."""
    code = code.upper()
    if code in REGIONS:
        return REGIONS[code]
    if code in COUNTRIES:
        return [code]
    return []


def resolve_countries(codes: list[str]) -> list[CountryConfig]:
    """Expand region codes and return CountryConfig objects, deduped."""
    seen: set[str] = set()
    result: list[CountryConfig] = []
    for code in codes:
        for country_code in expand_region(code) or [code]:
            if country_code not in seen:
                cfg = COUNTRIES.get(country_code)
                if cfg:
                    seen.add(country_code)
                    result.append(cfg)
    return result


def get_gov_search_query(country_code: str, base_query: str) -> str:
    """Build a site:-filtered government search query for a country."""
    cfg = COUNTRIES.get(country_code.upper())
    if not cfg or not cfg.gov_domain:
        return base_query
    return f"site:{cfg.gov_domain} {base_query}"


def get_world_bank_codes(country_codes: list[str]) -> list[str]:
    """Return World Bank API codes for given country list."""
    codes: list[str] = []
    for code in country_codes:
        cfg = COUNTRIES.get(code.upper())
        if cfg and cfg.world_bank_code:
            codes.append(cfg.world_bank_code)
    return list(set(codes))
