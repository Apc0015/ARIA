"""Tests for the new Jina AI + crawl4ai fallback methods in WebScraperCollector."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_scrape_jina_returns_doc_on_success():
    from aria.engine.collectors.web.scraper import WebScraperCollector

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="A" * 200)

    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.get = MagicMock(return_value=mock_cm)

    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("aria.engine.collectors.web.scraper.aiohttp.ClientSession", return_value=mock_session_cm):
        scraper = WebScraperCollector()
        doc = await scraper._scrape_jina("https://example.com/page", "example.com")

    assert doc is not None
    assert doc["url"] == "https://example.com/page"
    assert len(doc["text"]) >= 200
    assert doc["source_type"] == "web_page"


@pytest.mark.asyncio
async def test_scrape_jina_returns_none_on_short_body():
    from aria.engine.collectors.web.scraper import WebScraperCollector

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="short")

    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.get = MagicMock(return_value=mock_cm)

    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("aria.engine.collectors.web.scraper.aiohttp.ClientSession", return_value=mock_session_cm):
        scraper = WebScraperCollector()
        doc = await scraper._scrape_jina("https://example.com/page", "example.com")

    assert doc is None


@pytest.mark.asyncio
async def test_scrape_jina_returns_none_on_error():
    from aria.engine.collectors.web.scraper import WebScraperCollector

    with patch("aria.engine.collectors.web.scraper.aiohttp.ClientSession", side_effect=Exception("network error")):
        scraper = WebScraperCollector()
        doc = await scraper._scrape_jina("https://example.com/page", "example.com")

    assert doc is None


@pytest.mark.asyncio
async def test_scrape_crawl4ai_returns_none_when_unavailable():
    """crawl4ai not installed → returns None silently."""
    import aria.engine.collectors.web.scraper as scraper_mod
    original = scraper_mod._CRAWL4AI_AVAILABLE
    scraper_mod._CRAWL4AI_AVAILABLE = False
    try:
        scraper = scraper_mod.WebScraperCollector()
        doc = await scraper._scrape_crawl4ai("https://example.com/page", "example.com")
        assert doc is None
    finally:
        scraper_mod._CRAWL4AI_AVAILABLE = original
