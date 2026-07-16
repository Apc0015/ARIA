# Changelog

## 5.1.0 — 2026-07-16

Production-hardening release driven by the full-team readiness audit
(3 critical, 5 high, 4 medium, 2 low findings — all resolved).

### Security
- **API auth is fail-closed.** Auth is required by default; when
  `ARIA_API_KEY` is unset a one-session key is generated and logged.
  Explicit opt-out via `ARIA_API_KEY_REQUIRED=false`. Docker compose
  refuses to start without a key.
- **Per-run credential isolation.** User LLM selections and credentials
  no longer touch process-wide `os.environ`; they flow through
  `CredentialScope` and explicit overrides to `resolve_cleaning_llm()`.
  `Config.with_llm_override` (env-mutating) was removed.
- **Rate limiting hardened.** Identity is the client IP (proxy-aware via
  `ARIA_TRUST_PROXY`), not the attacker-controlled `X-API-Key` header;
  tracked clients are LRU-capped.
- **Secrets scrubbed** from `/api/credentials/verify` and
  `/api/llm/status` error responses (shared `aria/utils/scrub.py`).
- **Credentials at rest:** `credentials.json` is written with `0600`
  permissions; optional Fernet encryption via `ARIA_CREDENTIALS_KEY`
  (wrong key fails safe with a clear log).
- CLI binds `127.0.0.1` by default and honors `ARIA_API_HOST`/`ARIA_API_PORT`.

### Reliability & performance
- **Concurrent runs actually run concurrently.** The process-wide env
  lock is now a readers-writer lock: runs whose credentials match the
  process environment execute in parallel; only runs needing different
  credentials serialize.
- `.env` is loaded explicitly by `aria.config` (previously only as an
  import side effect of crawl4ai).
- Docker image installs Playwright Chromium so browser-based collectors
  work in the container.
- nginx: `proxy_buffering off` for the streaming chat route.
- Frontend: route-level code splitting (main bundle 641 kB → 461 kB).

### Compliance
- robots.txt is enforced by the web scraper and link crawler
  (`ARIA_RESPECT_ROBOTS=false` to opt out).
- Unpaywall is skipped unless a real `UNPAYWALL_EMAIL` is configured
  (no more fake default address).

### Fixes
- Mission validation derives valid sources from the collector registry —
  `wikipedia` and 35+ other real sources no longer warn as "unknown".
- `RUNS_DIR` (documented in `.env`) is honored.
- One shared model catalog (`STATIC_MODEL_CATALOG`) replaces three
  drifting copies with stale model ids.
- Version string centralized in `aria.__version__`.

### Testing & CI
- Suite green: 269 passed / 0 failed (was 247/3 — failures traced to
  crawl4ai loading `.env` at import time; tests are hermetic now).
- New: end-to-end API flow test (create run → poll → download exports →
  restart recovery), fail-closed auth tests, rate-limit identity and
  LRU tests, robots.txt gate tests, credential encryption tests.
- GitHub Actions CI: pytest on Python 3.11/3.13 + frontend
  type-check/build/tests.

## 5.0.0 — 2026-05

- ARIA Studio: React UI, FastAPI backend, 40+ source collectors,
  LLM cleaning pipeline, knowledge graph, gap detection, exports.
