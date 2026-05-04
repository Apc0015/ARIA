# CHANGES

## 2026-05-03 — Source Upgrades

### Change 1: Web Extraction Chain Upgrade

`aria/engine/collectors/web/scraper.py` now has a modernised fallback chain:

1. Camofox — anti-detection browser for known-blocked domains
2. Plain aiohttp — fast path for cooperative sites
3. **NEW: Jina AI Reader** — proxy-based extraction via `r.jina.ai` (no API key)
4. **NEW: crawl4ai** — JS-aware crawling with Markdown output (`pip install crawl4ai>=0.6.0`)
5. Retry Camofox — last resort for non-blocked domains

Each fallback now has a one-line comment explaining its purpose. Also fixed a
broken relative import (`..utils` → `...utils`) and added `base.py` re-export
stubs to all collector subdirectories so tests can import collectors directly.

---

### Change 2: OSINT Advanced Source Grouping

Sources are now classified as `standard` or `advanced` via a new `group` field:

**Advanced sources (opt-in, hidden by default in the Launch UI):**
- Shodan, Censys, VirusTotal, HaveIBeenPwned, Whoxy, Hunter, Social Searcher (OSINT)
- Jobs Boards (niche/specialized)

**UI change:** Launch page has a collapsible "Advanced — Cybersecurity & OSINT" section
below the standard source grid. Advanced sources default to unchecked.

**API:** New `GET /api/sources` endpoint returns all source IDs with their group.

---

### Change 3: 9 New Source Collectors

| Collector | File | API Endpoint | Credentials |
|-----------|------|-------------|-------------|
| CrossRef | `academic/crossref.py` | `api.crossref.org/works` | None (UNPAYWALL_EMAIL optional) |
| CORE.ac.uk | `academic/core_ac.py` | `api.core.ac.uk/v3/search/works` | CORE_API_KEY optional |
| Europe PMC | `academic/europe_pmc.py` | `ebi.ac.uk/europepmc/...` | None |
| SSRN | `academic/ssrn.py` | DuckDuckGo + BeautifulSoup scrape | None |
| BASE Search | `academic/base_search.py` | `api.base-search.net/...` | None |
| Wikidata | `knowledge/wikidata.py` | `wikidata.org/w/api.php` | None |
| Internet Archive | `data/internet_archive.py` | `archive.org/advancedsearch.php` | None |
| ProPublica | `specialized/propublica.py` | Congress API + Nonprofit Explorer | PROPUBLICA_API_KEY optional |
| Mastodon | `social/mastodon.py` | `mastodon.social/api/v2/search` | MASTODON_ACCESS_TOKEN optional |

All 9 collectors are registered in `aria/api/routes/sources.py` and
`aria-report/src/lib/sources.ts`. One pytest test per collector, all passing.

New env vars: `CORE_API_KEY`, `PROPUBLICA_API_KEY`, `MASTODON_ACCESS_TOKEN`
(documented in `.env.example`).
