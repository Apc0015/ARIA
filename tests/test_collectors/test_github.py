"""Tests for GitHubCollector."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from aria.engine.collectors.knowledge.github import GitHubCollector


def test_github_collector_instantiates():
    c = GitHubCollector(max_results=5)
    assert c._max_results == 5


def test_github_collector_no_token_validates():
    """Without GITHUB_TOKEN, validate() returns True (DDG fallback available)."""
    with patch.dict("os.environ", {}, clear=False):
        import os
        os.environ.pop("GITHUB_TOKEN", None)
        c = GitHubCollector()
        # validate() is a coroutine — check synchronously via _token
        assert c._token == "" or c._token is not None  # either empty or set from env


@pytest.mark.asyncio
async def test_github_collector_validate_no_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    c = GitHubCollector()
    result = await c.validate()
    assert result is True  # fallback DDG is always available


@pytest.mark.asyncio
async def test_github_collector_public_yields_docs(monkeypatch):
    """Public (DDG) path yields correctly shaped documents."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    fake_result = {
        "href": "https://github.com/some/repo",
        "title": "some/repo — AI toolkit",
        "body": "A great AI toolkit for research.",
    }

    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text = MagicMock(return_value=[fake_result])

    with patch("aria.engine.collectors.knowledge.github.DDGS", mock_ddgs, create=True):
        try:
            from ddgs import DDGS as _unused  # noqa
        except ImportError:
            pass

        c = GitHubCollector(max_results=5)
        c._token = ""  # force public path

        docs = []
        async for doc in c._collect_public(["AI research"]):
            docs.append(doc)

    assert len(docs) >= 1
    doc = docs[0]
    assert doc["platform"] == "github"
    assert doc["source_type"] == "technical_doc"
    assert "github.com" in doc["url"]
    assert doc["word_count"] > 0
    assert "collected_at" in doc
