"""Tests for the 9 new source collectors added in the source-upgrades release."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── CrossRef ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_crossref_yields_doc():
    from aria.engine.collectors.academic.crossref import CrossRefCollector

    fake_resp = {
        "message": {
            "items": [{
                "DOI": "10.1234/test",
                "title": ["Test Paper Title"],
                "abstract": "<p>Test abstract about AI.</p>",
                "author": [{"given": "Jane", "family": "Doe"}],
                "published": {"date-parts": [[2024]]},
                "is-referenced-by-count": 42,
            }]
        }
    }
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = fake_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.academic.crossref.httpx.AsyncClient", return_value=mock_client):
        docs = [d async for d in CrossRefCollector().collect(["AI safety"])]

    assert len(docs) == 1
    assert docs[0]["source_type"] == "academic_paper"
    assert docs[0]["platform"] == "crossref"
    assert docs[0]["metadata"]["citation_count"] == 42
    # HTML tags should be stripped from abstract
    assert "<p>" not in docs[0]["text"]


# ── CORE.ac.uk ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_core_ac_yields_doc():
    from aria.engine.collectors.academic.core_ac import CoreAcCollector

    fake_resp = {
        "results": [{
            "doi": "10.5678/core",
            "title": "Core Paper",
            "abstract": "Abstract text.",
            "authors": [{"name": "Alice Smith"}],
            "yearPublished": 2023,
            "downloadUrl": "https://core.ac.uk/download/1.pdf",
        }]
    }
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = fake_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.academic.core_ac.httpx.AsyncClient", return_value=mock_client):
        docs = [d async for d in CoreAcCollector().collect(["machine learning"])]

    assert len(docs) == 1
    assert docs[0]["platform"] == "core_ac"
    assert docs[0]["source_type"] == "academic_paper"
    assert docs[0]["metadata"]["year"] == "2023"


# ── Europe PMC ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_europe_pmc_yields_doc():
    from aria.engine.collectors.academic.europe_pmc import EuropePMCCollector

    fake_resp = {
        "resultList": {
            "result": [{
                "doi": "10.9999/epmc",
                "pmcid": "PMC1234",
                "title": "PMC Paper",
                "abstractText": "Medical abstract.",
                "authorString": "Smith J, Jones A",
                "pubYear": "2024",
                "source": "MED",
                "id": "12345",
            }]
        }
    }
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = fake_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.academic.europe_pmc.httpx.AsyncClient", return_value=mock_client):
        docs = [d async for d in EuropePMCCollector().collect(["CRISPR"])]

    assert len(docs) == 1
    assert docs[0]["platform"] == "europe_pmc"
    assert docs[0]["metadata"]["pmcid"] == "PMC1234"


# ── SSRN ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ssrn_skips_gracefully_on_ddg_error():
    """SSRN collector: DDG search failure → yields nothing, no exception raised."""
    from aria.engine.collectors.academic.ssrn import SSRNCollector

    mock_resp = MagicMock(status_code=503)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.academic.ssrn.httpx.AsyncClient", return_value=mock_client):
        docs = [d async for d in SSRNCollector().collect(["fintech regulation"])]

    assert docs == []  # graceful skip — no exception raised


# ── Wikidata ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wikidata_yields_doc():
    from aria.engine.collectors.knowledge.wikidata import WikidataCollector

    fake_resp = {
        "search": [{
            "id": "Q42",
            "label": "Douglas Adams",
            "description": "English author and humourist",
            "aliases": ["D. Adams"],
        }]
    }
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = fake_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.knowledge.wikidata.httpx.AsyncClient", return_value=mock_client):
        docs = [d async for d in WikidataCollector().collect(["Douglas Adams"])]

    assert len(docs) == 1
    assert docs[0]["platform"] == "wikidata"
    assert docs[0]["source_type"] == "knowledge_base"
    assert docs[0]["metadata"]["entity_id"] == "Q42"


# ── Internet Archive ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_internet_archive_yields_doc():
    from aria.engine.collectors.data.internet_archive import InternetArchiveCollector

    fake_resp = {
        "response": {
            "docs": [{
                "identifier": "test-book-1234",
                "title": "A History of Computing",
                "description": "A comprehensive look at computing history.",
                "date": "2005",
                "mediatype": "texts",
                "creator": "John Author",
            }]
        }
    }
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = fake_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.data.internet_archive.httpx.AsyncClient", return_value=mock_client):
        docs = [d async for d in InternetArchiveCollector().collect(["computing history"])]

    assert len(docs) == 1
    assert docs[0]["platform"] == "internet_archive"
    assert docs[0]["url"] == "https://archive.org/details/test-book-1234"
    assert docs[0]["source_type"] == "document"


# ── ProPublica ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propublica_nonprofit_yields_doc():
    from aria.engine.collectors.specialized.propublica import ProPublicaCollector

    fake_resp = {
        "organizations": [{
            "ein": "123456789",
            "name": "Test Foundation",
            "city": "New York",
            "state": "NY",
            "ntee_code": "A01",
        }]
    }
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = fake_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.specialized.propublica.httpx.AsyncClient", return_value=mock_client):
        docs = [d async for d in ProPublicaCollector().collect(["education foundation"])]

    assert len(docs) >= 1
    assert docs[0]["platform"] == "propublica"
    assert docs[0]["source_type"] == "gov_policy"


# ── BASE Search ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_base_search_yields_doc():
    from aria.engine.collectors.academic.base_search import BASESearchCollector

    fake_resp = {
        "response": {
            "docs": [{
                "dcidentifier": ["https://example.com/paper"],
                "dctitle": ["BASE Academic Paper"],
                "dcdescription": ["This is the abstract of the paper."],
                "dccreator": ["Author One", "Author Two"],
                "dcyear": "2022",
                "dcsubject": ["Computer Science"],
            }]
        }
    }
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = fake_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.academic.base_search.httpx.AsyncClient", return_value=mock_client):
        docs = [d async for d in BASESearchCollector().collect(["neural networks"])]

    assert len(docs) == 1
    assert docs[0]["platform"] == "base_search"
    assert docs[0]["source_type"] == "academic_paper"


# ── Mastodon ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mastodon_yields_doc():
    from aria.engine.collectors.social.mastodon import MastodonCollector

    fake_resp = {
        "statuses": [{
            "id": "123",
            "url": "https://mastodon.social/@user/123",
            "content": "<p>Interesting post about AI safety and alignment research.</p>",
            "created_at": "2024-01-01T12:00:00.000Z",
            "account": {"acct": "researcher@mastodon.social", "username": "researcher"},
            "favourites_count": 10,
            "reblogs_count": 3,
        }]
    }
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = fake_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.social.mastodon.httpx.AsyncClient", return_value=mock_client):
        docs = [d async for d in MastodonCollector().collect(["AI safety"])]

    assert len(docs) == 1
    assert docs[0]["platform"] == "mastodon"
    assert docs[0]["source_type"] == "social_media"
    assert "<p>" not in docs[0]["text"]  # HTML stripped
