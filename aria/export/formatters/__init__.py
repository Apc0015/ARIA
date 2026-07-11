"""Export formatters for different output formats."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aria.engine.output.exporter import Exporter


class JSONFormatter:
    """Format and write document collections as JSON."""

    def __init__(self, output_dir: Path) -> None:
        self._exporter = Exporter(output_dir)

    def format_raw(self, documents: list[dict[str, Any]]) -> Path:
        return self._exporter.export_raw_json(documents)

    def format_clean(self, documents: list[dict[str, Any]]) -> Path:
        return self._exporter.export_clean_json(documents)

    def format(self, documents: list[dict[str, Any]], filename: str = "documents.json") -> Path:
        return self._exporter.export_json(documents, filename)


class CSVFormatter:
    """Format and write document collections as CSV."""

    def __init__(self, output_dir: Path) -> None:
        self._exporter = Exporter(output_dir)

    def format_raw(self, documents: list[dict[str, Any]]) -> Path:
        return self._exporter.export_raw_csv(documents)

    def format_clean(self, documents: list[dict[str, Any]]) -> Path:
        return self._exporter.export_clean_csv(documents)


class MarkdownFormatter:
    """Format and write document collections as a Markdown research digest."""

    def __init__(self, output_dir: Path) -> None:
        self._exporter = Exporter(output_dir)

    def format(self, documents: list[dict[str, Any]], topic: str = "") -> Path:
        return self._exporter.export_markdown(documents, topic=topic)


class ZIPFormatter:
    """Bundle exported files into a ZIP archive."""

    def __init__(self, output_dir: Path) -> None:
        self._exporter = Exporter(output_dir)

    def format(self, export_paths: dict[str, str]) -> Path:
        return self._exporter.export_zip(export_paths)


__all__ = ["JSONFormatter", "CSVFormatter", "MarkdownFormatter", "ZIPFormatter"]
