"""Tests for NewsCollector."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from aria.engine.collectors.specialized.news import NewsCollector


def test_news_collector_instantiates():
    c = NewsCollector(max_results=20)
    assert c._max_results == 20


@pytest.mark.asyncio
async def test_news_collector_validate_with_feedparser():
    """validate() returns True when feedparser is available."""
    c = NewsCollector()
    try:
        import feedparser  # noqa
        result = await c.validate()
        assert result is True
    except ImportError:
        pytest.skip("feedparser not installed")


@pytest.mark.asyncio
async def test_news_collector_no_keys_skips_api(monkeypatch):
    """Without API keys, NewsAPI and GNews methods yield nothing."""
    monkeypatch.delenv("NEWS_API_KEY", raising=False)
    monkeypatch.delenv("GNEWS_API_KEY", raising=False)
    c = NewsCollector()
    assert c._newsapi_key == ""
    assert c._gnews_key == ""


@pytest.mark.asyncio
async def test_news_newsapi_yields_docs():
    """NewsAPI path yields correctly shaped documents."""
    fake_response = {
        "articles": [
            {
                "url": "https://example-news.com/article1",
                "title": "New AI breakthrough announced",
                "description": "Researchers unveil a novel architecture for language models.",
                "content": "Full content here about the AI breakthrough.",
                "source": {"name": "TechNews"},
                "publishedAt": "2024-01-15T10:00:00Z",
                "author": "Jane Doe",
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(return_value=fake_response)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.specialized.news.httpx.AsyncClient", return_value=mock_client):
        c = NewsCollector()
        c._newsapi_key = "fake-key"
        docs = []
        async for doc in c._search_newsapi("AI", set()):
            docs.append(doc)

    assert len(docs) == 1
    doc = docs[0]
    assert doc["platform"] == "news"
    assert doc["source_type"] == "news_article"
    assert doc["url"] == "https://example-news.com/article1"
    assert "AI breakthrough" in doc["text"]
    assert doc["metadata"]["provider"] == "newsapi"


@pytest.mark.asyncio
async def test_news_newsapi_invalid_key_yields_nothing():
    """401 from NewsAPI yields no docs."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.specialized.news.httpx.AsyncClient", return_value=mock_client):
        c = NewsCollector()
        c._newsapi_key = "bad-key"
        docs = []
        async for doc in c._search_newsapi("AI", set()):
            docs.append(doc)

    assert docs == []
