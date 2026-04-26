"""Research Brief and Phase dataclasses produced by the Research Director Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResearchPhase:
    """A single ordered phase of collection."""

    name: str                          # "landscape" | "deep_dive" | "critical" | "latest"
    goal: str                          # human-readable goal
    queries: list[str]                 # search queries for this phase
    source_types: list[str]            # which collector types to use
    max_docs: int = 50                 # cap per phase
    depends_on: str | None = None      # phase name this builds on


@dataclass
class ResearchBrief:
    """Structured understanding of what the user wants to research."""

    # Core
    original_topic: str
    resolved_topic: str = ""

    # Context — filled from conversation or inferred
    audience: str = "general"          # general | professional | academic | personal
    purpose: str = "informational"     # informational | academic | investment | clinical
    depth: str = "medium"              # surface | medium | expert
    time_range: str = "all"            # latest | 5years | all
    geography: str = "global"
    language: str = "english"
    focus: str = ""                    # specific angle user cares about

    # Research strategy
    key_questions: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    ambiguities_resolved: list[str] = field(default_factory=list)
    excluded_angles: list[str] = field(default_factory=list)

    # Source strategy
    must_have_sources: list[str] = field(default_factory=list)
    skip_sources: list[str] = field(default_factory=list)

    # Phased plan
    phases: list[ResearchPhase] = field(default_factory=list)

    # Conversation record
    answers: dict[str, Any] = field(default_factory=dict)
    questions_asked: int = 0
    skips: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_topic": self.original_topic,
            "resolved_topic": self.resolved_topic,
            "context": {
                "audience": self.audience,
                "purpose": self.purpose,
                "depth": self.depth,
                "time_range": self.time_range,
                "geography": self.geography,
                "language": self.language,
                "focus": self.focus,
            },
            "key_questions": self.key_questions,
            "entities": self.entities,
            "ambiguities_resolved": self.ambiguities_resolved,
            "must_have_sources": self.must_have_sources,
            "skip_sources": self.skip_sources,
            "phases": [
                {
                    "name": p.name,
                    "goal": p.goal,
                    "queries": p.queries,
                    "source_types": p.source_types,
                    "max_docs": p.max_docs,
                }
                for p in self.phases
            ],
        }
