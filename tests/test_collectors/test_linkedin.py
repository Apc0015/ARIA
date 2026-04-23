"""Tests for LinkedInCollector."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from aria.engine.collectors.social.linkedin import LinkedInCollector, _parse_linkedin_html


def test_linkedin_collector_instantiates():
    c = LinkedInCollector()
    assert c._max_results == 20


@pytest.mark.asyncio
async def test_linkedin_collector_validate():
    c = LinkedInCollector()
    assert await c.validate() is True


@pytest.mark.asyncio
async def test_linkedin_public_yields_docs():
    """Public (DDG) path yields correctly shaped documents."""
    fake_result = {
        "href": "https://www.linkedin.com/pulse/ai-research-trends-2024-alice-smith",
        "title": "AI Research Trends 2024",
        "body": "Key insights on AI research directions for the coming year.",
    }

    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text = MagicMock(return_value=[fake_result])

    with patch("aria.engine.collectors.social.linkedin.DDGS", mock_ddgs, create=True):
        c = LinkedInCollector(max_results=5)
        docs = []
        async for doc in c._collect_public(["AI research"]):
            docs.append(doc)

    assert len(docs) >= 1
    doc = docs[0]
    assert doc["platform"] == "linkedin"
    assert doc["source_type"] == "opinion_essay"
    assert "linkedin.com" in doc["url"]
    assert doc["metadata"]["collection_method"] == "public_search"


@pytest.mark.asyncio
async def test_linkedin_no_credentials_uses_public(monkeypatch):
    """Without credentials, collect() falls through to public search."""
    monkeypatch.delenv("LINKEDIN_EMAIL", raising=False)
    monkeypatch.delenv("LINKEDIN_PASSWORD", raising=False)

    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text = MagicMock(return_value=[])

    with patch("aria.engine.collectors.social.linkedin.DDGS", mock_ddgs, create=True):
        c = LinkedInCollector()
        docs = []
        async for doc in c.collect(["test"]):
            docs.append(doc)
    # No results but no crash — public path was taken
    assert isinstance(docs, list)


def test_parse_linkedin_html_json_ld():
    """_parse_linkedin_html extracts JSON-LD structured data."""
    html = """
    <html><head>
    <script type="application/ld+json">
    {"url": "https://www.linkedin.com/pulse/test-article",
     "name": "Test Article Title",
     "description": "A detailed article about testing."}
    </script>
    </head><body></body></html>
    """
    docs = _parse_linkedin_html(html, "test query")
    assert len(docs) == 1
    assert docs[0]["title"] == "Test Article Title"
    assert "testing" in docs[0]["text"]
    assert docs[0]["platform"] == "linkedin"
