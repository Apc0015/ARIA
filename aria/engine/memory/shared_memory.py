"""Shared memory backend for cross-agent state tracking."""

from __future__ import annotations

import hashlib
import threading
from typing import Any, Optional


class SharedMemory:
    """In-memory (or Redis-backed) shared state for collector agents.

    Tracks seen URLs and content fingerprints to prevent duplicates
    across multiple parallel collectors.
    """

    def __init__(self, backend: str = "dict", redis_url: Optional[str] = None) -> None:
        self._backend = backend
        self._redis_url = redis_url
        self._store: dict[str, Any] = {}
        self._seen_urls: set[str] = set()
        self._seen_fingerprints: set[str] = set()
        self._redis = None
        self._lock = threading.Lock()

        if backend == "redis" and redis_url:
            self._init_redis(redis_url)

    def _init_redis(self, redis_url: str) -> None:
        try:
            import redis

            self._redis = redis.from_url(redis_url, decode_responses=True)
            self._redis.ping()
        except Exception:
            self._redis = None
            self._backend = "dict"

    def set(self, key: str, value: Any) -> None:
        """Store a key-value pair.

        Args:
            key: Storage key.
            value: Value to store.
        """
        self._store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value by key.

        Args:
            key: Storage key.
            default: Default value if key not found.

        Returns:
            Stored value or default.
        """
        return self._store.get(key, default)

    def add_url(self, url: str) -> bool:
        """Register a URL as seen.

        Args:
            url: URL to register.

        Returns:
            True if the URL is new, False if already seen.
        """
        from aria.utils.url import normalize_url

        normalized = normalize_url(url).lower()
        if not normalized:
            return False
        url_hash = hashlib.sha256(normalized.encode()).hexdigest()

        if self._redis:
            added = self._redis.sadd("aria:seen_urls", url_hash)
            return bool(added)

        with self._lock:
            if url_hash in self._seen_urls:
                return False
            self._seen_urls.add(url_hash)
            return True

    def add_fingerprint(self, fp: str) -> bool:
        """Register a content fingerprint as seen.

        Args:
            fp: Content fingerprint string.

        Returns:
            True if the fingerprint is new, False if already seen.
        """
        if self._redis:
            added = self._redis.sadd("aria:seen_fingerprints", fp)
            return bool(added)

        with self._lock:
            if fp in self._seen_fingerprints:
                return False
            self._seen_fingerprints.add(fp)
            return True

    def clear(self) -> None:
        """Clear all tracked state."""
        with self._lock:
            self._store.clear()
            self._seen_urls.clear()
            self._seen_fingerprints.clear()
        if self._redis:
            self._redis.delete("aria:seen_urls", "aria:seen_fingerprints")
