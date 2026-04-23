"""Raw document storage backed by JSONL files."""

from __future__ import annotations

import json
from pathlib import Path


class RawStore:
    """Persistent storage for raw (uncleaned) collected documents."""

    FILENAME = "raw_documents.jsonl"

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._base_dir / self.FILENAME

    def save(self, documents: list[dict]) -> Path:
        """Atomically save documents to a JSONL file.

        Writes to a .tmp file first, then renames to the final path so a
        crash mid-write never leaves a truncated file.
        """
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for doc in documents:
                f.write(json.dumps(doc, ensure_ascii=False, default=str) + "\n")
        tmp.replace(self._path)
        return self._path

    def load(self) -> list[dict]:
        """Load documents from the JSONL file.

        Returns:
            List of document dicts, or empty list if file does not exist.
        """
        if not self._path.exists():
            return []
        docs = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        docs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return docs

    def count(self) -> int:
        """Return the number of stored documents."""
        return len(self.load())
