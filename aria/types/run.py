"""Run and execution type definitions."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Run execution status."""

    PENDING = "pending"
    COLLECTING = "collecting"
    CLEANING = "cleaning"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class Run(BaseModel):
    """Research run execution model."""

    id: str
    topic: str
    intent: Optional[str] = None
    status: RunStatus = RunStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    documents_collected: int = 0
    documents_cleaned: int = 0
    sources_enabled: list[str] = Field(default_factory=list)
    depth_level: int = 1
    config: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
