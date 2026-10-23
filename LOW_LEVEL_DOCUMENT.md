# ARIA Launch Review: Low-Level Document

Audit date: 2026-07-18. Scope: 334 current repository files were inventoried, including Python modules, React/TypeScript, tests, configuration, Docker/Nginx, missions, and README files. No product behavior was changed during this audit.

## Stack And Dependencies

### Runtime

- **Python 3.11+ / FastAPI / Uvicorn / Pydantic:** backend HTTP API, request validation primitives, and server.
- **React 19 / TypeScript / Vite / Tailwind / Radix / TanStack Query:** browser application, components, routing, cached polling, and styling.
- **httpx, aiohttp, requests:** HTTP calls to source services and LLM providers.
- **BeautifulSoup, Playwright, crawl4ai, PyMuPDF, OCR tools, MarkItDown:** web, browser, PDF, and office-file extraction.
- **OpenAI, Anthropic, Ollama-compatible API support:** LLM cleaning, planning, graph, and gap calls.
- **arxiv, feedparser, youtube tools, PyGithub, pyzotero, Redis:** source-specific integrations.
- **networkx, datasketch, sentence-transformers:** graph and optional semantic-dedup features.
- **cryptography:** optional encrypted `credentials.json` file.

### Dependency Risks

- `requirements.txt` uses broad lower bounds rather than a lock file. The Python runtime is not reproducible.
- `aria-report` contains both `package-lock.json` and `pnpm-lock.yaml`; CI uses npm, so the pnpm lock is misleading.
- `openai-whisper`, Playwright, OCR, browser dependencies, and sentence-transformers are heavy operational dependencies but are installed in the default requirement set.

## Major Module Breakdown

### Application Entry And Configuration

- `aria/cli.py` — CLI parsing, API startup, and headless research invocation.
- `aria/config.py` — paths, feature flags, LLM timeout/retry settings, crawler and citation limits.
- `aria/config_llm.py` — a separate LLM configuration model; it is not the main run-resolution path.
- `aria/mission.py` and `aria/engine/mission/__init__.py` — mission YAML defaults, validation, loading, and serialization.
- `aria/api/app.py` — FastAPI construction, middleware, real/demo router registration, and built React serving.

### API And Run State

- `aria/api/run_manager.py` — builds a credential scope, starts background tasks, persists `run_state.json`, records events, reloads historical runs, and maps results to API responses.
- `aria/api/routes/runs.py` — accepts either UI fields or mission YAML and maps UI depth/source choices into mission YAML.
- `aria/api/routes/exports.py` — maps known exports to download endpoints and guards filenames.
- `aria/api/routes/credentials.py` and `verify.py` — save/mask credentials, validate source connectivity, and inspect LLM/Ollama status.
- `aria/api/routes/director.py`, `chat.py`, and `domains.py` — planning conversations, intent analysis, country/domain plans.
- `aria/api/routes/studio.py` — a separate compatibility/demo adapter with a different response format and in-memory fake data.
- `aria/api/middleware/auth.py` and `rate_limit.py` — shared API-key gate and IP-based sliding-window rate limit.

### Research Engine

- `aria/engine/orchestrator/core.py` — main pipeline coordinator. It plans, collects, deduplicates, cleans, scores, enriches, saves, and exports.
- `planning.py`, `collection.py`, `cleaning.py`, `dedup.py`, `enrichment.py`, and `exporting.py` — phase helpers. `core.py` still duplicates most enrichment work instead of invoking `run_enrichment_phase`.
- `collectors/` — source-specific asynchronous collectors. `collection.py` has the actual registry and dynamic importer.
- `cleaner/llm_cleaner.py` — prompts the configured LLM per document and falls back to a local default document shape on an error.
- `intelligence/` — query planning, research director, relevance scoring, semantic deduplication, gap detection, knowledge graph, image extraction, and streaming support.
- `citation/` — extracts citations and uses public academic resolution sources.
- `knowledge_base/kb.py` — SQLite-backed persistent document index.
- `storage/` and `output/` — JSONL store files and JSON/CSV/Markdown/ZIP/HTML report generation.

### Browser Application

- `main.tsx`, `App.tsx`, `AppSidebar.tsx` — app boot, routes, shell, and API-key setup.
- `pages/Launch.tsx` — guided/manual/YAML launch forms and Research Director interaction.
- `pages/Monitor.tsx` — status polling and document preview; its source cards are not backed by actual source events.
- `pages/Report.tsx` — report header, a clean-document table, and four downloads.
- `pages/Settings.tsx` — credential and LLM configuration screens.
- `pages/Sources.tsx` and `hooks/useEnabledSources.ts` — source switches stored locally in the browser, not passed into `Launch.tsx`.
- `lib/api.ts` — API client and browser-local API-key storage.

