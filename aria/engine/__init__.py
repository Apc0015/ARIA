# aria.engine — Public API surface for the ARIA research engine.
# All cross-package imports from aria/ must go through these names only.
# Never import aria.engine internals (e.g. aria.engine.cleaner.llm_cleaner) from aria/.

from aria.engine.orchestrator.core import (
    InfoCollectorOrchestrator,
    ResultAggregator,
    MeshAggregator,   # backwards-compat alias
    RunResult,
)
from aria.engine.memory.shared_memory import SharedMemory
from aria.engine.storage.raw_store import RawStore
from aria.engine.storage.clean_store import CleanStore
from aria.engine.access.credential_manager import CredentialManager
from aria.engine.ensemble.providers import (
    build_provider_catalog,
    default_llm_source_models,
    describe_cleaning_brain,
    resolve_cleaning_llm,
)
from aria.engine.mission import (
    apply_defaults,
    build_mission_from_args,
    load_mission,
    load_mission_file_or_args,
    load_mission_text,
    validate_mission,
)

__all__ = [
    # Orchestration
    "InfoCollectorOrchestrator",
    "ResultAggregator",
    "MeshAggregator",
    "RunResult",
    # Memory / storage
    "SharedMemory",
    "RawStore",
    "CleanStore",
    # Access
    "CredentialManager",
    # LLM providers
    "build_provider_catalog",
    "default_llm_source_models",
    "describe_cleaning_brain",
    "resolve_cleaning_llm",
    # Mission
    "apply_defaults",
    "build_mission_from_args",
    "load_mission",
    "load_mission_file_or_args",
    "load_mission_text",
    "validate_mission",
]
