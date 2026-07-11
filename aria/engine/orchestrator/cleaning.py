"""Cleaning phase — per-document LLM cleaning coordination."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger("aria")


async def run_cleaning_phase(
    raw_docs: list[dict],
    instructions: str,
    output_schema: dict,
    config: Any,
    emit_fn: Optional[Callable] = None,
    log: Optional[logging.Logger] = None,
) -> list[dict]:
    """Clean raw documents with the LLM cleaner.

    Returns cleaned document dicts. Falls back to raw docs on any error.
    """
    _log = log or logger
    total = len(raw_docs)
    if emit_fn:
        await emit_fn("clean", f"Cleaning {total} documents with LLM...")

    async def _on_progress(completed: int, _total: int) -> None:
        if emit_fn:
            await emit_fn(
                "clean_progress",
                f"Cleaned {completed}/{_total} documents",
                count=completed,
            )

    try:
        from aria.engine.cleaner.llm_cleaner import LLMCleaner
        cleaner = LLMCleaner(config=config, logger=_log)
        clean_docs = await cleaner.clean_batch(
            raw_docs, instructions, output_schema,
            on_progress=_on_progress if emit_fn else None,
        )
        if emit_fn:
            await emit_fn("clean_done", f"Cleaned {len(clean_docs)} documents", count=len(clean_docs))
        return clean_docs
    except Exception as exc:
        _log.warning("Cleaning phase failed, returning raw docs: %s", exc)
        return raw_docs
