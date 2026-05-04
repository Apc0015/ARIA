# ARIA Test Report — 2026-05-03

## Summary

| Phase | Result | Notes |
|-------|--------|-------|
| Environment | ✅ PASS | Python 3.13.11, all core deps installed, `aria 5.0.0` importable |
| Unit Tests | ✅ PASS | 295 passed, 0 failed (8 errors fixed before final run) |
| New Collector Imports | ✅ PASS | All 9 new collectors import and instantiate cleanly |
| API Server | ✅ PASS | All endpoints healthy; 8 advanced sources correctly classified |
| End-to-End Mini Run | ✅ PASS | CrossRef ✓ EuropePMC ✓ Wikidata ✓ Mastodon (see known issues) |
| Frontend Build | ✅ PASS | `tsc -b && vite build` clean — 2515 modules, 0 errors |

---

## Fixes Applied

### 1. Broken `..utils.camofox` import in 3 collectors
**Files changed:**
- `aria/engine/collectors/specialized/government.py`
- `aria/engine/collectors/specialized/news.py`
- `aria/engine/collectors/social/linkedin.py`

**Problem:** `from ..utils.camofox import ...` resolves to `aria.engine.collectors.{subdir}.utils.camofox` which doesn't exist.

**Fix:** Changed to `from ...utils.camofox import ...` (three dots → `aria.engine.utils.camofox`).

**Impact:** `test_agents/test_llm_ensemble.py` and 3 collector tests were erroring at import time. All 29 tests in those files now pass.

---

### 2. Missing `core_platforms` module
**Files changed:**
- `aria/engine/collectors/academic/core_platforms.py` (created)

**Problem:** `tests/test_collectors/test_academic_platforms.py` imports from `aria.engine.collectors.academic.core_platforms` but the actual file is named `platforms.py`.

**Fix:** Created `core_platforms.py` as an alias re-exporting `AcademicPlatformsCollector` from `platforms.py`.

**Additional fix:** The two IEEE tests were patching `core_platforms.httpx.AsyncClient` but httpx lives in `platforms.py`. Updated test patch targets to `aria.engine.collectors.academic.platforms.httpx.AsyncClient`.

---

### 3. `GET /api/sources` returning 404
**Files changed:**
- `aria/api/routes/sources.py`

**Problem:** Route was registered as `@router.get("/sources")` but all other routes in the app use the `/api/` prefix (e.g. `@router.get("/api/health")`).

**Fix:** Changed route to `@router.get("/api/sources")`.

---

### 4. Wikidata collector returning 403
**Files changed:**
- `aria/engine/collectors/knowledge/wikidata.py`

**Problem:** Wikidata API enforces a descriptive `User-Agent` header per their terms of service. Missing header → 403.

**Fix:** Added `User-Agent: ARIA-Research-Bot/5.0 (...)` header to the `httpx.AsyncClient`.

---

### 5. `GlassCard` TypeScript error
**Files changed:**
- `aria-report/src/components/glass/GlassCard.tsx`

**Problem:** `perspective` prop was destructured and used in the component body but not declared in the `GlassCardProps` interface, causing `tsc` to error: `Property 'perspective' does not exist on type 'GlassCardProps'`.

**Fix:** Added `perspective?: boolean` to the interface.

---

## Known Issues

| Issue | Severity | Root Cause | Action Required |
|-------|----------|------------|-----------------|
| `MastodonCollector` returns 0 results without token | Low | mastodon.social removed unauthenticated status search (~2023). Accounts/hashtag search still works; status search requires `MASTODON_ACCESS_TOKEN`. | Set `MASTODON_ACCESS_TOKEN` in `.env` for live use. Code is correct. |
| `crawl4ai` optional dep not installed | Info | `crawl4ai>=0.6.0` is commented-out in requirements. `_scrape_crawl4ai` gracefully no-ops when unavailable. | Run `pip install crawl4ai` to enable JS-aware crawling. |
| ZIP export `Duplicate name: 'clean_documents.csv'` warning | Low | Pre-existing zipfile naming collision in exporter. | Not a test failure; filed for separate fix. |

---

## What Was Tested

**Unit tests:**
- Total: **295 passed**, 0 failed
- Test files: 36 across `tests/test_agents/`, `tests/test_brain/`, `tests/test_collectors/`, `tests/test_access/`, `tests/test_output/`, and core test files

**New collectors verified (smoke test + live):**
| Collector | Import | Live Test |
|-----------|--------|-----------|
| CrossRefCollector | ✅ | ✅ 2 docs live |
| CoreAcCollector | ✅ | (mocked) |
| EuropePMCCollector | ✅ | ✅ 2 docs live |
| SSRNCollector | ✅ | (mocked) |
| BASESearchCollector | ✅ | (mocked) |
| WikidataCollector | ✅ | ✅ 1 doc live (after User-Agent fix) |
| InternetArchiveCollector | ✅ | (mocked) |
| ProPublicaCollector | ✅ | (mocked) |
| MastodonCollector | ✅ | 0 docs (auth restriction — expected) |

**API endpoints checked:**
- `GET /api/health` → 200
- `GET /api/sources` → 200 (8 advanced sources correct)
- `GET /api/runs` → 200
- `POST /api/runs` (invalid) → 422
- Path traversal attempts → 404 (protected)

**Frontend:**
- `tsc -b` → 0 TypeScript errors
- `vite build` → success (2515 modules, 628 kB bundle)
