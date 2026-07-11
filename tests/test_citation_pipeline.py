"""Tests for the citation graph pipeline — Issue #3 fix.

Covers: ref_parser, seed.CorpusRecord, citation_crawl_enabled,
        citation_exporter, bibtex exporter, seed API helpers.
All tests are pure unit tests (no network calls, no filesystem I/O beyond tmp).
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

# ---------------------------------------------------------------------------
# ref_parser tests
# ---------------------------------------------------------------------------

from aria.engine.citation.ref_parser import ReferenceParser, RefRecord


class TestReferenceParser:
    def setup_method(self):
        self.parser = ReferenceParser()

    def test_journal_article_full(self):
        raw = "Londregan, J.B. & Poole, K.T. 1990. Poverty, the coup trap, and the seizure of executive power. World Politics, 42(2):151-183."
        rec = self.parser.parse_one(raw)
        assert rec["title"] == "Poverty, the coup trap, and the seizure of executive power"
        assert rec["journal"] == "World Politics"
        assert rec["volume"] == "42"
        assert rec["issue"] == "2"
        assert rec["pages"] == "151-183"
        assert rec["year"] == "1990"
        assert rec["ref_type"] == "journal_article"

    def test_web_report_with_url(self):
        raw = "Africa Center for Strategic Studies. 2022. Understanding Burkina Faso's latest coup. Retrieved from https://africacenter.org/spotlight/burkina-faso-coup/ [Accessed 1 Jan 2023]."
        rec = self.parser.parse_one(raw)
        assert rec["ref_type"] == "web_report"
        assert "africacenter.org" in rec["url"]
        assert rec["year"] == "2022"

    def test_book_record(self):
        raw = "Blaikie, P., Cannon, T., Davis, I. & Wisner, B. 2014. At risk: Natural hazards, people's vulnerability and disasters. London: Routledge."
        rec = self.parser.parse_one(raw)
        assert rec["year"] == "2014"
        assert "At risk" in rec["title"]

    def test_book_chapter(self):
        raw = "LaPalombara, J. 1971. Distribution: A crisis of resource management. In L. Binder (ed.) Crises and sequences in political development. Princeton, NJ: Princeton University Press, 233-282."
        rec = self.parser.parse_one(raw)
        assert rec["ref_type"] == "book_chapter"

    def test_no_year_flagged(self):
        raw = "Some Author. Title without a year anywhere here. Journal Name."
        rec = self.parser.parse_one(raw)
        assert "no_year_found" in rec["parse_notes"]

    def test_authors_split_ampersand(self):
        raw = "Turner, B.L. & Kasperson, R.E. 2003. A framework. PNAS, 100(14):8074-8079."
        rec = self.parser.parse_one(raw)
        assert len(rec["authors"]) == 2
        assert "Turner" in rec["authors"][0]

    def test_parse_list(self):
        raws = [
            "Author A. 2020. Title one. Journal X, 1(1):1-10.",
            "Author B. 2021. Title two. Journal Y, 2(2):11-20.",
        ]
        records = self.parser.parse_list(raws)
        assert len(records) == 2
        assert records[0]["year"] == "2020"
        assert records[1]["year"] == "2021"

    def test_doi_extraction(self):
        raw = "Some Author. 2024. Some Title. https://doi.org/10.5787/52-3-1483"
        rec = self.parser.parse_one(raw)
        assert "10.5787/52-3-1483" in rec["doi"]

    def test_long_title_truncated(self):
        long_title = "A " + "word " * 200
        raw = f"Smith, J. 2020. {long_title}. Some Journal, 1(1):1-5."
        rec = self.parser.parse_one(raw)
        assert len(rec["title"]) <= 300

    def test_text_block_split(self):
        block = """Smith, A. 2020. First paper. Journal A, 1(1):1-10.

Jones, B. 2021. Second paper. Journal B, 2(2):11-20.

