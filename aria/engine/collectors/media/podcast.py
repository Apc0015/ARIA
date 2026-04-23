"""Podcast collector — RSS feeds with optional Whisper transcription."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import html as html_module
import tempfile
from datetime import datetime, timezone
from typing import AsyncGenerator, Any, Optional

from .base import BaseCollector

logger = logging.getLogger("aria")

# Default tech/research podcast feeds
_DEFAULT_FEEDS: list[str] = [
    "https://feeds.simplecast.com/54nAGcIl",  # Lex Fridman
    "https://lexfridman.com/feed/podcast/",
    "https://rss.art19.com/lex-fridman-podcast",
    "https://changelog.com/podcast.rss",
    "https://feeds.feedburner.com/se-radio",
    "https://softwareengineeringdaily.com/feed/podcast/",
    "https://feeds.megaphone.fm/MLN2155636147",  # Machine Learning Street Talk
    "https://twimlai.com/feed/",
    "https://feeds.buzzsprout.com/1462672.rss",  # Practical AI
    "https://anchor.fm/s/5b7d4ba0/podcast/rss",  # AI in Business
]

# Max audio download size (200 MB) to avoid runaway downloads
_MAX_AUDIO_BYTES = 200 * 1024 * 1024


class PodcastCollector(BaseCollector):
    """Collects podcast episodes from RSS feeds.

    Default mode: returns episode titles and descriptions as documents.

    Transcription mode (PODCAST_TRANSCRIBE=true):
    - Downloads each episode's audio file
    - Transcribes it using openai-whisper (loaded once per instance)
    - Returns full transcript as document text instead of description
    - Model size configurable via WHISPER_MODEL env var (default: base)
      Options: tiny, base, small, medium, large (larger = slower, more accurate)

    Note: Transcription is CPU-intensive. base model ~5x real-time on CPU.
    """

    def __init__(
        self,
        feed_urls: list[str] | None = None,
        max_results: int = 10,
    ) -> None:
        self._feed_urls = feed_urls if feed_urls is not None else _DEFAULT_FEEDS
        self._max_results = max_results
        self._transcribe = os.getenv("PODCAST_TRANSCRIBE", "").lower() in ("1", "true", "yes")
        self._whisper_model_name = os.getenv("WHISPER_MODEL", "base")
        self._whisper_model: Optional[Any] = None  # lazy-loaded

    async def validate(self) -> bool:
        try:
            import feedparser  # noqa: F401
        except ImportError:
            logger.warning("PodcastCollector: feedparser not installed")
            return False

        if self._transcribe:
            try:
                import whisper  # noqa: F401
            except ImportError:
                logger.warning(
                    "PodcastCollector: PODCAST_TRANSCRIBE=true but openai-whisper not installed. "
                    "Install with: pip install openai-whisper"
                )
                self._transcribe = False  # degrade gracefully

        return True

    def _load_whisper(self) -> Any:
        """Load Whisper model once and cache on instance."""
        if self._whisper_model is None:
            import whisper
            logger.info(
                "PodcastCollector: loading Whisper model '%s' (first use)",
                self._whisper_model_name,
            )
            self._whisper_model = whisper.load_model(self._whisper_model_name)
        return self._whisper_model

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Parse podcast feeds and yield matching episode documents.

        Args:
            queries: Search query strings used for relevance filtering.

        Yields:
            Document dicts with platform='podcast', source_type='video_transcript'.
        """
        import feedparser

        query_tokens = {t.lower() for q in queries for t in q.split() if len(t) > 2}
        count = 0
        seen_urls: set[str] = set()

        for feed_url in self._feed_urls:
            if count >= self._max_results:
                break
            try:
                feed = await asyncio.get_event_loop().run_in_executor(
                    None, lambda u=feed_url: feedparser.parse(u)
                )

                podcast_title = ""
                if hasattr(feed, "feed"):
                    podcast_title = feed.feed.get("title", "")

                for entry in feed.get("entries", []):
                    if count >= self._max_results:
                        break

                    entry_url = entry.get("link", "") or entry.get("id", "")
                    if not entry_url or entry_url in seen_urls:
                        continue

                    title = entry.get("title", "")
                    summary = entry.get("summary", "") or entry.get("itunes_summary", "")
                    if not summary and entry.get("content"):
                        summary = entry["content"][0].get("value", "")

                    base_text = _strip_html(f"{title}\n\n{summary}".strip())
                    if len(base_text) < 20:
                        continue

                    # Relevance filter on base text
                    if query_tokens:
                        text_lower = base_text.lower()
                        if not any(t in text_lower for t in query_tokens):
                            continue

                    seen_urls.add(entry_url)
                    published = entry.get("published", "") or entry.get("updated", "")
                    duration = entry.get("itunes_duration", "")
                    author = entry.get("author", "")

                    # Find audio enclosure
                    audio_url = ""
                    for enc in entry.get("enclosures", []):
                        if "audio" in enc.get("type", ""):
                            audio_url = enc.get("href", "")
                            break

                    # Attempt transcription if enabled and audio URL is available
                    transcript = None
                    transcribed = False
                    if self._transcribe and audio_url:
                        transcript = await self._transcribe_episode(
                            audio_url=audio_url,
                            title=title,
                        )
                        if transcript:
                            transcribed = True

                    final_text = transcript if transcribed else base_text

                    yield {
                        "url": entry_url,
                        "title": title,
                        "text": final_text,
                        "source_type": "video_transcript",
                        "platform": "podcast",
                        "language": "en",
                        "word_count": len(final_text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "podcast_title": podcast_title,
                            "feed_url": feed_url,
                            "published": published,
                            "duration": duration,
                            "audio_url": audio_url,
                            "author": author,
                            "transcribed": transcribed,
                            "whisper_model": self._whisper_model_name if transcribed else None,
                        },
                    }
                    count += 1

                await asyncio.sleep(0.3)

            except Exception as exc:
                logger.warning(
                    "PodcastCollector: error fetching feed '%s': %s", feed_url, exc
                )

    async def _transcribe_episode(self, audio_url: str, title: str) -> Optional[str]:
        """Download audio and transcribe with Whisper.

        Args:
            audio_url: Direct URL to the audio file.
            title: Episode title (for logging).

        Returns:
            Transcript text, or None if download/transcription fails.
        """
        import httpx

        logger.info("PodcastCollector: transcribing '%s'", title[:60])

        tmp_path: Optional[str] = None
        try:
            # Download audio to temp file
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                async with client.stream("GET", audio_url) as resp:
                    if resp.status_code != 200:
                        logger.debug(
                            "PodcastCollector: audio download failed (HTTP %s) for '%s'",
                            resp.status_code,
                            title[:60],
                        )
                        return None

                    content_type = resp.headers.get("content-type", "")
                    if "audio" not in content_type and "octet-stream" not in content_type:
                        logger.debug(
                            "PodcastCollector: unexpected content-type '%s' for '%s'",
                            content_type,
                            title[:60],
                        )

                    # Determine file extension from URL
                    ext = ".mp3"
                    for candidate in (".mp3", ".m4a", ".ogg", ".wav", ".opus"):
                        if candidate in audio_url.lower():
                            ext = candidate
                            break

                    with tempfile.NamedTemporaryFile(
                        suffix=ext, delete=False
                    ) as tmp_file:
                        tmp_path = tmp_file.name
                        downloaded = 0
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            downloaded += len(chunk)
                            if downloaded > _MAX_AUDIO_BYTES:
                                logger.info(
                                    "PodcastCollector: audio too large (>50MB), truncating '%s'",
                                    title[:60],
                                )
                                tmp_file.write(chunk)
                                break
                            tmp_file.write(chunk)

            if not tmp_path:
                return None

            # Transcribe in thread pool to avoid blocking the event loop
            model = self._load_whisper()
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: model.transcribe(tmp_path, language="en", fp16=False),
            )
            transcript = result.get("text", "").strip()

            if transcript:
                logger.info(
                    "PodcastCollector: transcribed '%s' (%d words)",
                    title[:60],
                    len(transcript.split()),
                )
                return transcript
            return None

        except Exception as exc:
            logger.warning(
                "PodcastCollector: transcription failed for '%s': %s", title[:60], exc
            )
            return None
        finally:
            # Clean up temp file
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


def _strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_module.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
