"""Media and multimedia sources (video, podcast, etc.)."""
from aria.engine.collectors.media.youtube import YouTubeCollector
from aria.engine.collectors.media.podcast import PodcastCollector
from aria.engine.collectors.media.vimeo import VimeoCollector
__all__ = ["YouTubeCollector","PodcastCollector","VimeoCollector"]
