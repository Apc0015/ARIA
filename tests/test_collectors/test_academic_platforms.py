"""Tests for AcademicPlatformsCollector."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from aria.engine.collectors.academic.core_platforms import AcademicPlatformsCollector


def test_academic_platforms_collector_instantiates():
    c = AcademicPlatformsCollector(max_results=10)
    assert c._max_results == 10


@pytest.mark.asyncio
async def test_academic_platforms_validate_no_credentials(monkeypatch):
    """validate() returns False when no credentials are set."""
    for key in ("IEEE_API_KEY", "ELSEVIER_API_KEY", "SPRINGER_API_KEY",
                "JSTOR_SESSION_COOKIE", "ACM_SESSION_COOKIE"):
        monkeypatch.delenv(key, raising=False)

    c = AcademicPlatformsCollector()
    result = await c.validate()
    assert result is False


@pytest.mark.asyncio
async def test_academic_platforms_validate_with_ieee_key(monkeypatch):
    monkeypatch.setenv("IEEE_API_KEY", "fake-ieee-key")
    c = AcademicPlatformsCollector()
    result = await c.validate()
    assert result is True


@pytest.mark.asyncio
async def test_ieee_search_yields_docs():
    """IEEE Xplore search path yields correctly shaped documents."""
    fake_response = {
        "articles": [
            {
                "title": "Deep Learning for Medical Image Analysis",
                "doi": "10.1109/TPAMI.2023.123456",
                "html_url": "https://ieeexplore.ieee.org/document/123456",
                "abstract": "We present a novel deep learning approach for medical imaging.",
                "authors": {"authors": [
                    {"full_name": "Alice Smith"},
                    {"full_name": "Bob Jones"},
                ]},
                "publication_title": "IEEE Transactions on Pattern Analysis",
                "publication_year": "2023",
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

    with patch("aria.engine.collectors.academic.platforms.httpx.AsyncClient", return_value=mock_client):
        c = AcademicPlatformsCollector()
        c._ieee_key = "fake-key"
        c._resolver = MagicMock(resolve=AsyncMock(return_value=None))
        docs = []
        async for doc in c._search_ieee("deep learning medical", set()):
            docs.append(doc)

    assert len(docs) == 1
    doc = docs[0]
    assert doc["source_type"] == "academic_paper"
    assert doc["platform"] == "academic_platforms"
    assert doc["metadata"]["provider"] == "ieee"
    assert doc["metadata"]["doi"] == "10.1109/TPAMI.2023.123456"
    assert "Alice Smith" in doc["text"]


@pytest.mark.asyncio
async def test_ieee_invalid_key_yields_nothing():
    """401 from IEEE API yields no docs."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.academic.platforms.httpx.AsyncClient", return_value=mock_client):
        c = AcademicPlatformsCollector()
        c._ieee_key = "bad-key"
        docs = []
        async for doc in c._search_ieee("test query", set()):
            docs.append(doc)

    assert docs == []