Brown, C. 2022. Third paper. Journal C, 3(3):21-30."""
        records = self.parser.parse_text_block(block)
        assert len(records) == 3


# ---------------------------------------------------------------------------
# CorpusRecord tests
# ---------------------------------------------------------------------------

from aria.engine.citation.seed import CorpusRecord


class TestCorpusRecord:
    def test_default_fields(self):
        rec = CorpusRecord()
        assert rec.level == 0
        assert rec.doi == ""
        assert rec.authors == []
        assert rec.full_text_available is False
        assert rec.authors_raw == ""  # Issue #9 — field must exist

    def test_to_dict_has_all_fields(self):
        rec = CorpusRecord(
            level=1,
            doi="10.1000/xyz",
            title="Test Paper",
            authors=["Smith, J."],
            year="2020",
            authors_raw="Smith, J.",
        )
        d = rec.to_dict()
        assert d["level"] == 1
        assert d["doi"] == "10.1000/xyz"
        assert d["authors_raw"] == "Smith, J."
        assert "full_text_available" in d
        assert "access_status" in d
        assert "doi_status" in d

    def test_to_dict_level1_fields(self):
        rec = CorpusRecord(level=1, raw_ref="Some raw ref string")
        d = rec.to_dict()
        assert d["raw_ref"] == "Some raw ref string"


# ---------------------------------------------------------------------------
# citation_crawl_enabled tests
# ---------------------------------------------------------------------------

from aria.engine.orchestrator.citation_crawl import citation_crawl_enabled


class TestCitationCrawlEnabled:
    def test_enabled_with_doi(self):
        cfg = {"citation_crawl": {"enabled": True, "seed_doi": "10.5787/52-3-1483"}}
        assert citation_crawl_enabled(cfg) is True

    def test_enabled_with_url(self):
        cfg = {"citation_crawl": {"enabled": True, "seed_url": "https://example.com/paper"}}
        assert citation_crawl_enabled(cfg) is True

    def test_disabled_flag(self):
        cfg = {"citation_crawl": {"enabled": False, "seed_doi": "10.5787/52-3-1483"}}
        assert citation_crawl_enabled(cfg) is False

    def test_no_citation_crawl_key(self):
        cfg = {"collection": {"topic": "test"}}
        assert citation_crawl_enabled(cfg) is False

    def test_empty_config(self):
        assert citation_crawl_enabled({}) is False

    def test_enabled_no_seed(self):
        # enabled:true but no seed_doi or seed_url — should be False
        cfg = {"citation_crawl": {"enabled": True}}
        assert citation_crawl_enabled(cfg) is False

    def test_object_config(self):
        class FakeConfig:
            citation_crawl = {"enabled": True, "seed_doi": "10.1000/test"}
        assert citation_crawl_enabled(FakeConfig()) is True


# ---------------------------------------------------------------------------
# CitationExporter tests
# ---------------------------------------------------------------------------

from aria.engine.output.citation_exporter import CitationExporter


class TestCitationExporter:
    def test_corpus_json_schema(self, tmp_path):
        records = [
            CorpusRecord(level=0, doi="10.1000/seed", title="Seed Paper",
                         authors=["Author, A."], year="2024",
                         full_text_available=True, access_status="open_access",
                         doi_status="verified"),
            CorpusRecord(level=1, doi="10.1000/ref1", title="Reference One",
                         authors=["Other, B."], year="2020",
                         access_status="paywalled", doi_status="verified"),
            CorpusRecord(level=1, title="Reference Two No DOI",
                         year="2019", access_status="unavailable",
                         doi_status="not_found"),
        ]
        exporter = CitationExporter(str(tmp_path))
        paths = exporter.export(records)

        # corpus.json exists and is valid JSON
        assert os.path.exists(paths["corpus_json"])
        with open(paths["corpus_json"]) as f:
            data = json.load(f)
        assert len(data) == 3
        # Check required fields present on every record
        required = ["level", "doi", "title", "authors", "year", "full_text_available",
                    "access_status", "doi_status"]
        for rec in data:
            for field in required:
                assert field in rec, f"Missing field {field}"
        # Level 0 record correct
        assert data[0]["level"] == 0
        assert data[0]["doi"] == "10.1000/seed"

    def test_missing_full_text_md(self, tmp_path):
        records = [
            CorpusRecord(level=0, title="Seed", full_text_available=True, access_status="open_access"),
            CorpusRecord(level=1, title="Paywalled Paper", access_status="paywalled",
                         doi="10.1000/pw", authors=["X, Y."], year="2020",
                         ref_type="journal_article"),
            CorpusRecord(level=1, title="Unavailable Paper", access_status="unavailable",
                         authors=["Z, W."], year="2021"),
            CorpusRecord(level=1, title="Open Access Got Text", access_status="open_access",
                         full_text_available=True),
        ]
        exporter = CitationExporter(str(tmp_path))
        paths = exporter.export(records)

        assert os.path.exists(paths["missing_full_text"])
        content = open(paths["missing_full_text"]).read()
        assert "Paywalled" in content
        assert "Unavailable" in content or "Fetch Failed" in content
        # Open access with full text should NOT appear
        assert "Open Access Got Text" not in content


# ---------------------------------------------------------------------------
# BibTeXExporter tests
# ---------------------------------------------------------------------------

from aria.engine.output.bibtex import BibTeXExporter


class TestBibTeXExporter:
    def test_journal_article_entry(self, tmp_path):
        rec = CorpusRecord(
            level=1, title="Poverty the coup trap",
            authors=["Londregan, J.B.", "Poole, K.T."],
            year="1990", journal="World Politics",
            volume="42", issue="2", pages="151-183",
            doi="10.1017/abc", ref_type="journal_article",
        )
        bex = BibTeXExporter(str(tmp_path))
        entry = bex._record_to_bibtex(rec)
        assert entry.startswith("@article{")
        assert "londregan1990" in entry
        assert "journal" in entry
        assert "volume = {42}" in entry
        assert "number = {2}" in entry
        assert "pages = {151--183}" in entry

    def test_book_entry(self, tmp_path):
        rec = CorpusRecord(
            level=1, title="At Risk Natural Hazards",
            authors=["Blaikie, P."], year="2014",
            publisher="Routledge", place="London",
            ref_type="book",
        )
        bex = BibTeXExporter(str(tmp_path))
        entry = bex._record_to_bibtex(rec)
        assert entry.startswith("@book{")
        assert "publisher" in entry

    def test_no_title_skipped(self, tmp_path):
        rec = CorpusRecord(level=1, ref_type="journal_article")
        bex = BibTeXExporter(str(tmp_path))
        entry = bex._record_to_bibtex(rec)
        assert entry.startswith("% SKIPPED")

    def test_cite_key_format(self, tmp_path):
        rec = CorpusRecord(
            level=1, authors=["Turner, B.L."], year="2003",
            title="A framework for vulnerability", ref_type="journal_article",
        )
        bex = BibTeXExporter(str(tmp_path))
        key = bex._make_cite_key(rec)
        assert "turner" in key
        assert "2003" in key
        assert "framework" in key

    def test_export_file(self, tmp_path):
        records = [
            CorpusRecord(level=0, title="Seed", ref_type="journal_article"),
            CorpusRecord(level=1, title="Ref One", authors=["A, B."], year="2020",
                         journal="Journal", ref_type="journal_article"),
            CorpusRecord(level=1, title="Ref Two", authors=["C, D."], year="2021",
                         ref_type="book"),
        ]
        bex = BibTeXExporter(str(tmp_path))
        path = bex.export(records, level=1)
        assert os.path.exists(path)
        content = open(path).read()
        assert "@article{" in content or "@book{" in content
        assert "Ref One" in content
        assert "Ref Two" in content
        # Level 0 should not appear
        assert "Seed" not in content or content.count("Seed") <= 1  # only in header comment


# ---------------------------------------------------------------------------
# seed API helper tests (no network)
# ---------------------------------------------------------------------------

from aria.api.routes.seed import (
    _extract_doi, _extract_year, _extract_abstract,
    _extract_title, _extract_authors,
)


class TestSeedApiHelpers:
    def test_extract_doi(self):
        text = "Published at DOI: 10.5787/52-3-1483 in Scientia Militaria"
        assert _extract_doi(text) == "10.5787/52-3-1483"

    def test_extract_doi_missing(self):
        assert _extract_doi("No DOI here") == ""

    def test_extract_year(self):
        assert _extract_year("Published in 2024 in Cape Town") == "2024"
        assert _extract_year("Older paper from 1990") == "1990"
        assert _extract_year("No year") == ""

    def test_extract_abstract(self):
        # Abstract section followed by Introduction — extraction should stop at Introduction
        text = "Title here\nAbstract\nCoups do not occur randomly. They are significant. This study examines vulnerability.\nIntroduction\nMore text here."
        abstract = _extract_abstract(text)
        assert "Coups do not occur" in abstract
        assert "Introduction" not in abstract

    def test_extract_abstract_missing(self):
        text = "Just a title line. No abstract marker present anywhere in this text."
        abstract = _extract_abstract(text)
        assert abstract == ""

    def test_extract_title(self):
        text = "Where did you hear that? Narrative Competition\nAuthors: Smith, J.\nAbstract"
        title = _extract_title(text)
        assert len(title) > 0
        assert len(title) <= 300

    def test_extract_authors_ampersand(self):
        text = "Smith, J. & Jones, A. & Brown, B.\nAbstract\nIntroduction"
        authors = _extract_authors(text)
        # Should find multiple authors
        assert isinstance(authors, list)
