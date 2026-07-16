# ARIA — Agentic Research Intelligence Architecture

ARIA is a fully automated research collection and intelligence platform. Give it a topic and a research goal — it runs selected source collectors in parallel, deduplicates and stores every document, then uses a connected AI model to extract structured, relevance-scored data. Results are available as research exports and an HTML report.

## Quickstart

```bash
pip install -r requirements.txt
playwright install chromium
python -m aria.cli --serve-api   # start the API backend
```

Then open the React UI:

```bash
cd aria-report
npm install
npm run dev
```

Or run headless from the CLI:

```bash
python -m aria.cli --topic "AI safety benchmarks 2025" --mission missions/examples/default.yaml
```

## What ARIA does

1. **Query expansion** — LLM expands your topic into 5–8 diverse search queries before any agent fires
2. **Parallel collection** — 18 web agents (search, academic, Reddit, YouTube, Wikipedia, Stack Overflow, and more) run simultaneously via `asyncio.gather`
3. **LLM Providers** — select from OpenRouter, OpenAI, or Anthropic (cloud) or local Ollama; optionally enable multiple models in parallel
4. **Zotero import** — import your existing Zotero library or a specific collection as additional source documents
5. **Deduplication** — URL-hash + content-fingerprint dedup before any document is stored
6. **Smart Cleaning** — one LLM call per document: detects content type (10 categories), applies the matching extraction strategy, scores relevance 0–1 against your research goal
7. **Export** — JSON, CSV, Markdown, HTML report — all sortable by relevance score
8. **Download** — 6 one-click formats from the React UI including raw data and a full ZIP bundle

## Sources

### Free (no credentials needed)

| Source | Details |
|---|---|
| Web Search | SerpAPI / DuckDuckGo · multi-query expansion |
| PDF Discovery | Finds and extracts PDF documents from the web |
| Academic | arXiv · PubMed · Semantic Scholar |
| YouTube | Search + transcript extraction via yt-dlp |
| Reddit | reddit.com/search.json |
| Hacker News | Algolia HN API |
| Wikipedia | MediaWiki search + REST summary |
| Stack Overflow | Stack Exchange public API |
| Medium | BeautifulSoup scraping |
| Dev.to | dev.to/api/articles |
| Substack | RSS feed reader |
| RSS / Atom | feedparser — any feed URL from mission YAML |
| News | BBC · Reuters · AP · NPR · Guardian · Wired · Ars Technica (RSS) |
| Government | data.gov catalog API + DuckDuckGo site:.gov |
| GitHub | DuckDuckGo site:github.com fallback |
| Multilingual | DuckDuckGo across 12 language regions (de/fr/es/zh/ja/pt/ar/ru…) |
| User URLs | Explicit URLs you provide directly |

### Auth required (silently skipped if no token)

| Source | Credentials |
|---|---|
| Twitter / X | `TWITTER_BEARER_TOKEN` |
| Notion | `NOTION_TOKEN` integration token |
| Slack | `SLACK_TOKEN` with search:read scope |
| Podcast | RSS + opt-in Whisper transcription (`PODCAST_TRANSCRIBE=true`) |
| Vimeo | `VIMEO_ACCESS_TOKEN` |
| **Zotero** | local app (no key) or cloud API key + library ID |
| GitHub (full) | `GITHUB_TOKEN` — PyGithub API, repos + issues |
| News (enhanced) | `NEWS_API_KEY` (NewsAPI.org) · `GNEWS_API_KEY` (GNews) |
| Government (enhanced) | `REGULATIONS_GOV_KEY` (regulations.gov) |
| **IEEE Xplore** | `IEEE_API_KEY` |
| **Elsevier** | `ELSEVIER_API_KEY` |
| **Springer Nature** | `SPRINGER_API_KEY` |
| **JSTOR** | `JSTOR_SESSION_COOKIE` (institutional) |
| **ACM Digital Library** | `ACM_SESSION_COOKIE` (institutional) |

### LLM Providers (configurable)

**Cloud:** OpenRouter (meta-provider) · OpenAI (GPT models) · Anthropic (Claude models)

**Local:** Ollama (llama3.1, llama3.2, etc.)

Users can select one or mix multiple models.

## Research depth levels

| Level | Name | Documents | Deep Crawl |
|---|---|---|---|
| 1 | Surface | ~50 | None |
| 2 | Standard | ~200 | None |
| 3 | Deep | ~500 | 1 BFS level |
| 4 | Thorough | ~1,500 | 2 BFS levels |
| 5 | Maximum | 5,000+ | Full recursive |

## Smart Cleaning Agent

No configuration required. The LLM auto-detects content type and applies the correct extraction strategy:

| Type | What gets extracted |
|---|---|
| `academic_paper` | Research question, methodology, findings, limitations |
| `news_article` | Who/what/when/where/why, key quotes, named sources |
| `forum_post` | Core question, consensus answer, vote/score |
| `social_media` | Core claim, evidence offered, credibility signals |
| `technical_doc` | Concept, step-by-step instructions, code, version notes |
| `video_transcript` | Key points, named examples, speaker conclusions |
| `encyclopedia` | Definition, key facts, related concepts |
| `opinion_essay` | Thesis, evidence, counter-arguments, conclusion |
| `gov_policy` | Policy name, date, who is affected, penalties |
| `data_report` | Headline stats, trends, source, methodology |

Power users can add a global override or per-source override in the UI. When left blank, smart mode handles everything.

## Zotero integration

