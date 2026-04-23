"""Language helpers."""

from __future__ import annotations

from langdetect import detect


def detect_language(text: str) -> str:
    """Detect the language of a text sample."""

    sample = text.strip()
    if not sample:
        return "unknown"
    try:
        return detect(sample)
    except Exception:
        return "unknown"
