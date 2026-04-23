from __future__ import annotations

from aria.agents.pdf import PDFAgent


def test_pdf_agent_alias_exists():
    assert PDFAgent is not None
