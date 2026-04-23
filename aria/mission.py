"""Mission loading and validation for the canonical ARIA package."""

from __future__ import annotations

from typing import Any, TypeAlias

from aria.engine.mission import (
    apply_defaults,
    build_mission_from_args,
    load_mission,
    load_mission_file_or_args,
    load_mission_text,
    mission_to_yaml_text,
    schema_to_pretty_json,
    validate_mission,
)


Mission: TypeAlias = dict[str, Any]

__all__ = [
    "Mission",
    "apply_defaults",
    "build_mission_from_args",
    "load_mission",
    "load_mission_file_or_args",
    "load_mission_text",
    "mission_to_yaml_text",
    "schema_to_pretty_json",
    "validate_mission",
]
