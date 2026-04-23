"""MarkItDown adapter — convert office/pdf/html/audio bytes to Markdown.

Thin wrapper around Microsoft MarkItDown used by collectors to ingest
non-plaintext attachments (DOCX, PPTX, XLSX, PDF, HTML, audio). Callers
get a string; failure returns "".
"""
from __future__ import annotations

import io
import logging
from typing import Optional

logger = logging.getLogger("aria")

# Extensions MarkItDown handles well (as shipped with [docx,pptx,xlsx,pdf] extras).
_SUPPORTED_EXTS = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".csv",
    ".html", ".htm", ".md", ".txt", ".rtf", ".epub", ".json", ".xml",
    ".zip", ".wav", ".mp3", ".m4a",
}

_instance = None


def is_supported(filename_or_ext: str) -> bool:
    """Return True if MarkItDown can convert this extension."""
    ext = filename_or_ext.lower()
    if not ext.startswith("."):
        ext = "." + ext.rsplit(".", 1)[-1]
    return ext in _SUPPORTED_EXTS


def _get() -> Optional[object]:
    global _instance
    if _instance is not None:
        return _instance
    try:
        from markitdown import MarkItDown
        _instance = MarkItDown(enable_plugins=False)
        return _instance
    except ImportError:
        logger.debug("markitdown not installed — attachment conversion disabled")
        return None
    except Exception as exc:
        logger.warning("markitdown init failed: %s", exc)
        return None


def convert_bytes(data: bytes, filename: str) -> str:
    """Convert a byte payload to Markdown. Returns '' on any failure.

    Args:
        data: Raw file bytes.
        filename: Original filename — used for extension-based format detection.
    """
    if not data:
        return ""
    md = _get()
    if md is None:
        return ""
    try:
        # MarkItDown 0.1.x accepts a file-like stream + stream_info with extension.
        from markitdown import StreamInfo
        ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        stream = io.BytesIO(data)
        result = md.convert_stream(stream, stream_info=StreamInfo(extension=ext, filename=filename))
        return (result.text_content or "").strip()
    except Exception as exc:
        logger.debug("markitdown conversion failed for %s: %s", filename, exc)
        return ""


def convert_path(path: str) -> str:
    """Convert a local file path to Markdown. Returns '' on any failure."""
    md = _get()
    if md is None:
        return ""
    try:
        result = md.convert(path)
        return (result.text_content or "").strip()
    except Exception as exc:
        logger.debug("markitdown conversion failed for %s: %s", path, exc)
        return ""