## Data Flow

`Launch.tsx` sends a topic/source/depth payload to `POST /api/runs`.

`routes/runs.py` creates mission YAML. `RunManager.start_run()` validates the mission, builds a credential environment, creates `data/runs/<id>`, and schedules `_execute_run()`.

`InfoCollectorOrchestrator.run()` uses `planning.py` or a Research Director brief, invokes collector tasks from `_COLLECTOR_REGISTRY`, deduplicates documents, writes raw JSONL, calls the LLM cleaner, scores documents, optionally follows citations, detects gaps, builds a graph, extracts images, writes clean JSONL, stores knowledge-base records, and exports files.

`RunManager` persists state and the React hooks poll `/api/runs/<id>` and `/documents`. The React Report page can download raw JSON, clean JSON, clean CSV, and Markdown.

## Audit Findings

### Critical

**[Product integrity] `aria-report/src/pages/Monitor.tsx:103-143`:** The source pipeline marks sources active with `i % 3 !== 2` → It is a visual simulation, not progress from collectors → Replace it with source-level events from `RunManager.record_event`; otherwise remove it.

**[Product integrity] `aria/api/routes/studio.py:85-230`:** A second Studio API has no-op login, in-memory credentials, fixed `agents_total`, and simulated run progress → Production code contains a fake product surface that can be mistaken for real behavior → Remove it from production registration or isolate it as an explicitly labelled demo fixture.

**[Trust / missing feature] `aria-report/src/pages/Report.tsx` and `aria/api/routes/runs.py:180-215`:** The backend stores raw documents, graph, gaps, images, and a report, but the UI only renders cleaned rows and four downloads → A user cannot verify AI output against captured raw source text or use the strongest intelligence outputs → Build source-review, raw-text, evidence-link, graph/gap, image, HTML, and ZIP UI/API surfaces.

**[Security / privacy] `aria/api/run_manager.py`, `aria/api/routes/credentials.py`:** All API clients share one process-wide run map, run directory tree, and credentials file → There are no accounts, roles, ownership checks, or tenant isolation → Do not launch as multi-user SaaS; add identity, authorization, per-tenant storage, server-side secret management, and audit logging.

### High

**[Broken user setting] `aria-report/src/pages/Sources.tsx`, `hooks/useEnabledSources.ts`, and `pages/Launch.tsx`:** Sources-page switches only change `localStorage`; Launch uses its own state initialized to web/arXiv/Hacker News → A user’s source choice is ignored at launch → Make one shared source-selection state and send it to the API.

**[Incomplete workflow] `aria/engine/orchestrator/core.py:174-180, 453-541` and `aria/api/run_manager.py:374-380`:** `collect_only` can bypass LLM readiness and skips cleaning/gap/graph stages → The run can complete as unprocessed data despite the product’s research-intelligence promise → Remove it from user workflows or rename and design it as an internal ingestion job with an explicit cleaning continuation.

**[Reliability] `aria/api/run_manager.py:92-116, 391-422`:** Runs are `asyncio` tasks in the web process; after restart the manager marks queued/running work failed → Long research work disappears on deploy, crash, or restart → Use a durable worker/job queue with persisted job state, cancellation, retry policy, and resumable checkpoints.

**[Silent partial success] `aria/engine/orchestrator/collection.py:122-157`, `cleaning.py:38-67`, and `core.py`:** Collector and cleaner exceptions are generally logged then replaced by an empty batch or raw documents → A completed run can hide source failures or failed LLM extraction → Report per-source status, failure reasons, expected/actual counts, and mark incomplete runs distinctly.

**[Misleading product claims] `README.md`, `pages/Report.tsx`, `pages/Launch.tsx`, and `routes/runs.py`:** README promises six downloads/ZIP and depth up to 5,000+; UI offers four downloads and source caps constrain output → Users will buy or operate based on capabilities not delivered in the UI → Align documentation, API, UI, and acceptance tests.

**[Deployment security] `docker-compose.yml: ports 8765:8765` and `nginx.conf`:** The API is published directly on host port 8765 as well as proxied by Nginx → It can bypass Nginx controls and is exposed outside the intended web boundary → Remove public API port mapping or bind it to loopback/internal Docker networking only.

