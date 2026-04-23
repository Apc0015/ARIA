"""Per-domain async rate limiter."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Dict


class DomainRateLimiter:
    """Async per-domain rate limiter using token bucket algorithm."""

    def __init__(self, default_calls_per_second: float = 1.0) -> None:
        self._default_rate = default_calls_per_second
        self._rates: Dict[str, float] = {}
        self._last_call: Dict[str, float] = defaultdict(float)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def set_rate(self, domain: str, calls_per_second: float) -> None:
        """Set the allowed call rate for a specific domain.

        Args:
            domain: Domain name (e.g., 'arxiv.org').
            calls_per_second: Maximum calls per second allowed.
        """
        self._rates[domain] = calls_per_second

    async def acquire(self, domain: str) -> None:
        """Wait until a request is allowed for the given domain.

        Args:
            domain: Domain name to rate-limit.
        """
        async with self._locks[domain]:
            rate = self._rates.get(domain, self._default_rate)
            min_interval = 1.0 / rate if rate > 0 else 1.0

            now = time.monotonic()
            elapsed = now - self._last_call[domain]
            wait_time = min_interval - elapsed

            if wait_time > 0:
                await asyncio.sleep(wait_time)

            self._last_call[domain] = time.monotonic()
