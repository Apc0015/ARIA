"""Tests for PodcastCollector."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from aria.engine.collectors.media.podcast import PodcastCollector, _strip_html


def test_podcast_collector_instantiates():
    c = PodcastCollector(max_results=5)
    assert c._max_results == 5
    assert isinstance(c._feed_urls, list)
    assert len(c._feed_urls) > 0


def test_podcast_transcribe_default_off(monkeypatch):
    monkeypatch.delenv("PODCAST_TRANSCRIBE", raising=False)
    c = PodcastCollector()
    assert c._transcribe is False


def test_podcast_transcribe_env_var_on(monkeypatch):
    monkeypatch.setenv("PODCAST_TRANSCRIBE", "true")
    monkeypatch.setattr(
        "aria.engine.collectors.media.podcast.PodcastCollector.__init__",
        lambda self, **kw: None,
    )
    import os
    assert os.getenv("PODCAST_TRANSCRIBE") == "true"


def test_strip_html():
    assert _strip_html("<p>Hello <b>world</b>!</p>") == "Hello world !"
    assert _strip_html("&amp; &lt;b&gt;") == "& <b>"
    assert _strip_html("  lots   of   spaces  ") == "lots of spaces"


@pytest.mark.asyncio
async def test_podcast_validate_with_feedparser():
    try:
        import feedparser  # noqa
    except ImportError:
        pytest.skip("feedparser not installed")
    c = PodcastCollector()
    assert await c.validate() is True


@pytest.mark.asyncio
async def test_podcast_collect_yields_docs():
    """collect() yields metadata docs when transcription is off."""
    fake_entry = {
        "link": "https://example-podcast.com/episode/1",
        "title": "AI in Healthcare",
        "summary": "Discussion on machine learning applications in medical diagnosis.",
        "published": "Mon, 15 Jan 2024 10:00:00 +0000",
        "itunes_duration": "3600",
        "enclosures": [{"type": "audio/mpeg", "href": "https://example.com/ep1.mp3"}],
        "author": "Dr. Smith",
    }
    fake_feed = MagicMock()
    fake_feed.feed = MagicMock()
    fake_feed.feed.get = MagicMock(return_value="Tech Research Podcast")
    fake_feed.get = MagicMock(return_value=[fake_entry])

    with patch("aria.engine.collectors.media.podcast.asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=fake_feed)

        c = PodcastCollector(
            feed_urls=["https://example-podcast.com/rss"],
            max_results=5,
        )
        c._transcribe = False

        docs = []
        async for doc in c.collect(["AI healthcare machine learning"]):
            docs.append(doc)

    assert len(docs) == 1
    doc = docs[0]
    assert doc["platform"] == "podcast"
    assert doc["source_type"] == "video_transcript"
    assert doc["metadata"]["transcribed"] is False
    assert doc["metadata"]["audio_url"] == "https://example.com/ep1.mp3"
    assert "AI in Healthcare" in doc["text"]


@pytest.mark.asyncio
async def test_podcast_collect_relevance_filter():
    """Episodes not matching query tokens are filtered out."""
    fake_entry = {
        "link": "https://example-podcast.com/episode/2",
        "title": "Cooking with Spices",
        "summary": "A deep dive into world cuisines and spice blends.",
        "published": "",
        "itunes_duration": "1800",
        "enclosures": [],
        "author": "Chef Bob",
    }
    fake_feed = MagicMock()
    fake_feed.feed = MagicMock()
    fake_feed.feed.get = MagicMock(return_value="Food Podcast")
    fake_feed.get = MagicMock(return_value=[fake_entry])

    with patch("aria.engine.collectors.media.podcast.asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=fake_feed)

        c = PodcastCollector(
            feed_urls=["https://example-podcast.com/rss"],
            max_results=5,
        )
        c._transcribe = False

        # Query is about AI, episode is about cooking — should be filtered
        docs = []
        async for doc in c.collect(["artificial intelligence neural networks"]):
            docs.append(doc)

    assert docs == []
