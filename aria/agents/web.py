"""Open-web collection agent surface."""

from __future__ import annotations

from typing import Any

from aria.engine.collectors.web.pdf import PDFCollector
from aria.engine.collectors.web.scraper import WebScraperCollector
from aria.engine.collectors.web.search import WebSearchCollector


class WebAgent:
    """Composite open-web agent using search plus scrape collectors."""

    def __init__(self, settings: Any, logger: Any, rate_limiter: Any, shared_memory: Any | None = None) -> None:
        self.search = WebSearchCollector(settings, logger, rate_limiter, shared_memory=shared_memory)
        self.pdf = PDFCollector(settings, logger, rate_limiter, shared_memory=shared_memory)
        self.scraper = WebScraperCollector(settings, logger, rate_limiter, self.pdf, shared_memory=shared_memory)

    async def collect(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """Collect web documents for a query."""

        documents: list[dict[str, Any]] = []
        for result in await self.search.collect(query, max_results=max_results):
            url = str(result.get("url", ""))
            if not url:
                continue
            documents.extend(await self.scraper.collect(url))
        return documents


__all__ = ["WebAgent", "WebSearchCollector", "WebScraperCollector"]
