"""Tests for WebOfScienceHandler."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from aria.access.platforms.web_of_science import WebOfScienceHandler


def test_wos_handler_instantiates():
    h = WebOfScienceHandler()
    assert h._api_key is None
    assert h._authenticated is False


@pytest.mark.asyncio
async def test_wos_authenticate_with_key():
    h = WebOfScienceHandler()
    result = await h.authenticate({"api_key": "fake-wos-key"})
    assert result is True
    assert h._api_key == "fake-wos-key"
    assert h.is_authenticated is True


@pytest.mark.asyncio
async def test_wos_authenticate_no_key(monkeypatch):
    monkeypatch.delenv("WOS_API_KEY", raising=False)
    h = WebOfScienceHandler()
    result = await h.authenticate({})
    assert result is False
    assert h.is_authenticated is False


@pytest.mark.asyncio
async def test_wos_authenticate_from_env(monkeypatch):
    monkeypatch.setenv("WOS_API_KEY", "env-key-123")
    h = WebOfScienceHandler()
    result = await h.authenticate({})
    assert result is True
    assert h._api_key == "env-key-123"


@pytest.mark.asyncio
async def test_wos_fetch_without_auth():
    h = WebOfScienceHandler()
    result = await h.fetch("https://www.webofscience.com/wos/woscc/full-record/WOS:000123")
    assert result is None


@pytest.mark.asyncio
async def test_wos_search_yields_json():
    fake_json = '{"hits": [{"uid": "WOS:000123", "title": "Test Paper"}]}'

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = fake_json

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.access.platforms.web_of_science.httpx.AsyncClient", return_value=mock_client):
        h = WebOfScienceHandler()
        h._api_key = "fake-key"
        h._authenticated = True
        result = await h.search("machine learning")

    assert result == fake_json


@pytest.mark.asyncio
async def test_wos_search_invalid_key_returns_none():
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.access.platforms.web_of_science.httpx.AsyncClient", return_value=mock_client):
        h = WebOfScienceHandler()
        h._api_key = "bad-key"
        h._authenticated = True
        result = await h.search("test")

    assert result is None
    assert h.is_authenticated is False


def test_extract_uid():
    uid = WebOfScienceHandler._extract_uid(
        "https://www.webofscience.com/wos/woscc/full-record/WOS:000123456789012"
    )
    assert uid == "WOS:000123456789012"


def test_extract_uid_none():
    assert WebOfScienceHandler._extract_uid("https://doi.org/10.1234/test") is None


def test_extract_doi():
    doi = WebOfScienceHandler._extract_doi("https://doi.org/10.1109/TPAMI.2023.123456")
    assert doi == "10.1109/TPAMI.2023.123456"


def test_extract_doi_none():
    assert WebOfScienceHandler._extract_doi("https://www.webofscience.com/WOS:000123") is None
