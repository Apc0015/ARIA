"""YouTube collector using yt-dlp for search and transcript extraction."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Any, Optional

from .base import BaseCollector

logger = logging.getLogger("aria")


class YouTubeCollector(BaseCollector):
    """Searches YouTube and extracts auto-captions / transcripts via yt-dlp."""

    def __init__(
        self,
        max_results: int = 10,
        max_duration_seconds: int = 3600,
        timeout: int = 30,
    ) -> None:
        self._max_results = max_results
        self._max_duration = max_duration_seconds
        self._timeout = timeout

    async def validate(self) -> bool:
        try:
            import yt_dlp  # noqa: F401
            return True
        except ImportError:
            logger.warning("YouTubeCollector: yt-dlp not installed")
            return False

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Search YouTube and yield video transcript documents.

        Args:
            queries: Search queries.

        Yields:
            Document dicts with source_type='video_transcript', platform='youtube'.
        """
        seen_ids: set[str] = set()

        for query in queries:
            try:
                videos = await self._search_youtube(query)
                for video_info in videos:
                    vid_id = video_info.get("id", "")
                    if vid_id in seen_ids:
                        continue
                    seen_ids.add(vid_id)

                    doc = await self._build_doc(video_info, query)
                    if doc:
                        yield doc
                    await asyncio.sleep(0.3)
            except Exception as exc:
                logger.warning("YouTubeCollector: error for query '%s': %s", query, exc)

    async def _search_youtube(self, query: str) -> list[dict]:
        """Use yt-dlp to search YouTube."""
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "noplaylist": True,
        }

        search_url = f"ytsearch{self._max_results}:{query}"

        loop = asyncio.get_event_loop()
        try:
            info = await loop.run_in_executor(
                None,
                lambda: _ydl_extract(search_url, ydl_opts),
            )
            if not info:
                return []
            entries = info.get("entries", [])
            return [e for e in entries if e] if entries else []
        except Exception as exc:
            logger.debug("YouTubeCollector: search failed for '%s': %s", query, exc)
            return []

    async def _build_doc(self, video_info: dict, query: str) -> Optional[dict[str, Any]]:
        """Fetch transcript and build a document for a video."""
        vid_id = video_info.get("id", "")
        if not vid_id:
            return None

        url = f"https://www.youtube.com/watch?v={vid_id}"
        title = video_info.get("title", "") or ""
        duration = video_info.get("duration") or 0

        if duration and duration > self._max_duration:
            logger.debug("YouTubeCollector: skipping long video (%ds): %s", duration, title)
            return None

        # Try to get transcript
        transcript = await self._get_transcript(url, vid_id)

        # If no transcript, use description + title as text
        if not transcript:
            description = video_info.get("description") or ""
            transcript = description

        if not transcript or len(transcript.strip()) < 50:
            return None

        uploader = video_info.get("uploader", "") or video_info.get("channel", "")
        upload_date = video_info.get("upload_date", "")
        if upload_date and len(upload_date) == 8:
            upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

        return {
            "url": url,
            "title": title,
            "text": transcript,
            "source_type": "video_transcript",
            "platform": "youtube",
            "language": "en",
            "word_count": len(transcript.split()),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "query": query,
                "video_id": vid_id,
                "channel": uploader,
                "duration_seconds": duration,
                "upload_date": upload_date,
                "view_count": video_info.get("view_count"),
                "thumbnail": video_info.get("thumbnail", ""),
            },
        }

    async def _get_transcript(self, url: str, vid_id: str) -> Optional[str]:
        """Attempt to extract auto-captions via yt-dlp."""
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "writeautomaticsub": True,
            "subtitlesformat": "json3",
            "subtitleslangs": ["en", "en-US", "en-GB"],
        }

        loop = asyncio.get_event_loop()
        try:
            info = await loop.run_in_executor(
                None,
                lambda: _ydl_extract(url, ydl_opts),
            )
            if not info:
                return None

            # Try automatic captions first
            auto_captions = info.get("automatic_captions", {})
            captions = info.get("subtitles", {})

            for lang in ["en", "en-US", "en-GB"]:
                tracks = auto_captions.get(lang) or captions.get(lang)
                if tracks:
                    text = _extract_caption_text(tracks)
                    if text:
                        return text

            return None
        except Exception as exc:
            logger.debug("YouTubeCollector: transcript fetch failed for %s: %s", vid_id, exc)
            return None


def _ydl_extract(url: str, opts: dict) -> Optional[dict]:
    """Run yt-dlp extract_info synchronously."""
    import yt_dlp
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:
        logger.debug("yt-dlp extract failed for %s: %s", url, exc)
        return None


def _extract_caption_text(tracks: list) -> Optional[str]:
    """Extract plain text from caption track data."""
    if not tracks:
        return None

    # Prefer json3 format
    for track in tracks:
        fmt = track.get("ext", "")
        if fmt == "json3":
            data = track.get("data")
            if data:
                return _parse_json3_captions(data)

    # Fallback: use url if available (vtt/srv3)
    for track in tracks:
        url = track.get("url")
        if url:
            try:
                import urllib.request
                with urllib.request.urlopen(url, timeout=10) as resp:
                    content = resp.read().decode("utf-8", errors="replace")
                return _parse_vtt_text(content)
            except Exception:
                pass

    return None


def _parse_json3_captions(data: Any) -> str:
    """Parse json3 caption format to plain text."""
    if isinstance(data, str):
        import json
        try:
            data = json.loads(data)
        except Exception:
            return data

    parts = []
    events = data.get("events", []) if isinstance(data, dict) else []
    for event in events:
        segs = event.get("segs", [])
        for seg in segs:
            utf8 = seg.get("utf8", "")
            if utf8 and utf8 != "\n":
                parts.append(utf8)

    return " ".join(parts).strip()


def _parse_vtt_text(vtt_content: str) -> str:
    """Extract plain text from WebVTT content."""
    import re
    lines = vtt_content.split("\n")
    text_parts = []
    for line in lines:
        line = line.strip()
        # Skip timing lines, WEBVTT header, NOTE lines
        if not line or line.startswith("WEBVTT") or "-->" in line or line.startswith("NOTE"):
            continue
        if re.match(r"^\d+$", line):
            continue
        # Strip HTML tags
        clean = re.sub(r"<[^>]+>", "", line)
        if clean:
            text_parts.append(clean)
    return " ".join(text_parts).strip()
