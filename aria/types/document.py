"""Document type definitions."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    """Detected content types from Smart Cleaning Agent."""

    ACADEMIC_PAPER = "academic_paper"
    NEWS_ARTICLE = "news_article"
    FORUM_POST = "forum_post"
    SOCIAL_MEDIA = "social_media"
    TECHNICAL_DOC = "technical_doc"
    VIDEO_TRANSCRIPT = "video_transcript"
    ENCYCLOPEDIA = "encyclopedia"
    OPINION_ESSAY = "opinion_essay"
    GOV_POLICY = "gov_policy"
    DATA_REPORT = "data_report"
    UNKNOWN = "unknown"


class Document(BaseModel):
    """Base document model."""

    url: str
    title: str
    text: str
    source_type: str
    platform: str
    language: Optional[str] = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RawDocument(Document):
    """Raw collected document with original content."""

    word_count: int = 0
    original_text: str = ""


class CleanDocument(Document):
    """Cleaned and extracted document."""

    content_type_detected: ContentType = ContentType.UNKNOWN
    relevance_score: float = Field(ge=0.0, le=1.0)
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    cleaning_config: Optional[dict[str, Any]] = None
    cleaned_at: datetime = Field(default_factory=datetime.utcnow)
