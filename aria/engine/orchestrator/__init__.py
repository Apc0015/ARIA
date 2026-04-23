"""Main orchestration engine for ARIA research collection runs."""

from aria.engine.orchestrator.core import (
    InfoCollectorOrchestrator,
    ResultAggregator,
    MeshAggregator,  # backwards-compat alias
    RunResult,
)

# Alias used by aria/orchestrator/master.py
MasterOrchestrator = InfoCollectorOrchestrator

__all__ = [
    "InfoCollectorOrchestrator",
    "MasterOrchestrator",
    "ResultAggregator",
    "MeshAggregator",
    "RunResult",
]
