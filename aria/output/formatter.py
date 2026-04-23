"""Formatting helpers."""

from __future__ import annotations


def format_document_excerpt(document: dict[str, object], max_length: int = 240) -> str:
    """Return a readable document excerpt for logs or previews."""

    text = str(document.get("summary") or document.get("raw_text") or document.get("text") or "")
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."
