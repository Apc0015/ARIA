"""Index helpers for raw document storage."""

from __future__ import annotations

from typing import Any

from aria.storage.raw import RawStore


class IndexManager:
    """Expose raw-store index loading in a named module."""

    def __init__(self, raw_store: RawStore) -> None:
        self.raw_store = raw_store

    def load(self) -> list[dict[str, Any]]:
        return self.raw_store.load()
