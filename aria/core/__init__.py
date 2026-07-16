"""Core orchestration engine for ARIA."""
from aria.engine.orchestrator import MasterOrchestrator
from aria.engine.orchestrator import ResultAggregator, MeshAggregator
from aria.engine.utils.deduplicator import Deduplicator
from aria.engine.orchestrator import RunResult

Aggregator = ResultAggregator  # backwards-compat alias

__all__ = ["MasterOrchestrator", "Deduplicator", "ResultAggregator", "Aggregator", "RunResult"]
