"""Export phase — writing JSON/CSV/Markdown/ZIP outputs to disk."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("aria")


async def run_export_phase(
    raw_docs: list[dict],
    clean_docs: list[dict],
    topic: str,
    export_dir: Path,
    formats: list[str],
    stats: dict,
    kg_data: Optional[dict] = None,
    images: Optional[list[dict]] = None,
    gap_result: Optional[dict] = None,
    methodology: Optional[dict] = None,
    emit_fn: Optional[Callable] = None,
    log: Optional[logging.Logger] = None,
) -> tuple[dict[str, str], str]:
    """Export results and generate the HTML report.

    Returns (export_paths, report_path) as string dicts/paths.
    """
    _log = log or logger
    from aria.engine.output.exporter import Exporter
    from aria.engine.output.report import generate_report

    if emit_fn:
        await emit_fn("export", f"Exporting in formats: {formats}")

    exporter = Exporter(export_dir)
    export_paths = exporter.export_all(
        raw_docs=raw_docs,
        clean_docs=clean_docs,
        formats=formats,
        topic=topic,
    )

    if kg_data:
        try:
            kg_path = export_dir / "knowledge_graph.json"
            kg_path.write_text(json.dumps(kg_data, indent=2, default=str))
            export_paths["knowledge_graph"] = str(kg_path)
        except Exception as exc:
            _log.debug("Failed to write knowledge_graph.json: %s", exc)

    if images:
        try:
            img_path = export_dir / "images.json"
            img_path.write_text(json.dumps(images, indent=2, default=str))
            export_paths["images"] = str(img_path)
        except Exception as exc:
            _log.debug("Failed to write images.json: %s", exc)

    if emit_fn:
        await emit_fn("export_done", "Export complete", paths=export_paths)

    if emit_fn:
        await emit_fn("report", "Generating HTML report...")
    report_path = generate_report(
        documents=clean_docs,
        topic=topic,
        output_dir=export_dir,
        stats=stats,
        knowledge_graph=kg_data or None,
        gap_analysis=gap_result or None,
        images=images or None,
        methodology=methodology,
    )

    str_export_paths = {k: str(v) for k, v in export_paths.items()}
    return str_export_paths, str(report_path)
