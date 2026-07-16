from __future__ import annotations

from aria.engine.collectors.web.pdf import PDFCollector as PDFAgent


def test_pdf_agent_alias_exists():
    assert PDFAgent is not None
