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
    from aria.engine.collectors.academic.base_search import BaseSearchCollector

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
        docs = [d async for d in BaseSearchCollector().collect(["neural networks"])]

    assert len(docs) == 1
    assert docs[0]["platform"] == "base_search"
    assert docs[0]["source_type"] == "academic_paper"


# ── Mastodon ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mastodon_yields_doc_via_hashtag_timeline():
    """Part A: hashtag timeline returns posts without any credentials."""
    from aria.engine.collectors.social.mastodon import MastodonCollector

    # The hashtag timeline endpoint returns a JSON *list* of status objects
    # (not a dict with a 'statuses' key like the v2 search endpoint).
    fake_timeline = [
        {
            "id": "456",
            "url": "https://fosstodon.org/@dev/456",
            "content": "<p>Exploring <strong>AI safety</strong> and alignment research in depth — these are important open problems in modern machine learning and deserve serious scientific attention from the broader research community worldwide.</p>",
            "created_at": "2024-06-01T10:00:00.000Z",
            "account": {"acct": "dev@fosstodon.org", "username": "dev"},
            "favourites_count": 7,
            "reblogs_count": 2,
        }
    ]
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = fake_timeline

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.social.mastodon.httpx.AsyncClient", return_value=mock_client):
        docs = [d async for d in MastodonCollector().collect(["AI safety"])]

    assert len(docs) >= 1
    assert docs[0]["platform"] == "mastodon"
    assert docs[0]["source_type"] == "social_media"
    assert "<p>" not in docs[0]["text"]        # HTML stripped
    assert "<strong>" not in docs[0]["text"]   # nested tags stripped too
    assert docs[0]["word_count"] > 20          # min word count threshold met


@pytest.mark.asyncio
async def test_mastodon_skips_short_content():
    """Status with <= 20 words must be skipped."""
    from aria.engine.collectors.social.mastodon import MastodonCollector

    fake_timeline = [
        {
            "id": "789",
            "url": "https://fosstodon.org/@x/789",
            "content": "<p>Short post.</p>",  # far below 20-word threshold
            "created_at": "2024-06-01T10:00:00.000Z",
            "account": {"acct": "x@fosstodon.org", "username": "x"},
            "favourites_count": 0,
            "reblogs_count": 0,
        }
    ]
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = fake_timeline

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("aria.engine.collectors.social.mastodon.httpx.AsyncClient", return_value=mock_client):
        docs = [d async for d in MastodonCollector().collect(["python"])]

    assert docs == []


@pytest.mark.asyncio
async def test_mastodon_ddg_fallback_when_hashtag_returns_nothing():
    """Part C: DuckDuckGo fallback fires when hashtag timeline returns empty list."""
    from aria.engine.collectors.social.mastodon import MastodonCollector

    # All hashtag timeline calls return empty lists
    empty_resp = MagicMock(status_code=200)
    empty_resp.json.return_value = []

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=empty_resp)

    ddg_results = [
        {
            "href": "https://mastodon.social/@researcher/99",
            "title": "Researcher on Mastodon",
            "body": "A long enough snippet about machine learning and neural networks to pass the word count filter in the fallback path.",
        }
    ]

    class _FakeDDGS:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def text(self, *_a, **_kw): return ddg_results

    with patch("aria.engine.collectors.social.mastodon.httpx.AsyncClient", return_value=mock_client):
        with patch("aria.engine.collectors.social.mastodon.DDGS", _FakeDDGS, create=True):
            # Patch both possible import paths
            import sys
            # Inject a fake ddgs module so the `from ddgs import DDGS` branch resolves
            import types
            fake_ddgs_mod = types.ModuleType("ddgs")
            fake_ddgs_mod.DDGS = _FakeDDGS  # type: ignore[attr-defined]
            old = sys.modules.get("ddgs")
            sys.modules["ddgs"] = fake_ddgs_mod
            try:
                docs = [d async for d in MastodonCollector().collect(["machine learning"])]
            finally:
                if old is None:
                    sys.modules.pop("ddgs", None)
                else:
                    sys.modules["ddgs"] = old

    assert len(docs) >= 1
    assert docs[0]["platform"] == "mastodon"
    assert docs[0]["metadata"]["via"] == "ddg_fallback"
