"""Citation corpus exporter — writes corpus.json and missing-full-text.md.

Takes a list of CorpusRecord objects (from the citation crawl phase) and
produces the deliverable files for the literature review pipeline:

- ``corpus.json``         — one record per paper, all levels
- ``missing-full-text.md`` — papers where only abstract was available

Usage::

    from aria.engine.output.citation_exporter import CitationExporter
    from aria.engine.orchestrator.citation_crawl import run_citation_crawl_phase

    records = await run_citation_crawl_phase(config, output_dir)
    exporter = CitationExporter(output_dir)
    exporter.export(records)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from aria.engine.citation.seed import CorpusRecord


class CitationExporter:
    """Write citation corpus deliverable files."""

    def __init__(self, output_dir: str, subdir: str = "citation-graph") -> None:
        self.base_dir = os.path.join(output_dir, subdir)
        os.makedirs(self.base_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(self, records: list[CorpusRecord]) -> dict[str, str]:
        """Write all deliverable files and return a dict of {name: path}."""
        paths = {}
        paths["corpus_json"] = self._write_corpus_json(records)
        paths["missing_full_text"] = self._write_missing_full_text(records)
        return paths

    # ------------------------------------------------------------------
    # corpus.json
    # ------------------------------------------------------------------

    def _write_corpus_json(self, records: list[CorpusRecord]) -> str:
        path = os.path.join(self.base_dir, "corpus.json")
        data = [self._record_to_dict(r) for r in records]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        return path

    @staticmethod
    def _record_to_dict(rec: CorpusRecord) -> dict[str, Any]:
        return {
            "level": rec.level,
            "doi": rec.doi or None,
            "title": rec.title or None,
            "authors": rec.authors or [],
            "year": rec.year or None,
            "journal": rec.journal or None,
            "volume": rec.volume or None,
            "issue": rec.issue or None,
            "pages": rec.pages or None,
            "abstract": rec.abstract or None,
            "full_text_available": rec.full_text_available,
            "full_text_path": rec.full_text_path or None,
            "access_status": rec.access_status,
            "doi_status": rec.doi_status,
            "url": rec.url or None,
            "ref_type": rec.ref_type,
            "parse_notes": rec.parse_notes or [],
            "raw_ref": rec.raw_ref or None,
        }

    # ------------------------------------------------------------------
    # missing-full-text.md
    # ------------------------------------------------------------------

    def _write_missing_full_text(self, records: list[CorpusRecord]) -> str:
        path = os.path.join(self.base_dir, "missing-full-text.md")

        missing = [
            r for r in records
            if r.level == 1 and not r.full_text_available
        ]
        # Separate into categories
        paywalled = [r for r in missing if r.access_status == "paywalled"]
        unavailable = [r for r in missing if r.access_status == "unavailable"]
        unknown = [r for r in missing if r.access_status not in ("paywalled", "unavailable", "open_access")]
        no_doi = [r for r in missing if not r.doi and r.ref_type in ("journal_article", "book", "book_chapter")]

        lines = [
            "# Missing Full Text — Manual Follow-Up Required",
            f"\n*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*",
            f"\n**Total Level 1 papers without full text:** {len(missing)}",
            "",
        ]

        if paywalled:
            lines.append(f"## Paywalled ({len(paywalled)})")
            lines.append("*Requires institutional access or inter-library loan.*\n")
            for r in paywalled:
                lines.append(_format_missing_entry(r))
            lines.append("")

        if unavailable:
            lines.append(f"## Fetch Failed ({len(unavailable)})")
            lines.append("*URL was reachable but content could not be extracted.*\n")
            for r in unavailable:
                lines.append(_format_missing_entry(r))
            lines.append("")

        if unknown:
            lines.append(f"## Access Status Unknown ({len(unknown)})")
            lines.append("*Could not determine access status — check manually.*\n")
            for r in unknown:
                lines.append(_format_missing_entry(r))
            lines.append("")

        if no_doi:
            lines.append(f"## No DOI Resolved ({len(no_doi)})")
            lines.append("*DOI lookup failed — verify reference manually.*\n")
            for r in no_doi:
                lines.append(_format_missing_entry(r))
            lines.append("")

        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        return path


def _format_missing_entry(rec: CorpusRecord) -> str:
    """Format a single missing record as a markdown list item."""
    authors = ", ".join(rec.authors[:3]) if rec.authors else rec.authors_raw if hasattr(rec, "authors_raw") else "Unknown"
    if len(rec.authors) > 3:
        authors += " et al."
    doi_str = f"DOI: `{rec.doi}`" if rec.doi else "DOI: *not resolved*"
    url_str = f" — [link]({rec.url})" if rec.url else ""
    notes = f" ⚠ {', '.join(rec.parse_notes)}" if rec.parse_notes else ""
    return (
        f"- **{rec.title or '[untitled]'}**  \n"
        f"  {authors} ({rec.year or '?'}) · {doi_str}{url_str}{notes}"
    )
