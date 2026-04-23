"""Abstract base class for all collection sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Optional


@dataclass
class CollectorConfig:
    """Configuration for a collector."""

    name: str
    enabled: bool = True
    rate_limit: Optional[int] = None
    timeout: int = 30
    max_results: int = 100
    extra: dict[str, Any] | None = None


class BaseCollector(ABC):
    """Abstract base class for all collection sources.

    All collectors (web search, academic, social, LLM, etc.)
    inherit from this and implement the async collect() method.
    """

    def __init__(self, config: CollectorConfig):
        """Initialize collector with configuration.

        Args:
            config: Collector configuration
        """
        self.config = config
        self.name = config.name

    @abstractmethod
    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Collect documents for given queries.

        Yields:
            Document dictionaries with 'url', 'title', 'text', 'source_type', etc.
        """
        pass

    async def validate(self) -> bool:
        """Validate collector configuration and credentials.

        Returns:
            True if collector is ready to run, False otherwise.
        """
        return True

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, enabled={self.config.enabled})"
