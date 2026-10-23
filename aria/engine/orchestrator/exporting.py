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
    report_documents: Optional[list[dict]] = None,
    include_clean_exports: bool = True,
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
    # The archive is intentionally deferred until the HTML report exists.
    base_formats = [item for item in formats if item != "zip"]
    export_paths = exporter.export_all(
        raw_docs=raw_docs,
        clean_docs=clean_docs,
        formats=base_formats,
        topic=topic,
        include_clean_exports=include_clean_exports,
        digest_documents=report_documents,
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
        documents=report_documents if report_documents is not None else clean_docs,
        topic=topic,
        output_dir=export_dir,
        stats=stats,
        knowledge_graph=kg_data or None,
        gap_analysis=gap_result or None,
        images=images or None,
        methodology=methodology,
    )

    if "html" in formats:
        export_paths["html"] = str(report_path)

    export_paths, export_issues = exporter.validate_exports(
        export_paths,
        raw_docs_count=len(raw_docs),
        clean_docs_count=len(clean_docs),
    )
    if export_issues:
        _log.warning("Export validation issues: %s", ", ".join(export_issues))

    # Create the archive last so it includes every requested artifact,
    # including the visual HTML report generated above.
    if "zip" in formats:
        zip_path = exporter.export_zip(export_paths)
        export_paths["zip"] = str(zip_path)

    str_export_paths = {k: str(v) for k, v in export_paths.items()}
    return str_export_paths, str(report_path)