### Medium

**[Duplicate logic] `aria/engine/orchestrator/core.py` and `aria/engine/orchestrator/enrichment.py`:** `run_enrichment_phase()` implements the enrichment workflow but the main coordinator repeats that workflow inline → Two future fixes can diverge → Make core call the phase helper or delete the unused helper.

**[Unused/dead behavior] `aria/api/routes/studio.py` and `aria-report/src/lib/api.ts`:** Current React client calls `/api/*`, not `/api/studio/*` → Studio adapter adds maintenance surface without serving this UI → Delete or move to a separate demo application.

**[Inconsistent source catalog] `aria-report/src/lib/sources.ts` and `aria/engine/orchestrator/collection.py`:** The frontend hardcodes a partial source catalog while backend has a larger registry and `/api/sources` endpoint → UI can advertise a source differently from the runtime registry → Serve source metadata from one backend contract.

**[Inconsistent LLM selection] `aria/engine/ensemble/providers.py:build_provider_catalog` and `resolve_cleaning_llm`:** Catalog always advertises Ollama models while run resolution requires an explicit local URL/selection → UI can show an available model that is not actually reachable → Make readiness, catalog, and run validation share one status object.

**[Security design] `aria-report/src/lib/api.ts:8-37` and `Settings.tsx`:** The shared API key is stored in browser `localStorage` → Any script executing in the browser origin can read it → For a real product, replace shared API keys in the browser with session authentication and HTTP-only cookies; at minimum use strict CSP and document this as single-operator only.

**[Authorization gap] `aria/api/routes/exports.py:73-107`:** Download access checks only that a run exists and filename is safe → Any caller with the shared API key can read every run file → Add ownership/role checks once accounts exist.

**[Hardcoded product numbers] `aria/api/routes/studio.py`, `README.md`, and `pages/Launch.tsx`:** Agent totals, source totals, document-depth labels, and limits are independently hardcoded → Product numbers drift from actual behavior → Drive them from a versioned configuration/API contract.

**[Maintainability] `aria/api/app.py:25-31`:** The app silently falls back to demo mode if a broad import raises `ImportError` → A packaging mistake can start an API that looks valid but is fake → Fail startup in production; allow demo only via explicit environment flag.

### Low

**[Naming / structure] `aria/access/*` and `aria/engine/access/*`:** Both namespaces expose access/platform concepts; most outer files are aliases but `web_of_science.py` is unique → The boundary is not obvious → Consolidate under `aria/engine/access` or clearly document why the public wrapper remains.

**[Unused config] `aria/config_llm.py`:** Separate Pydantic LLM configuration exists alongside environment/provider resolution in `engine/ensemble/providers.py` → Two models can drift and confuse maintainers → Consolidate or delete after confirming no external consumer.

**[Operational configuration] `requirements.txt`:** Dependencies have minimum versions only → A future compatible-looking release can change runtime behavior → Generate and use a locked production dependency set.

**[Test determinism] full `pytest -q` run during this audit:** The full backend suite remained running after visible output stopped and was terminated; frontend `vitest` completed with 9 passing tests → CI confidence is incomplete → Identify network/live-service tests, mock them, apply timeouts, and require full completion.

## Test And Launch Evidence

- Frontend: `npm test` completed: 2 files, 9 tests passed.
- Backend focused suite previously passed in this workspace: 128 tests passed. The full `pytest -q` audit run did not finish deterministically and was stopped after more than one minute.
- Frontend production build completed earlier in this workspace; it emitted a large-chunk warning in prior builds.
- CI declares Python tests and frontend build/tests, but it does not run lint, type checking beyond Vite build, security scanning, dependency vulnerability scanning, browser E2E, or a controlled full research run.

## Recommended Test Cases Before Any Launch

1. A successful complete run using a local fixture source and fake LLM response produces every advertised export.
2. Missing/unreachable LLM blocks every user-facing research run with one actionable error.
3. Each enabled source emits real start/success/failure status visible in Monitor.
4. Source-page toggle changes the next launch payload.
5. A report page displays raw captured text, original URL, LLM summary, and claim/source links.
6. API restart during a run either resumes safely or clearly persists an incomplete state without data loss.
7. A user cannot read another user’s credentials, run metadata, documents, or exports.
8. Docker deployment exposes only Nginx publicly and rejects unauthenticated API requests.
9. All backend tests run without network access and finish within a fixed timeout.
