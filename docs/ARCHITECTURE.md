# ARIA Architecture

ARIA has one supported application path:

1. `aria-report/` is the React user interface.
2. `aria/api/` accepts user requests, validates configuration, and tracks runs.
3. `aria/engine/` performs planning, collection, cleaning, intelligence enrichment, storage, and export.
4. `aria/access/` contains specialised paywall and academic-platform access handlers.
5. `missions/` contains reusable research instructions.
6. `tests/` verifies the API, engine, collectors, and exports.

## Research Run

`Launch` -> `API` -> `engine/orchestrator` -> `collectors` -> `cleaner` -> `intelligence` -> `storage + exports`

A full run requires a configured and reachable LLM. Collection-only runs may run without one. Results are written under `data/runs/<run-id>/`.

## Removed Compatibility Namespaces

The former `aria/agents`, `aria/brain`, `aria/orchestrator`, `aria/sources`, `aria/output`, `aria/storage`, `aria/export`, and `aria/memory` namespaces were duplicate compatibility layers. Their active responsibilities now live under `aria/engine`, and the obsolete citation-expansion implementation was removed in favor of `aria/engine/citation`.
