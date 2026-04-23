"""ARIA — Agentic Research Intelligence Architecture."""

from __future__ import annotations

__version__ = "5.0.0"
__author__ = "Ayush Chhoker"
__author_email__ = "ayush.chhoker@example.com"
__contributors__ = ["ARIA Contributors"]

# Minimal imports to avoid circular deps
# Full imports available after package initialization
try:
    from aria.config import Config, load_config
except ImportError:
    pass

try:
    from aria.types import (
        Document,
        RawDocument,
        CleanDocument,
        Run,
        RunStatus,
    )
except ImportError:
    pass

__all__ = [
    "Config",
    "load_config",
    "Document",
    "RawDocument",
    "CleanDocument",
    "Run",
    "RunStatus",
    "__version__",
]
