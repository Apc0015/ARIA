"""URL and content-based deduplication."""

from __future__ import annotations

import hashlib
from typing import Set


class Deduplicator:
    """Deduplicates documents by URL hash and content fingerprint."""

    def __init__(self) -> None:
        self._url_hashes: Set[str] = set()
        self._content_fingerprints: Set[str] = set()

    def _url_hash(self, url: str) -> str:
        return hashlib.sha256(url.strip().lower().encode()).hexdigest()

    def _content_fingerprint(self, text: str) -> str:
        # Use first 500 chars + length to create a stable fingerprint
        sample = text.strip()[:500] if text else ""
        length = len(text)
        combined = f"{length}:{sample}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def is_duplicate(self, url: str, text: str) -> bool:
        """Check if a document is a duplicate.

        Args:
            url: Document URL.
            text: Document text content.

        Returns:
            True if this is a duplicate (URL or content already seen).
        """
        url_h = self._url_hash(url)
        if url_h in self._url_hashes:
            return True

        if text and len(text.strip()) > 50:
            fp = self._content_fingerprint(text)
            if fp in self._content_fingerprints:
                return True

        return False

    def add(self, url: str, text: str) -> None:
        """Register a document's URL and content fingerprint.

        Args:
            url: Document URL.
            text: Document text content.
        """
        self._url_hashes.add(self._url_hash(url))
        if text and len(text.strip()) > 50:
            self._content_fingerprints.add(self._content_fingerprint(text))

    def reset(self) -> None:
        """Clear all tracked URLs and fingerprints."""
        self._url_hashes.clear()
        self._content_fingerprints.clear()
