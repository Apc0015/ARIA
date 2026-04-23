"""Tests for the MarkItDown adapter utility."""
from __future__ import annotations

from aria.engine.utils.markitdown_adapter import convert_bytes, is_supported


def test_is_supported_accepts_office_formats():
    for ext in ["report.docx", "slides.pptx", "data.xlsx", "doc.pdf", "page.html"]:
        assert is_supported(ext) is True


def test_is_supported_rejects_binary_formats():
    for ext in ["movie.mp4", "archive.tar.gz", "bin.exe", "img.gif"]:
        assert is_supported(ext) is False


def test_convert_bytes_html_to_markdown_roundtrip():
    html = b"<h1>Title</h1><p>Paragraph with <b>bold</b> text.</p>"
    md = convert_bytes(html, "sample.html")
    assert "# Title" in md
    assert "**bold**" in md


def test_convert_bytes_empty_input_returns_empty_string():
    assert convert_bytes(b"", "empty.html") == ""


def test_convert_bytes_unsupported_returns_empty_string_or_handles_gracefully():
    # MP4 bytes are gibberish to markitdown — should not raise.
    result = convert_bytes(b"\x00\x01\x02random-binary", "file.mp4")
    assert isinstance(result, str)
