"""Deduplication phase — URL-hash + content-fingerprint + semantic MinHash."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger("aria")


def _content_fingerprint(text: str) -> str:
    """SHA-256 fingerprint of the first 2000 chars (length-prefixed).

    2000-char window reduces false deduplication of documents that share
    a common abstract/intro (e.g. arXiv preprints vs. published versions).
    """
    sample = text.strip()[:2000]
    combined = f"{len(text)}:{sample}"
    return hashlib.sha256(combined.encode()).hexdigest()


async def run_dedup_phase(
    docs: list[dict],
    config: Any = None,
    emit_fn: Optional[Callable] = None,
    log: Optional[logging.Logger] = None,
) -> list[dict]:
    """Apply semantic MinHash deduplication if enabled; otherwise return as-is."""
    _log = log or logger
    semantic_enabled = getattr(config, "semantic_dedup_enabled", False) if config else False
    if not semantic_enabled:
        return docs

    try:
        from aria.engine.intelligence.semantic_dedup import SemanticDeduplicator
        dedup = SemanticDeduplicator()
        unique, removed = dedup.filter_documents(docs)
        if removed:
            msg = f"Semantic dedup removed {removed} duplicate documents"
            _log.info(msg)
            if emit_fn:
                await emit_fn("dedup", msg)
        return unique
    except Exception as exc:
        _log.debug("Semantic dedup failed (using raw list): %s", exc)
        return docs
