"""
Semantic deduplication — goes beyond URL/hash matching.

Two strategies (both run if available):
  1. MinHash LSH  — near-duplicate text detection (requires datasketch)
  2. Embedding cosine similarity — semantic duplicate detection (requires sentence-transformers)

Falls back gracefully to the existing content-fingerprint approach.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("aria")

# ─── MinHash LSH ─────────────────────────────────────────────────────────────

_minhash_available = False
try:
    from datasketch import MinHash, MinHashLSH
    _minhash_available = True
except ImportError:
    pass


def _text_shingles(text: str, k: int = 3) -> list[bytes]:
    """Convert text to k-word shingles for MinHash."""
    words = re.findall(r"\b\w+\b", text.lower())
    if len(words) < k:
        return [" ".join(words).encode()]
    return [" ".join(words[i:i+k]).encode() for i in range(len(words) - k + 1)]


class MinHashDeduplicator:
    """
    Near-duplicate detector using MinHash LSH.
    Similarity threshold: 0.8 (80% text overlap = duplicate).
    """

    def __init__(self, threshold: float = 0.80, num_perm: int = 128) -> None:
        self._threshold = threshold
        self._num_perm = num_perm
        self._lsh: Optional[Any] = None
        self._index: dict[str, str] = {}  # key → url
        self._available = _minhash_available

        if self._available:
            self._lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
            logger.debug("MinHash LSH deduplicator initialised (threshold=%.2f)", threshold)
        else:
            logger.debug("datasketch not installed — MinHash dedup disabled")

    def _make_minhash(self, text: str) -> Optional[Any]:
        if not self._available:
            return None
        m = MinHash(num_perm=self._num_perm)
        for shingle in _text_shingles(text):
            m.update(shingle)
        return m

    def is_duplicate(self, text: str, url: str = "") -> bool:
        """Return True if text is a near-duplicate of something already seen."""
        if not self._available or not text or len(text.strip()) < 100:
            return False
        m = self._make_minhash(text)
        if m is None:
            return False

        key = url or text[:50]
        try:
            results = self._lsh.query(m)
            return len(results) > 0
        except Exception:
            return False

    def add(self, text: str, url: str = "") -> None:
        """Register a text as seen."""
        if not self._available or not text or len(text.strip()) < 100:
            return
        m = self._make_minhash(text)
        if m is None:
            return

        key = (url or text[:50])[:200]
        if key not in self._index:
            try:
                self._lsh.insert(key, m)
                self._index[key] = url
            except Exception as exc:
                logger.debug("MinHash insert failed: %s", exc)

    def check_and_add(self, text: str, url: str = "") -> bool:
        """
        Check if duplicate, then register.
        Returns True if it IS a duplicate (should be skipped).
        """
        if self.is_duplicate(text, url):
            return True
        self.add(text, url)
        return False


# ─── Embedding-based dedup ────────────────────────────────────────────────────

class EmbeddingDeduplicator:
    """
    Semantic duplicate detector using sentence-transformers.
    Catches paraphrased content MinHash misses.
    Similarity threshold: 0.92 (very high — only true semantic duplicates).
    """

    def __init__(self, threshold: float = 0.92) -> None:
        self._threshold = threshold
        self._embeddings: list[tuple[str, Any]] = []  # (url, embedding)
        self._encoder = None
        self._available = False
        self._try_load()

    def _try_load(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            # all-MiniLM-L6-v2 is ~90MB; downloaded once to ~/.cache/huggingface/
            # First run will take 10-60s depending on connection speed.
            logger.info(
                "Loading sentence-transformers model 'all-MiniLM-L6-v2' "
                "(~90MB, one-time download). Set ARIA_SEMANTIC_DEDUP=false to skip."
            )
            self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
            self._available = True
            logger.debug("Embedding deduplicator initialised")
        except ImportError:
            logger.debug("sentence-transformers not installed — embedding dedup disabled")
        except Exception as exc:
            logger.debug("Embedding dedup init failed: %s", exc)

    def check_and_add(self, text: str, url: str = "") -> bool:
        """
        Returns True if text is a semantic duplicate of something already seen.
        """
        if not self._available or not text or len(text.strip()) < 200:
            return False

        try:
            import numpy as np
            snippet = text[:800]
            new_emb = self._encoder.encode(snippet, convert_to_numpy=True)

            for _, stored_emb in self._embeddings:
                sim = float(np.dot(new_emb, stored_emb) / (
                    np.linalg.norm(new_emb) * np.linalg.norm(stored_emb) + 1e-9
                ))
                if sim >= self._threshold:
                    return True  # semantic duplicate

            self._embeddings.append((url, new_emb))
            return False
        except Exception as exc:
            logger.debug("Embedding dedup check failed: %s", exc)
            return False


# ─── Combined deduplicator ────────────────────────────────────────────────────

class SemanticDeduplicator:
    """
    Combines MinHash LSH + optional embedding similarity.
    Drop-in replacement for the existing fingerprint-based approach.

    Usage:
        dedup = SemanticDeduplicator()
        for doc in docs:
            if dedup.is_duplicate(doc):
                continue  # skip
            yield doc
    """

    def __init__(
        self,
        minhash_threshold: float = 0.80,
        embedding_threshold: float = 0.92,
        use_embeddings: bool = True,
    ) -> None:
        self._minhash = MinHashDeduplicator(threshold=minhash_threshold)
        self._embed = EmbeddingDeduplicator(threshold=embedding_threshold) if use_embeddings else None

    def is_duplicate(self, doc: dict[str, Any]) -> bool:
        """
        Return True if this document is a near-duplicate of one already processed.
        Registers the document if it is new.
        """
        text = doc.get("text", "")
        url = doc.get("url", "")

        # MinHash check
        if self._minhash.check_and_add(text, url):
            logger.debug("MinHash duplicate: %s", url[:80])
            return True

        # Embedding check (only for longer documents)
        if self._embed and len(text) > 200:
            if self._embed.check_and_add(text, url):
                logger.debug("Semantic duplicate: %s", url[:80])
                return True

        return False

    def filter_documents(
        self,
        docs: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Filter a list of documents, removing duplicates.

        Returns:
            (unique_docs, num_removed)
        """
        unique = []
        removed = 0
        for doc in docs:
            if self.is_duplicate(doc):
                removed += 1
            else:
                unique.append(doc)
        if removed:
            logger.info("Semantic dedup removed %d duplicates from %d docs", removed, len(docs))
        return unique, removed
