"""Abstract base class for all aria.engine collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Any


class BaseCollector(ABC):
    """Abstract base for all document collectors.

    Subclasses implement collect() as an async generator that yields
    document dicts.
    """

    @abstractmethod
    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Collect documents for the given search queries.

        Args:
            queries: List of search query strings.

        Yields:
            Document dicts conforming to the standard schema.
        """
        # Make this a generator to satisfy type checking
        yield  # type: ignore[misc]

    async def validate(self) -> bool:
        """Check that the collector is operational.

        Returns:
            True if ready to collect.
        """
        return True
