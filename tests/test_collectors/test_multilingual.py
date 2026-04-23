"""Tests for MultilingualCollector."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from aria.engine.collectors.specialized.multilingual import (
    MultilingualCollector,
    _parse_regions,
    _DEFAULT_REGIONS,
    _REGION_LANG_MAP,
)


def test_multilingual_collector_instantiates():
    c = MultilingualCollector(max_results=10)
    assert c._max_results == 10
    assert isinstance(c._regions, list)
    assert len(c._regions) > 0


def test_parse_regions_defaults(monkeypatch):
    monkeypatch.delenv("MULTILINGUAL_REGIONS", raising=False)
    regions = _parse_regions()
    assert regions == _DEFAULT_REGIONS


def test_parse_regions_custom(monkeypatch):
    monkeypatch.setenv("MULTILINGUAL_REGIONS", "de-de,ja-jp")
    regions = _parse_regions()
    assert "de-de" in regions
    assert "ja-jp" in regions
    assert len(regions) == 2


def test_parse_regions_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("MULTILINGUAL_REGIONS", "xx-xx,yy-yy")
    regions = _parse_regions()
    assert regions == _DEFAULT_REGIONS


@pytest.mark.asyncio
async def test_multilingual_collector_validate():
    c = MultilingualCollector()
    assert await c.validate() is True


@pytest.mark.asyncio
async def test_multilingual_collector_yields_docs():
    """Collector yields docs with correct language field from region."""
    fake_result = {
        "href": "https://de.wikipedia.org/wiki/Kuenstliche_Intelligenz",
        "title": "Künstliche Intelligenz — Wikipedia",
        "body": "Künstliche Intelligenz beschreibt die Simulation menschlicher Intelligenz.",
    }

    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text = MagicMock(return_value=[fake_result])

    with patch("aria.engine.collectors.specialized.multilingual.DDGS", mock_ddgs, create=True):
        c = MultilingualCollector(max_results=5)
        c._regions = ["de-de"]  # only test one region

        docs = []
        async for doc in c.collect(["artificial intelligence"]):
            docs.append(doc)

    assert len(docs) >= 1
    doc = docs[0]
    assert doc["platform"] == "multilingual"
    assert doc["source_type"] == "web_page"
    assert doc["language"] == "de"
    assert doc["metadata"]["region"] == "de-de"
