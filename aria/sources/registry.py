"""Source registry for dynamic collector registration and management."""

from __future__ import annotations

from typing import Optional

from aria.sources.base import BaseCollector, CollectorConfig


class SourceRegistry:
    """Central registry for all collection sources.

    Enables dynamic registration, discovery, and instantiation of collectors.
    """

    _instance: Optional[SourceRegistry] = None
    _collectors: dict[str, type[BaseCollector]] = {}

    def __new__(cls) -> SourceRegistry:
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, source_type: str, collector_class: type[BaseCollector]) -> None:
        """Register a collector class.

        Args:
            source_type: Unique identifier for the source (e.g., "web_search", "arxiv")
            collector_class: The collector class to register
        """
        cls._collectors[source_type] = collector_class

    @classmethod
    def get(cls, source_type: str, config: CollectorConfig) -> BaseCollector:
        """Get a collector instance.

        Args:
            source_type: Source type identifier
            config: Collector configuration

        Returns:
            Instantiated collector

        Raises:
            ValueError: If source type is not registered
        """
        if source_type not in cls._collectors:
            raise ValueError(f"Unknown source type: {source_type}")
        return cls._collectors[source_type](config)

    @classmethod
    def list_sources(cls) -> list[str]:
        """List all registered sources.

        Returns:
            List of registered source type identifiers
        """
        return sorted(cls._collectors.keys())

    @classmethod
    def list_by_category(cls, category: str) -> list[str]:
        """List sources by category (e.g., 'web', 'academic', 'social').

        Args:
            category: Source category

        Returns:
            List of matching source identifiers
        """
        return [s for s in cls._collectors.keys() if s.startswith(f"{category}_")]
