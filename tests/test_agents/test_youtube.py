from __future__ import annotations

from aria.engine.collectors.media.youtube import YouTubeCollector as YouTubeAgent


def test_youtube_agent_alias_exists():
    assert YouTubeAgent is not None
