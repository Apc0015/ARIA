"""Structured logging configuration for ARIA."""

from __future__ import annotations

from pathlib import Path

from aria.config import PROJECT_ROOT
from aria.engine.utils.logger import configure_logging as configure_legacy_logging


def configure_logging(log_dir: Path | None = None, verbose: bool = False):
    """Configure the shared logger using the root logs directory by default."""

    destination = (log_dir or (PROJECT_ROOT / "logs")).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    return configure_legacy_logging(verbose=verbose)
