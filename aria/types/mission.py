"""Mission and configuration type definitions."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class MissionConfig(BaseModel):
    """Mission configuration."""

    topic: str
    intent: Optional[str] = None
    sources_enabled: list[str] = Field(default_factory=list)
    depth_level: int = Field(1, ge=1, le=5)
    max_documents: int = 10000
    language: str = "en"
    output_formats: list[str] = Field(default_factory=lambda: ["json", "csv", "markdown"])
    output_schema: dict[str, Any] = Field(default_factory=dict)


class Mission(BaseModel):
    """Full mission model."""

    id: str
    name: str
    description: Optional[str] = None
    config: MissionConfig
    credentials: dict[str, str] = Field(default_factory=dict)
    custom_instructions: Optional[dict[str, str]] = None
