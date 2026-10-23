"""Multi-format document exporter."""

from __future__ import annotations

import csv
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Exporter:
    """Exports document collections to JSON, CSV, Markdown, HTML, and ZIP formats."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def export_json(self, documents: list[dict], filename: str = "documents.json") -> Path:
        """Generic JSON export — alias used by tests and direct callers."""
        path = self._output_dir / filename
        _atomic_write_json(path, documents)
        return path

    def export_raw_json(self, documents: list[dict]) -> Path:
        """Export raw documents as a JSON array.

        Args:
            documents: List of raw document dicts.

        Returns:
            Path to the exported file.
        """
        path = self._output_dir / "raw_documents.json"
        _atomic_write_json(path, documents)
        return path

    def export_clean_json(self, documents: list[dict]) -> Path:
        """Export cleaned documents as a JSON array.

        Args:
            documents: List of cleaned document dicts.

        Returns:
            Path to the exported file.
        """
        path = self._output_dir / "clean_documents.json"
        _atomic_write_json(path, documents)
        return path

    def export_raw_csv(self, documents: list[dict]) -> Path:
        """Export raw documents as a CSV file.

        Args:
            documents: List of raw document dicts.

        Returns:
            Path to the exported file.
        """
        path = self._output_dir / "raw_documents.csv"
        if not documents:
            _atomic_write_text(path, "url,title,platform,source_type,word_count,text\n")
            return path

        priority_keys = [
            "url", "title", "platform", "source_type", "language",
            "word_count", "collected_at", "text",
        ]
        all_keys: list[str] = list(priority_keys)
        for doc in documents:
            for k in doc:
                if k not in all_keys and k != "metadata":
                    all_keys.append(k)

        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
            writer.writeheader()
            for doc in documents:
                flat_doc = {k: _flatten_value(doc.get(k)) for k in all_keys}
                writer.writerow(flat_doc)
        tmp_path.replace(path)
        return path

    def export_clean_csv(self, documents: list[dict]) -> Path:
        """Export cleaned documents as a CSV file.

        Args:
            documents: List of cleaned document dicts.

        Returns:
            Path to the exported file.
        """
        path = self._output_dir / "clean_documents.csv"
        if not documents:
            _atomic_write_text(path, "")
            return path

        # Collect all keys across all docs (maintaining a stable order)
        priority_keys = [
            "title", "url", "platform", "source_type", "relevance_score",
            "is_relevant", "content_type", "summary", "language",
            "word_count", "collected_at", "text",
        ]
        all_keys: list[str] = list(priority_keys)
        for doc in documents:
            for k in doc:
                if k not in all_keys and k != "metadata":
                    all_keys.append(k)

        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
            writer.writeheader()
            for doc in documents:
                flat_doc = {k: _flatten_value(doc.get(k)) for k in all_keys}
                writer.writerow(flat_doc)
        tmp_path.replace(path)
        return path

    def export_markdown(self, documents: list[dict], topic: str = "") -> Path:
        """Export cleaned documents as a Markdown research digest.

        Args:
            documents: List of cleaned document dicts.
            topic: Research topic for the document title.

        Returns:
            Path to the exported file.
        """
        path = self._output_dir / "research_digest.md"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            f"# Research Digest: {topic or 'Research'}",
            f"",
            f"*Generated: {now}*  ",
            f"*Documents: {len(documents)}*",
            f"",
            "---",
            "",
        ]

        for i, doc in enumerate(documents, 1):
            title = doc.get("title", f"Document {i}")
            url = doc.get("url", "")
            platform = doc.get("platform", "")
            relevance = doc.get("relevance_score", "")
            summary = doc.get("summary", "")
            content_type = doc.get("content_type", "")
            word_count = doc.get("word_count", "")
            collected_at = doc.get("collected_at", "")

            lines.append(f"## {i}. {title}")
            lines.append("")

            if url:
                lines.append(f"**Source:** [{url}]({url})  ")
            meta_parts = []
            if platform:
                meta_parts.append(f"Platform: {platform}")
            if content_type:
                meta_parts.append(f"Type: {content_type}")
            if relevance != "":
                meta_parts.append(f"Relevance: {float(relevance):.2f}")
            if word_count:
                meta_parts.append(f"Words: {word_count}")
            if meta_parts:
                lines.append(f"**{' | '.join(meta_parts)}**")
            lines.append("")

            if summary:
                lines.append(f"**Summary:** {summary}")
                lines.append("")

            # Include key topics if present
            key_topics = doc.get("key_topics", [])
            if key_topics:
                topics_str = ", ".join(str(t) for t in key_topics[:8])
                lines.append(f"**Key Topics:** {topics_str}")
                lines.append("")

            lines.append("---")
            lines.append("")

        _atomic_write_text(path, "\n".join(lines))
        return path

    def export_zip(self, export_paths: dict) -> Path:
        """Bundle all exported files into a single ZIP archive.

        Args:
            export_paths: Dict of {format_name: file_path}.

        Returns:
            Path to the ZIP file.
        """
        zip_path = self._output_dir / "research_export.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            seen_paths: set[Path] = set()
            seen_arcnames: set[str] = set()
            for name, file_path in export_paths.items():
                p = Path(file_path).resolve()
                if not p.exists() or p in seen_paths:
                    continue
                arcname = p.name
                # Disambiguate if two different files share the same basename
                if arcname in seen_arcnames:
                    arcname = f"{name}_{arcname}"
                seen_paths.add(p)
                seen_arcnames.add(arcname)
                zf.write(p, arcname=arcname)
        return zip_path

    def export_all(
        self,
        raw_docs: list[dict],
        clean_docs: list[dict],
        formats: list[str],
        topic: str = "",
        *,
        include_clean_exports: bool = True,
        digest_documents: list[dict] | None = None,
    ) -> dict[str, str]:
        """Export documents in all requested formats.

        Args:
            raw_docs: Raw collected documents.
            clean_docs: Cleaned documents.
            formats: List of format names (json, csv, markdown, zip).
            include_clean_exports: Whether the run produced AI-cleaned records.
            digest_documents: Records used for the human-readable digest.
            topic: Research topic string.

        Returns:
            Dict mapping format name to exported file path.
        """
        paths: dict[str, str] = {}

        if "json" in formats:
            raw_path = self.export_raw_json(raw_docs)
            paths["raw_json"] = str(raw_path)
            if include_clean_exports:
                clean_path = self.export_clean_json(clean_docs)
                paths["clean_json"] = str(clean_path)

        if "csv" in formats:
            raw_csv_path = self.export_raw_csv(raw_docs)
            paths["raw_csv"] = str(raw_csv_path)
            if include_clean_exports:
                clean_csv_path = self.export_clean_csv(clean_docs)
                paths["csv"] = str(clean_csv_path)      # legacy key kept for compat
                paths["clean_csv"] = str(clean_csv_path)

        if "markdown" in formats:
            md_path = self.export_markdown(
                digest_documents if digest_documents is not None else clean_docs,
                topic=topic,
            )
            paths["markdown"] = str(md_path)

        if "zip" in formats:
            zip_path = self.export_zip(paths)
            paths["zip"] = str(zip_path)

        return paths

    def validate_exports(
        self,
        export_paths: dict[str, str],
        raw_docs_count: int,
        clean_docs_count: int,
    ) -> tuple[dict[str, str], list[str]]:
        """Validate exported files exist and are non-empty when expected."""
        valid: dict[str, str] = {}
        issues: list[str] = []

        for key, path_str in export_paths.items():
            path = Path(path_str)
            if not path.exists():
                issues.append(f"missing:{key}")
                continue
            if key in {"raw_json", "raw_csv"} and raw_docs_count > 0 and path.stat().st_size == 0:
                issues.append(f"empty:{key}")
                continue
            if key in {"clean_json", "clean_csv", "markdown"} and clean_docs_count > 0 and path.stat().st_size == 0:
                issues.append(f"empty:{key}")
                continue
            valid[key] = str(path)

        return valid, issues


def _flatten_value(value: Any) -> str:
    """Convert a value to a CSV-safe string."""
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _atomic_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def _atomic_write_json(path: Path, data: Any) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    tmp_path.replace(path)
