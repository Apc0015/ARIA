"""Tests for MeshAggregator — deduplication of parallel collector results."""

from __future__ import annotations

import pytest

from aria.engine.memory.shared_memory import SharedMemory
from aria.engine.orchestrator.core import MeshAggregator


def _mem():
    return SharedMemory()


@pytest.mark.asyncio
async def test_aggregate_empty_batches():
    agg = MeshAggregator(_mem())
    result = await agg.aggregate([])
    assert result == []


@pytest.mark.asyncio
async def test_aggregate_single_batch():
    doc = {"url": "https://example.com/a", "text": "Some text content here", "title": "A"}
    agg = MeshAggregator(_mem())
    result = await agg.aggregate([[doc]])
    assert len(result) == 1
    assert result[0]["url"] == "https://example.com/a"


@pytest.mark.asyncio
async def test_aggregate_deduplicates_by_url():
    doc1 = {"url": "https://example.com/dup", "text": "content one", "title": "A"}
    doc2 = {"url": "https://example.com/dup", "text": "content two", "title": "B"}
    agg = MeshAggregator(_mem())
    result = await agg.aggregate([[doc1], [doc2]])
    assert len(result) == 1
    assert result[0]["url"] == "https://example.com/dup"


@pytest.mark.asyncio
async def test_aggregate_deduplicates_by_content_fingerprint():
    text = "identical content " * 10
    doc1 = {"url": "https://site1.com", "text": text, "title": "A"}
    doc2 = {"url": "https://site2.com", "text": text, "title": "B"}
    agg = MeshAggregator(_mem())
    result = await agg.aggregate([[doc1], [doc2]])
    assert len(result) == 1


@pytest.mark.asyncio
async def test_aggregate_skips_known_urls():
    doc = {"url": "https://known.com/doc", "text": "content", "title": "Known"}
    known_urls = {"https://known.com/doc"}
    agg = MeshAggregator(_mem(), known_urls=known_urls)
    result = await agg.aggregate([[doc]])
    assert result == []


@pytest.mark.asyncio
async def test_aggregate_allows_unknown_urls():
    known_urls = {"https://other.com/doc"}
    doc = {"url": "https://new.com/doc", "text": "new content", "title": "New"}
    agg = MeshAggregator(_mem(), known_urls=known_urls)
    result = await agg.aggregate([[doc]])
    assert len(result) == 1


@pytest.mark.asyncio
async def test_aggregate_no_url_dedup_by_fingerprint_only():
    text = "short text"
    doc1 = {"url": "", "text": text, "title": "A"}
    doc2 = {"url": "", "text": text, "title": "B"}
    agg = MeshAggregator(_mem())
    result = await agg.aggregate([[doc1], [doc2]])
    # short text (len <= 50) skips fingerprint dedup, no url = no url dedup → both pass
    assert len(result) == 2


@pytest.mark.asyncio
async def test_aggregate_short_text_not_fingerprinted():
    doc1 = {"url": "", "text": "hi", "title": "A"}
    doc2 = {"url": "", "text": "hi", "title": "B"}
    agg = MeshAggregator(_mem())
    result = await agg.aggregate([[doc1], [doc2]])
    assert len(result) == 2


@pytest.mark.asyncio
async def test_aggregate_empty_batches_skipped():
    doc = {"url": "https://example.com/z", "text": "ok", "title": "Z"}
    agg = MeshAggregator(_mem())
    result = await agg.aggregate([[], [doc], []])
    assert len(result) == 1


@pytest.mark.asyncio
async def test_aggregate_preserves_doc_fields():
    doc = {
        "url": "https://example.com/x",
        "title": "Title",
        "text": "Content here with enough length for sure",
        "platform": "web",
        "source_type": "news_article",
    }
    agg = MeshAggregator(_mem())
    result = await agg.aggregate([[doc]])
    assert result[0]["platform"] == "web"
    assert result[0]["source_type"] == "news_article"