ARIA can import your Zotero library as a source. Each item's URL or PDF attachment is scraped and flows through the normal cleaning pipeline.

**Local mode** (Zotero desktop must be running — no API key needed):

```yaml
collection:
  sources:
    enabled: [zotero, web, academic]
  zotero_config:
    mode: local
    collection_key: ""      # leave blank to import all items
    library_type: user
```

**Cloud mode** (api.zotero.org):

```yaml
collection:
  sources:
    enabled: [zotero]
  zotero_config:
    mode: cloud
    library_id: "1234567"
    api_key: "your_api_key_here"
    library_type: user
    collection_key: "ABC123"   # optional
    max_items: 500
```

Or set via environment variables:

```env
ZOTERO_API_KEY=your_api_key_here
ZOTERO_LIBRARY_ID=1234567
ZOTERO_LIBRARY_TYPE=user
```

## Downloads

| Group | Format | Contents |
|---|---|---|
| Raw | JSON | Full envelope — all documents with original text + metadata |
| Raw | CSV | Flat table — url, title, source_type, platform, word_count, text (3000 chars) |
| Clean | JSON | Structured array — all output schema fields per document |
| Clean | CSV | One row per document, all schema columns |
| Clean | Markdown | Human-readable report — titles, summaries, source links |
| Bundle | ZIP | `clean/` + `raw/` in all formats |

All downloads bypass the 100-document UI preview cap and return the complete dataset.

## Environment variables

```env
# Search
SERPAPI_KEY=

# LLM providers
LLM_PROVIDER=openrouter        # openrouter | openai | anthropic | ollama
OPENROUTER_API_KEY=
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-3-5-haiku-latest
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Zotero
ZOTERO_API_KEY=
ZOTERO_LIBRARY_ID=
ZOTERO_LIBRARY_TYPE=user

# Authenticated web sources
TWITTER_BEARER_TOKEN=
NOTION_TOKEN=
SLACK_TOKEN=
VIMEO_ACCESS_TOKEN=
GITHUB_TOKEN=

# News providers (optional — RSS feeds always work without keys)
NEWS_API_KEY=
GNEWS_API_KEY=

# Government (optional — data.gov always works without key)
REGULATIONS_GOV_KEY=

# Academic platforms (subscription-based)
IEEE_API_KEY=
ELSEVIER_API_KEY=
SPRINGER_API_KEY=
JSTOR_SESSION_COOKIE=
ACM_SESSION_COOKIE=

# Podcast transcription (optional — requires openai-whisper)
PODCAST_TRANSCRIBE=false        # set to true to enable Whisper transcription
WHISPER_MODEL=base              # tiny | base | small | medium | large

# Multilingual search
MULTILINGUAL_REGIONS=de-de,fr-fr,es-es,zh-cn   # comma-separated DuckDuckGo region codes

# Open access (set your real email — required by Unpaywall TOS)
UNPAYWALL_EMAIL=

# Runtime
LLM_MAX_TOKENS=2000
LLM_TEMPERATURE=0.1
ARIA_API_PORT=8765
SHARED_MEMORY_BACKEND=dict     # dict | redis
REDIS_URL=redis://localhost:6379
```

## Project layout

```text
aria/                    Python package
  api/                   FastAPI backend (routes, middleware, run manager)
  engine/                Research engine: orchestrator, collectors, cleaner,
                         intelligence, storage, export
  access/                Credential, session, paywall management
  types/ utils/          Shared types and helpers
missions/examples/       Mission YAML templates
credentials/             Gitignored credential storage
aria-report/             React web UI
docs/                    Architecture documentation
tests/                   Python test suite
```

## Security defaults

- **API auth is required by default.** Set `ARIA_API_KEY`; if unset, the
  server generates a one-session key and prints it in the log. Local dev
  (`aria --serve-api` on a loopback bind) disables auth automatically;
  `ARIA_API_KEY_REQUIRED=false` disables it explicitly (unsafe).
- **The API binds 127.0.0.1 by default.** Pass `--api-host 0.0.0.0` (or set
  `ARIA_API_HOST`) to expose it, ideally behind the provided nginx config.
- **robots.txt is respected** by the web scraper and link crawler
  (`ARIA_RESPECT_ROBOTS=false` to opt out for sites you own).
- **Unpaywall requires your real email** (`UNPAYWALL_EMAIL`); the route is
  skipped when unset.
- **Credentials can be encrypted at rest.** Set `ARIA_CREDENTIALS_KEY` (a
  Fernet key) and `credentials.json` is written encrypted with owner-only
  file permissions; existing plaintext files keep loading.

## CLI reference

```bash
# Full run from a mission file
python -m aria.cli --mission missions/examples/default.yaml

# Quick topic run
python -m aria.cli --topic "transformer attention mechanisms"

# Start the API server
python -m aria.cli --serve-api

# Collection-only pass: gather raw data, skip cleaning
python -m aria.cli --mission missions/examples/default.yaml --collect-only --run-id my-run

# Cleaning-only pass: clean the raw data from the same run
python -m aria.cli --mission missions/examples/default.yaml --clean-only --run-id my-run

# Cleaning-only pass over an explicit raw data directory
python -m aria.cli --mission missions/examples/default.yaml --clean-only --raw-dir data/runs/my-run/raw

# Resume an interrupted run
python -m aria.cli --mission missions/examples/default.yaml --resume

# Validate credentials and exit
python -m aria.cli --mission missions/examples/default.yaml --validate-credentials
```
