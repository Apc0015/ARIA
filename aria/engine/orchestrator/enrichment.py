"""Enrichment phase — knowledge graph, gap detection, image extraction."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger("aria")


async def run_enrichment_phase(
    docs: list[dict],
    topic: str,
    intent: str,
    sub_questions: list[str],
    config: Any,
    emit_fn: Optional[Callable] = None,
    log: Optional[logging.Logger] = None,
    gap_followup_fn: Optional[Callable] = None,
) -> dict:
    """Run all enrichment passes and return collected intelligence.

    Returns a dict with keys: gap_result, kg_data, images, extra_docs.
    *gap_followup_fn* is an optional async callable for second-pass collection
    on detected gaps; supplied by the orchestrator to avoid circular deps.
    """
    _log = log or logger
    result: dict[str, Any] = {
        "gap_result": {},
        "kg_data": {},
        "images": [],
        "extra_docs": [],
    }

    # ── Gap detection ─────────────────────────────────────────────────────────
    if getattr(config, "gap_detection_enabled", True) and docs:
        if emit_fn:
            await emit_fn("gap_detect", "Detecting research gaps...")
        result["gap_result"] = await _detect_gaps(docs, topic, intent, sub_questions, _log, config)

        if result["gap_result"].get("has_gaps") and result["gap_result"].get("follow_up_queries") and gap_followup_fn:
            follow_ups = result["gap_result"]["follow_up_queries"]
            if emit_fn:
                await emit_fn(
                    "gap_detect",
                    f"Found {len(result['gap_result']['gaps'])} gaps — running follow-up ({len(follow_ups)} queries)",
                )
            result["extra_docs"] = await gap_followup_fn(follow_ups, result["gap_result"])

    # ── Knowledge graph ───────────────────────────────────────────────────────
    if getattr(config, "knowledge_graph_enabled", True) and docs:
        if emit_fn:
            await emit_fn("knowledge_graph", "Building knowledge graph...")
        result["kg_data"] = await _build_knowledge_graph(docs, topic, _log)
        contradictions = result["kg_data"].get("contradictions", [])
        if emit_fn:
            await emit_fn(
                "knowledge_graph",
                f"Graph: {result['kg_data'].get('total_entities', 0)} entities, "
                f"{len(contradictions)} contradictions",
                has_contradictions=bool(contradictions),
            )

    # ── Image extraction ──────────────────────────────────────────────────────
    if getattr(config, "image_extraction_enabled", True) and docs:
        result["images"] = _extract_images(docs, topic, _log)
        if result["images"] and emit_fn:
            await emit_fn("images", f"Extracted {len(result['images'])} images")

    return result


def _score_documents(docs: list[dict], topic: str, intent: str, log: Optional[logging.Logger] = None) -> list[dict]:
    """Annotate docs with multi-dimensional relevance scores."""
    _log = log or logger
    try:
        from aria.engine.intelligence.relevance_scorer import score_and_annotate
        return score_and_annotate(docs, topic, intent)
    except Exception as exc:
        _log.debug("Relevance scoring failed: %s", exc)
        return docs


async def _detect_gaps(
    docs: list[dict],
    topic: str,
    intent: str,
    sub_questions: list[str],
    log: logging.Logger,
    config: Any,
) -> dict:
    try:
        from aria.engine.intelligence.gap_detector import detect_gaps
        return await detect_gaps(
            docs=docs,
            topic=topic,
            intent=intent,
            sub_questions=sub_questions,
            config=config,
        )
    except Exception as exc:
        log.debug("Gap detection failed: %s", exc)
        return {}


async def _build_knowledge_graph(docs: list[dict], topic: str, log: logging.Logger) -> dict:
    try:
        from aria.engine.intelligence.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        await kg.build_from_documents(docs, topic, max_docs_to_extract=80)
        log.info(kg.summary())
        return kg.to_dict()
    except Exception as exc:
        log.debug("Knowledge graph failed: %s", exc)
        return {}


def _extract_images(docs: list[dict], topic: str, log: logging.Logger) -> list[dict]:
    try:
        from aria.engine.intelligence.image_extractor import extract_images_from_docs
        return extract_images_from_docs(docs, max_total=50, max_per_doc=5)
    except Exception as exc:
        log.debug("Image extraction failed: %s", exc)
        return []
