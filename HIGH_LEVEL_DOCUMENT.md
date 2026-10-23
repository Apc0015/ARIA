# ARIA Launch Review: High-Level Document

Audit date: 2026-07-18

## Executive Verdict

ARIA is an early-stage research-workbench product, not a launch-ready paid multi-user product. The research pipeline is substantial and the browser interface builds and has passing unit tests, but the visible product does not yet expose or reliably represent several of its strongest backend features. A paying user could not safely rely on it for defensible research today.

## What The Product Is

ARIA accepts a research topic and goal, asks optional planning questions, searches selected public and authenticated sources, removes duplicate material, asks an LLM to structure the material, then creates raw and cleaned exports plus an HTML report.

The stated goal inferred from the code is evidence-oriented research support: find sources across web, academic, social, media, data, government, and personal systems; rank the material; identify gaps; find entities and contradictions; retain the source material for later review.

## Who It Is For

The implemented product is best suited to a single technically capable operator running local or self-hosted exploratory research. It is not yet built for independent customer accounts, collaborative teams, regulated research, or a customer who needs guaranteed source quality and reproducible results.

## Core User Flow

1. A user opens the React web application and enters a topic, optionally answering Research Director questions.
2. The API validates a mission and starts a background run.
3. The engine turns the topic into queries, runs selected collectors concurrently, and deduplicates documents.
4. A configured LLM cleans documents, applies a relevance score, and can perform gap detection and knowledge-graph extraction.
5. The engine writes raw/clean JSON and CSV files, a Markdown digest, an HTML report, and optional ZIP/graph/image files.
6. The interface polls for status, shows a document table, and offers four downloads.

## What Is Actually Implemented

### Implemented And Connected

- FastAPI backend with API-key middleware, rate limiting, health checks, run persistence, credential storage, and export download routes.
- React/Vite interface with launch, monitor, report, source, and settings screens.
- A real asynchronous orchestration path: query planning, collector dispatch, URL/content deduplication, LLM cleaning, relevance scoring, citation following, gap detection, knowledge graph, image extraction, knowledge-base storage, and exports.
- More than forty collector registrations for web, academic, social, media, knowledge, government, and data sources.
- Raw and cleaned documents are persisted under a run directory and are reloadable after an API restart.
- Encryption at rest is optionally available for the credentials file.

### Implemented But Not Reliably Presented To Users

- Knowledge graph, gap analysis, contradiction detection, extracted images, methodology, HTML report, and ZIP export are created by backend code, but the main React Report screen does not display them or provide downloads for most of them.
- Raw documents are stored and have an API endpoint, but the main UI shows only cleaned-document rows and original URLs. It does not provide the source-review experience needed to validate an LLM summary against captured text.
- Source settings persist only in browser local storage and are not used by the Launch screen. A user can enable or disable a source on the Sources page without affecting the next run.
- The monitor screen displays a patterned, simulated source-activity indicator instead of actual per-source run events.

### Half-Done Or Misleading

- A separate `/api/studio` adapter includes no-op login, in-memory credentials, fixed agent totals, and simulated run progress. It is registered in the production app even though the current React UI does not use it.
- Documentation promises six one-click downloads, a ZIP bundle, depth levels up to 5,000+ documents, and 18 agents. The current UI exposes four downloads, does not request ZIP, uses a different source list, and cannot guarantee those document volumes.
- Full runs now check for an LLM before starting, but `collect_only` still bypasses that check and delivers an intentionally incomplete result. This conflicts with the product promise of research intelligence.

## Architecture In Plain Language

- `aria-report/` is the screen a user sees.
- `aria/api/` is the front door. It receives requests, stores the run state, protects routes with an API key, and serves downloads.
- `aria/engine/` is the workshop. It plans research, talks to sources, cleans documents with an LLM, analyzes results, and writes files.
- `aria/access/` handles credentials, sessions, and some academic/paywall integrations.
- `data/runs/<run id>/` is the filing cabinet for each research run.

The design is a single Python process plus a browser UI. There is no database-backed job queue, user-account system, tenant isolation, durable streaming channel, or deployment migration system.

## What “Done” Means Before Launch

A launch-ready ARIA must do all of the following:

- Deliver one honest, evidence-backed research workflow rather than a mixture of real, simulated, and disconnected screens.
- Require a verified LLM for every user-facing research run, or clearly offer a separately named ingestion-only product with an explicit next step.
- Show every important conclusion with links to exact captured source text and the original URL.
- Make graph, gaps, contradictions, raw sources, HTML report, and all advertised exports accessible from the UI.
- Have a single source-of-truth for source selection, models, limits, and output formats.
- Separate customer accounts and runs; never share credentials, research data, or API access between customers.
- Use durable background jobs, cancellation, retry policy, timeouts, telemetry, and reliable deployment configuration.
- Run deterministic backend and frontend tests in CI and demonstrate a real end-to-end run against controlled test sources.

## Major Launch Risks

1. **Trust risk:** the product shows AI scores and summaries without an in-product captured-text review path or claim-level evidence links.
2. **Product honesty risk:** the monitoring display and Studio routes contain simulated values while the product is presented as live research intelligence.
3. **Security and privacy risk:** API-key authentication is a shared-server mechanism, not account authorization. Stored credentials and run data are global to the deployment.
4. **Reliability risk:** collectors fail independently and are often silently skipped; a run can complete with far fewer sources or documents than a user expects.
5. **Scalability risk:** work runs in one API process with in-memory tasks and state. Restarted runs are marked failed; there is no worker queue or job recovery.
6. **Verification risk:** the full Python test suite did not complete during this audit. The React suite passed 9 tests, but neither suite proves a real research run against a controlled source and LLM.

## Genuine Strengths

- The codebase contains a real, modular pipeline rather than only a prototype interface.
- Raw source retention, source URLs, deduplication, run directories, and export formats are a strong starting point for evidence-backed research.
- The API has useful baseline protections: a secure-by-default API key, constant-time key comparison, rate limits, CORS allow-list, filename validation, secret scrubbing, and optional credentials encryption.
- Collectors are grouped by source type and largely share a consistent dispatch contract.
- The application has a meaningful suite of unit and integration tests, and the frontend build/test path exists in CI.

## Prioritized Punch List

1. Remove simulated product behavior from production routes and replace Monitor source status with real collector events.
2. Build the evidence-review experience: raw captured text, source URL, quote/claim linkage, and clear AI uncertainty.
3. Make the report screen expose graph, gaps, contradictions, images, HTML, ZIP, and all actual exports.
4. Decide whether ARIA is single-operator self-hosted or multi-user SaaS. If SaaS, add accounts, authorization, tenant data isolation, encrypted secret management, and audit logs before launch.
5. Replace in-process research tasks with durable jobs, cancellation, bounded concurrency, timeouts, and restart recovery.
6. Remove or fully separate `collect_only`; do not let a normal user receive incomplete “research” output.
7. Make Sources, Settings, Launch, API registry, and documentation use the same authoritative configuration.
8. Correct all product claims in README and UI to match tested capabilities and limits.
9. Add controlled end-to-end tests and make the entire backend test suite finish deterministically in CI.
