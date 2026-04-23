# ARIA — Agentic Research Intelligence Architecture

## Project Structure

```
aria/                    Canonical Python package (this is the main codebase)
├── api/                 FastAPI backend + routes
├── brain/               Query expander, router, translator, cleaner
├── agents/              LLM ensemble + source agent types (web, academic, etc.)
├── sources/             Source registry + collectors (web/, academic/, media/, social/)
│   └── registry.py     Source registration
├── storage/             raw/, clean/ storage adapters
├── export/              formatters, exporter, reporter
├── memory/              shared memory, registry, discovery
├── access/              credentials, paywall, platforms/
├── orchestrator/        Master orchestrator (proxies to aria.engine)
├── engine/              Infocollector engine (real implementation, pip install)
├── types/               document, mission, run, source pydantic models
├── cli.py               CLI entry point
├── config.py            Config + load_config / load_settings
└── mission.py           Mission loading/validation (delegates to engine)

aria_studio/             Flutter desktop app (macos/linux/windows/web)
aria-report/             React/Vite/Tailwind web reporting UI
tests/                   Python test suite
```

## Key Conventions

- `__version__ = "5.0.0"` lives in `aria/__init__.py`
- CLI version string lives in `aria/cli.py` (keep aligned)
- All env var config routed through `aria/config.py` `load_config()`
- Mission files are YAML, validated via `aria.mission` helpers
- Source agents registered in `sources/registry.py`
- Storage uses raw/clean separation in `storage/`

## Running

```bash
# CLI research run
python -m aria.cli --topic "AI safety" --mission missions/examples/default.yaml

# API server
python -m aria.cli --serve-api

# Flutter UI
cd aria_studio && flutter run
```

## Testing

```bash
pytest tests/ -v
```

## Notes

- `aria/orchestrator/master.py` imports from `aria.engine.orchestrator` (infocollector), NOT from `aria/orchestrator/`
- The `aria.engine` package is a separate pip install (infocollector)
- API has demo mode fallback when `aria.engine` is not installed
