"""Mission YAML loading, validation, and manipulation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("aria")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_MISSION: dict[str, Any] = {
    "mission": {
        "name": "Research Mission",
    },
    "collection": {
        "topic": "",
        "intent": "",
        # ARIA 5.0: optional domain and country selection
        # If set, activates domain-specific collectors (DepartmentRunner)
        "domains": [],  # e.g. ["jobs", "health", "finance"]
        "countries": [],  # e.g. ["IN", "US"] or ["ASIA"]
        "depth": "medium",
        "max_documents": 100,
        "max_per_source": 25,
        "languages": {
            "collect": ["en"],
            "translate_to": "en",
        },
        "sources": {
            "enabled": ["web", "pdf", "academic"],
            "priority": {
                "academic": 10,
                "pdf": 8,
                "web": 7,
                "youtube": 5,
            },
        },
    },
    "authenticated_sources": {
        "enabled": False,
        "platforms": [],
    },
    "llm_sources": {
        "enabled": False,
        "models": [],
        "query_settings": {
            "parallel": True,
            "delay_between_queries": 2,
            "skip_duplicate_queries": True,
        },
        "comparison": {
            "enabled": False,
            "min_models_for_comparison": 2,
            "highlight_divergence": True,
            "confidence_scoring": True,
        },
    },
    "cleaning": {
        "instructions": (
            "Extract structured, source-attributed research findings. "
            "Focus on actionable insights, recurring themes, institutions, "
            "locations, dates, and notable risks or opportunities."
        ),
        "output_schema": {
            "is_relevant": "bool",
            "relevance_score": "float",
            "title": "string",
            "summary": "string",
            "language_original": "string",
            "text_english": "string",
            "key_topics": "list",
            "entities": {
                "organizations": "list",
                "locations": "list",
                "people": "list",
                "policies_mentioned": "list",
            },
            "document_type": "string",
            "date_published": "string",
            "source_organization": "string",
            "quality_issues": "list",
        },
    },
    "output": {
        "formats": ["json", "csv", "markdown"],
        "sort_by": "relevance_score",
        "sort_order": "desc",
        "organize_by": "",
    },
}

_DEPTH_ALIASES = {
    "surface": "low",
    "quick": "low",
    "standard": "medium",
    "normal": "medium",
    "deep": "high",
    "expert": "high",
    "thorough": "high",
    "maximum": "exhaustive",
    "max": "exhaustive",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def apply_defaults(mission: dict) -> dict:
    """Fill in missing fields using the default mission template.

    Args:
        mission: Partially specified mission dict.

    Returns:
        Mission dict with all defaults applied.
    """
    return _deep_merge(_DEFAULT_MISSION, mission)


def validate_mission(mission: dict) -> dict:
    """Validate a mission dict and raise ValueError on problems.

    Args:
        mission: Mission dict (should have defaults applied first).

    Returns:
        The validated mission dict.

    Raises:
        ValueError: If required fields are missing or invalid.
    """
    collection = mission.get("collection", {})
    if not isinstance(collection, dict):
        raise ValueError("Mission 'collection' must be a dict.")
    topic = collection.get("topic", "").strip()
    if not topic:
        raise ValueError("Mission is missing a 'collection.topic' field.")

    raw_depth = str(collection.get("depth", "medium")).strip().lower()
    depth = _DEPTH_ALIASES.get(raw_depth, raw_depth)
    if depth not in ("low", "medium", "high", "exhaustive"):
        raise ValueError(
            f"Invalid depth '{raw_depth}'. Must be one of: low, medium, high, "
            "exhaustive, surface, standard, deep, thorough, maximum."
        )
    collection["depth"] = depth

    max_documents = collection.get("max_documents", 100)
    max_per_source = collection.get("max_per_source", 25)
    if not isinstance(max_documents, int) or max_documents <= 0:
        raise ValueError("collection.max_documents must be a positive integer.")
    if not isinstance(max_per_source, int) or max_per_source <= 0:
        raise ValueError("collection.max_per_source must be a positive integer.")
    if max_per_source > max_documents:
        raise ValueError("collection.max_per_source cannot exceed collection.max_documents.")

    languages = collection.get("languages", {})
    if not isinstance(languages, dict):
        raise ValueError("collection.languages must be a dict.")
    collect_langs = languages.get("collect", ["en"])
    if not isinstance(collect_langs, list) or not all(isinstance(x, str) for x in collect_langs):
        raise ValueError("collection.languages.collect must be a list of strings.")

    sources = collection.get("sources", {})
    if not isinstance(sources, dict):
        raise ValueError("collection.sources must be a dict.")
    enabled = sources.get("enabled", [])
    if not isinstance(enabled, list) or not all(isinstance(x, str) for x in enabled):
        raise ValueError("collection.sources.enabled must be a list of strings.")
    if not enabled:
        raise ValueError("collection.sources.enabled must include at least one source.")
    valid_sources = {
        "web",
        "pdf",
        "academic",
        "youtube",
        "reddit",
        "hackernews",
        "rss",
        "llm",
    }
    unknown = set(enabled) - valid_sources
    if unknown:
        # Warn rather than fail — allow forward compatibility
        logger.warning("Unknown collection sources: %s", ", ".join(sorted(unknown)))

    cleaning = mission.get("cleaning", {})
    if not isinstance(cleaning, dict):
        raise ValueError("cleaning must be a dict.")
    instructions = cleaning.get("instructions", "")
    if not isinstance(instructions, str) or not instructions.strip():
        raise ValueError("cleaning.instructions must be a non-empty string.")
    output_schema = cleaning.get("output_schema", {})
    if not isinstance(output_schema, dict):
        raise ValueError("cleaning.output_schema must be a dict.")

    output = mission.get("output", {})
    if not isinstance(output, dict):
        raise ValueError("output must be a dict.")
    formats = output.get("formats", [])
    if not isinstance(formats, list) or not all(isinstance(x, str) for x in formats):
        raise ValueError("output.formats must be a list of strings.")
    valid_formats = {"json", "csv", "markdown", "html", "zip"}
    invalid_formats = set(formats) - valid_formats
    if invalid_formats:
        raise ValueError(f"Invalid output formats: {sorted(invalid_formats)}")

    return mission


def load_mission_text(yaml_text: str) -> dict:
    """Parse and apply defaults to a mission defined as a YAML string.

    Args:
        yaml_text: YAML text of the mission.

    Returns:
        Fully resolved mission dict.
    """
    raw = yaml.safe_load(yaml_text) or {}
    if not isinstance(raw, dict):
        raise ValueError("Mission YAML must parse to a dict.")
    mission = apply_defaults(raw)
    return validate_mission(mission)


def load_mission(path: "str | Path") -> dict:
    """Load a mission from a YAML file path.

    Args:
        path: Path to the mission YAML file.

    Returns:
        Fully resolved mission dict.
    """
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        yaml_text = f.read()
    return load_mission_text(yaml_text)


# Alias for backward compatibility
load_mission_file = load_mission


def load_mission_file_or_args(
    mission_file: "str | Path | None" = None,
    topic: "str | None" = None,
    **kwargs: Any,
) -> dict:
    """Load a mission from a file, or build one from CLI arguments.

    Args:
        mission_file: Optional path to a mission YAML file.
        topic: Topic string to use if no file is provided.
        **kwargs: Additional kwargs passed to build_mission_from_args.

    Returns:
        Fully resolved mission dict.

    Raises:
        ValueError: If neither file nor topic is provided.
    """
    if mission_file:
        return load_mission(mission_file)
    if topic:
        return build_mission_from_args(topic, **kwargs)
    raise ValueError("Provide either a mission_file or a topic.")


def build_mission_from_args(topic: str, **kwargs: Any) -> dict:
    """Construct a mission dict from a topic string and optional overrides.

    Args:
        topic: Research topic.
        **kwargs: Optional overrides (depth, max_documents, sources, etc.).

    Returns:
        Fully resolved mission dict.
    """
    raw: dict[str, Any] = {
        "mission": {"name": kwargs.get("name", f"Research: {topic[:60]}")},
        "collection": {
            "topic": topic,
            "intent": kwargs.get("intent", ""),
            "depth": kwargs.get("depth", "medium"),
            "max_documents": kwargs.get("max_documents", 100),
            "max_per_source": kwargs.get("max_per_source", 25),
        },
    }

    if "sources" in kwargs:
        raw["collection"]["sources"] = {"enabled": kwargs["sources"]}

    if "formats" in kwargs:
        raw["output"] = {"formats": kwargs["formats"]}

    if "cleaning_instructions" in kwargs:
        raw["cleaning"] = {"instructions": kwargs["cleaning_instructions"]}

    mission = apply_defaults(raw)
    return validate_mission(mission)


def mission_to_yaml_text(mission: dict) -> str:
    """Serialise a mission dict back to YAML text.

    Args:
        mission: Mission dict.

    Returns:
        YAML string.
    """
    return yaml.dump(
        mission, allow_unicode=True, sort_keys=False, default_flow_style=False
    )


def schema_to_pretty_json(schema: dict) -> str:
    """Convert an output_schema dict to pretty-printed JSON.

    Args:
        schema: output_schema dict from the mission.

    Returns:
        Indented JSON string.
    """
    return json.dumps(schema, indent=2, ensure_ascii=False)
