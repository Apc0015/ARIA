"""Tests for GovernmentCollector."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from aria.engine.collectors.specialized.government import GovernmentCollector


def test_government_collector_instantiates():
    c = GovernmentCollector(max_results=10)
    assert c._max_results == 10


@pytest.mark.asyncio
async def test_government_collector_validate_always_true():
    c = GovernmentCollector()
    assert await c.validate() is True


@pytest.mark.asyncio
async def test_government_datagov_yields_docs():
    """data.gov API path yields correctly shaped documents."""
    fake_response = {
        "result": {
            "results": [
                {
                    "name": "climate-data-2024",
                    "title": "Climate Data 2024",
                    "notes": "Annual climate measurements from NOAA stations.",
                    "organization": {"title": "NOAA"},
                    "tags": [{"name": "climate"}, {"name": "weather"}],
                    "resources": [{"format": "CSV"}, {"format": "JSON"}],
                }
            ]
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(return_value=fake_response)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.specialized.government.httpx.AsyncClient", return_value=mock_client):
        c = GovernmentCollector(max_results=5)
        docs = []
        async for doc in c._search_datagov("climate change", set()):
            docs.append(doc)

    assert len(docs) == 1
    doc = docs[0]
    assert doc["platform"] == "government"
    assert doc["source_type"] == "gov_policy"
    assert "catalog.data.gov" in doc["url"]
    assert "NOAA" in doc["text"]
    assert doc["metadata"]["source"] == "data.gov"


@pytest.mark.asyncio
async def test_government_regulations_skipped_without_key(monkeypatch):
    """regulations.gov not queried when no API key."""
    monkeypatch.delenv("REGULATIONS_GOV_KEY", raising=False)
    c = GovernmentCollector()
    assert c._regulations_key == ""

    docs = []
    async for doc in c._search_regulations("test", set()):
        docs.append(doc)
    assert docs == []
