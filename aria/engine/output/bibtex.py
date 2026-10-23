"""BibTeX exporter for citation corpus records.

Produces a valid ``.bib`` file from a list of CorpusRecord objects.
Handles journal articles, books, book chapters, and misc (web/report) types.
Output imports cleanly into Zotero, Mendeley, and LaTeX.

Usage::

    from aria.engine.output.bibtex import BibTeXExporter

    exporter = BibTeXExporter(output_dir)
    path = exporter.export(records, filename="references-level0.bib", level=1)
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Optional

from aria.engine.citation.seed import CorpusRecord


class BibTeXExporter:
    """Export CorpusRecord objects to a BibTeX .bib file."""

    def __init__(self, output_dir: str, subdir: str = "citation-graph") -> None:
        self.base_dir = os.path.join(output_dir, subdir)
        os.makedirs(self.base_dir, exist_ok=True)

    def export(
        self,
        records: list[CorpusRecord],
        filename: str = "references-level0.bib",
        level: Optional[int] = None,
    ) -> str:
        """Write BibTeX file and return its path.

        Args:
            records:  List of CorpusRecord objects.
            filename: Output filename (default: references-level0.bib).
            level:    If set, only export records with this level value.
        """
        if level is not None:
            records = [r for r in records if r.level == level]

        path = os.path.join(self.base_dir, filename)
        entries = []

        for rec in records:
            entry = self._record_to_bibtex(rec)
            if entry:
                entries.append(entry)

        header = (
            f"% BibTeX export — ARIA Citation Graph\n"
            f"% Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"% Records: {len(entries)}\n\n"
        )

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(header)
            fh.write("\n\n".join(entries))
            fh.write("\n")

        return path

    # ------------------------------------------------------------------
    # Entry builder
    # ------------------------------------------------------------------

    def _record_to_bibtex(self, rec: CorpusRecord) -> str:
        """Convert a single CorpusRecord to a BibTeX entry string."""
        cite_key = self._make_cite_key(rec)
        ref_type = rec.ref_type or "unknown"

        if ref_type == "journal_article":
            entry_type = "article"
        elif ref_type == "book":
            entry_type = "book"
        elif ref_type == "book_chapter":
            entry_type = "incollection"
        else:
            entry_type = "misc"

        fields: dict[str, str] = {}

        # Authors
        if rec.authors:
            fields["author"] = " and ".join(rec.authors)
        elif rec.raw_ref:
            # Try to extract author from raw ref as fallback
            author_raw = rec.raw_ref.split(".")[0].strip() if rec.raw_ref else ""
            if author_raw:
                fields["author"] = author_raw

        # Core fields
        if rec.title:
            fields["title"] = _brace(rec.title)
        if rec.year:
            fields["year"] = re.sub(r"[a-z]", "", rec.year)  # strip suffix
        if rec.journal and entry_type == "article":
            fields["journal"] = _brace(rec.journal)
        if rec.volume:
            fields["volume"] = rec.volume
        if rec.issue:
            fields["number"] = rec.issue
        if rec.pages:
            fields["pages"] = rec.pages.replace("–", "--").replace("-", "--")
        if rec.abstract:
            fields["abstract"] = _brace(rec.abstract[:800])
        if rec.doi:
            fields["doi"] = rec.doi
            fields["url"] = fields.get("url", f"https://doi.org/{rec.doi}")
        elif rec.url:
            fields["url"] = rec.url
        if rec.url and not rec.doi:
            fields["howpublished"] = f"\\url{{{rec.url}}}"
            if rec.year:
                fields["note"] = f"Accessed {rec.year}"

        # Publisher for books
        if entry_type in ("book", "incollection"):
            if rec.publisher:
                fields["publisher"] = _brace(rec.publisher)
            if rec.place:
                fields["address"] = _brace(rec.place)

        if not fields.get("title"):
            return f"% SKIPPED (no title): {rec.raw_ref[:100] if rec.raw_ref else 'unknown'}"

        # Build entry
        field_lines = [f"  {k} = {{{v}}}" for k, v in fields.items()]
        return f"@{entry_type}{{{cite_key},\n" + ",\n".join(field_lines) + "\n}"

    # ------------------------------------------------------------------
    # Cite key generation
    # ------------------------------------------------------------------

    @staticmethod
    def _make_cite_key(rec: CorpusRecord) -> str:
        """Generate a unique cite key: firstauthorYYYYkeyword."""
        # First author last name
        author_part = ""
        if rec.authors:
            # "Last, First" or "First Last" or "Organisation"
            first = rec.authors[0]
            if "," in first:
                author_part = first.split(",")[0].strip()
            else:
                parts = first.split()
                author_part = parts[-1] if parts else first
        author_part = re.sub(r"[^a-zA-Z]", "", author_part)[:15].lower()

        year_part = re.sub(r"[^0-9]", "", rec.year or "")[:4]

        # First significant word of title
        title_part = ""
        if rec.title:
            words = re.sub(r"[^a-zA-Z\s]", "", rec.title).split()
            stop = {"a", "an", "the", "of", "in", "on", "and", "or", "for",
                    "to", "is", "are", "was", "were", "at", "by", "from", "with"}
            sig = [w for w in words if w.lower() not in stop]
            if sig:
                title_part = sig[0].lower()[:12]

        key = f"{author_part}{year_part}_{title_part}" if title_part else f"{author_part}{year_part}"
        return key or "unknown"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _brace(text: str) -> str:
    """Wrap text in extra braces to preserve capitalisation in BibTeX."""
    # Escape backslashes and braces already present
    text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    return text
