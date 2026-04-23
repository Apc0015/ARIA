"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from aria.config import load_config
from aria.utils.logger import configure_logging


@pytest.fixture
def temp_output_root() -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def aria_settings(temp_output_root: Path):
    return load_config(output_dir=temp_output_root)


@pytest.fixture
def aria_logger():
    return configure_logging(verbose=True)
