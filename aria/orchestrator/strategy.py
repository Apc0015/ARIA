"""Query planning helpers."""

from __future__ import annotations

from typing import Any


class QueryStrategy:
    """Mission query expansion helper."""

    def __init__(self, settings: Any, logger: Any) -> None:
        self.settings = settings
        self.logger = logger

    def expand(self, topic: str, collection_config: dict[str, Any] | None = None) -> list[str]:
        from aria.engine.orchestrator.core import _flatten_plan_queries, _heuristic_plan
        plan = _heuristic_plan(topic, "")
        return _flatten_plan_queries(plan)
