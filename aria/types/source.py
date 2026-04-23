"""Source and collector metadata."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class SourceMetadata(BaseModel):
    """Metadata about a collection source."""

    source_type: str
    source_name: str
    category: str  # "web", "academic", "media", "social", "llm", "knowledge"
    description: Optional[str] = None
    requires_auth: bool = False
    rate_limit: Optional[int] = None
    extra: dict[str, Any] = {}
