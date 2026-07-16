"""Small raw-document index facade."""

from __future__ import annotations

from typing import Any

from aria.engine.storage.raw_store import RawStore


class IndexManager:
    """Expose raw-store index loading through a focused interface."""

    def __init__(self, raw_store: RawStore) -> None:
        self.raw_store = raw_store

    def load(self) -> list[dict[str, Any]]:
        return self.raw_store.load()
