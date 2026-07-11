"""Export and reporting surfaces.

Issue #8 — canonical export path is aria.engine.output.
This module is a thin re-export layer kept for backward compatibility.
Prefer importing directly from aria.engine.output.
"""

from aria.output.exporter import Exporter
from aria.output.formatter import format_document_excerpt
from aria.output.reporter import generate_report

__all__ = ["Exporter", "format_document_excerpt", "generate_report"]
