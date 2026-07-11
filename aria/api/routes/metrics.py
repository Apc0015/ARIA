"""Real-time metrics endpoint for ARIA.

Exposes run statistics, LLM health, and system info in both JSON
(for dashboards) and Prometheus text format (for Grafana/DataDog).

Endpoints:
    GET /api/metrics        — JSON metrics
    GET /api/metrics/prom   — Prometheus text format
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

router = APIRouter()

# Module-level counters — persist for the lifetime of the server process
_start_time = time.time()
_llm_calls_total = 0
_llm_calls_failed = 0
_llm_calls_retried = 0
_docs_cleaned_total = 0
_docs_collected_total = 0


def increment_llm_call(failed: bool = False, retried: bool = False) -> None:
    """Call from LLM cleaner to track API call stats."""
    global _llm_calls_total, _llm_calls_failed, _llm_calls_retried
    _llm_calls_total += 1
    if failed:
        _llm_calls_failed += 1
    if retried:
        _llm_calls_retried += 1


def increment_docs(collected: int = 0, cleaned: int = 0) -> None:
    global _docs_collected_total, _docs_cleaned_total
    _docs_collected_total += collected
    _docs_cleaned_total += cleaned


def _collect_metrics(run_manager: Any) -> dict[str, Any]:
    runs = list(run_manager.runs.values())
    by_status: dict[str, int] = {}
    for s in runs:
        by_status[s.status] = by_status.get(s.status, 0) + 1

    total_docs_collected = sum(s.docs_collected for s in runs)
    total_docs_cleaned = sum(s.docs_cleaned for s in runs)

    # LLM config from env
    provider = os.getenv("LLM_PROVIDER", "unknown")
    llm_configured = bool(
        os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or provider == "ollama"
    )

    uptime_secs = time.time() - _start_time

    # DB stats
    db_total = 0
    try:
        db_total = run_manager._run_store.count()
    except Exception:
        pass

    return {
        "aria_version": "5.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(uptime_secs),
        "runs": {
            "in_memory": len(runs),
            "persisted_total": db_total,
            "by_status": by_status,
            "active": by_status.get("running", 0),
        },
        "documents": {
            "collected_this_session": total_docs_collected,
            "cleaned_this_session": total_docs_cleaned,
            "llm_calls_total": _llm_calls_total,
            "llm_calls_failed": _llm_calls_failed,
            "llm_calls_retried": _llm_calls_retried,
            "llm_success_rate": (
                round((_llm_calls_total - _llm_calls_failed) / _llm_calls_total, 3)
                if _llm_calls_total > 0 else None
            ),
        },
        "llm": {
            "provider": provider,
            "model": (
                os.getenv("OPENROUTER_MODEL")
                or os.getenv("OPENAI_MODEL")
                or os.getenv("ANTHROPIC_MODEL")
                or os.getenv("OLLAMA_MODEL")
                or "unknown"
            ),
            "configured": llm_configured,
        },
        "system": {
            "max_concurrent_runs": int(os.getenv("ARIA_MAX_CONCURRENT_RUNS", "20")),
            "rate_limit_runs_per_hour": int(os.getenv("ARIA_RATE_LIMIT_RUNS_PER_HOUR", "30")),
            "rate_limit_reqs_per_min": int(os.getenv("ARIA_RATE_LIMIT_REQS_PER_MIN", "300")),
            "shared_memory_backend": os.getenv("SHARED_MEMORY_BACKEND", "dict"),
        },
    }


@router.get("/api/metrics")
async def get_metrics(request: Request) -> dict[str, Any]:
    """Return real-time ARIA metrics as JSON."""
    run_manager = request.app.state.run_manager
    return _collect_metrics(run_manager)


@router.get("/api/metrics/prom", response_class=PlainTextResponse)
async def get_metrics_prometheus(request: Request) -> str:
    """Return metrics in Prometheus text exposition format.

    Compatible with Prometheus scrape, Grafana, and DataDog agent.
    """
    run_manager = request.app.state.run_manager
    m = _collect_metrics(run_manager)

    lines = [
        "# HELP aria_uptime_seconds Seconds since the ARIA server started",
        "# TYPE aria_uptime_seconds counter",
        f"aria_uptime_seconds {m['uptime_seconds']}",
        "",
        "# HELP aria_runs_total Total runs in memory by status",
        "# TYPE aria_runs_total gauge",
    ]
    for status, count in m["runs"]["by_status"].items():
        lines.append(f'aria_runs_total{{status="{status}"}} {count}')

    lines += [
        "",
        "# HELP aria_runs_persisted_total Total runs in SQLite database",
        "# TYPE aria_runs_persisted_total counter",
        f"aria_runs_persisted_total {m['runs']['persisted_total']}",
        "",
        "# HELP aria_documents_collected_total Documents collected this session",
        "# TYPE aria_documents_collected_total counter",
        f"aria_documents_collected_total {m['documents']['collected_this_session']}",
        "",
        "# HELP aria_documents_cleaned_total Documents cleaned this session",
        "# TYPE aria_documents_cleaned_total counter",
        f"aria_documents_cleaned_total {m['documents']['cleaned_this_session']}",
        "",
        "# HELP aria_llm_calls_total LLM API calls made",
        "# TYPE aria_llm_calls_total counter",
        f"aria_llm_calls_total {m['documents']['llm_calls_total']}",
        "",
        "# HELP aria_llm_calls_failed_total LLM API calls that permanently failed",
        "# TYPE aria_llm_calls_failed_total counter",
        f"aria_llm_calls_failed_total {m['documents']['llm_calls_failed']}",
        "",
        "# HELP aria_llm_configured Whether an LLM API key is set (1=yes, 0=no)",
        "# TYPE aria_llm_configured gauge",
        f"aria_llm_configured {1 if m['llm']['configured'] else 0}",
        "",
    ]
    return "\n".join(lines)
