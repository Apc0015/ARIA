"""Robots.txt compliance helpers.

``allowed_async`` is the collector-facing entry point: cached per host,
non-blocking, fail-open (an unreachable robots.txt never stops research),
and opt-out via ``ARIA_RESPECT_ROBOTS=false``.
"""

from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import urlparse
import urllib.robotparser

logger = logging.getLogger("aria")

_DEFAULT_USER_AGENT = "ARIA-Research-Collector"

# origin → parser (None means robots.txt unreachable → allow everything)
_parser_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_cache_lock: asyncio.Lock | None = None


def _respect_robots() -> bool:
    return os.environ.get("ARIA_RESPECT_ROBOTS", "true").lower() not in (
        "false", "0", "no",
    )


def is_allowed(user_agent: str, url: str) -> bool:
    """Return whether robots.txt permits fetching the URL (synchronous)."""

    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception:
        return True
    return parser.can_fetch(user_agent, url)


def _read_parser(origin: str) -> urllib.robotparser.RobotFileParser | None:
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(f"{origin}/robots.txt")
    try:
        parser.read()
        return parser
    except Exception:
        return None  # unreachable → treat as allow-all


async def allowed_async(url: str, user_agent: str = _DEFAULT_USER_AGENT) -> bool:
    """Async, cached robots.txt check used by web collectors.

    Fail-open: network errors, missing robots.txt, or a disabled
    ARIA_RESPECT_ROBOTS flag all return True.
    """
    if not _respect_robots():
        return True

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return True
    origin = f"{parsed.scheme}://{parsed.netloc}"

    global _cache_lock
    if _cache_lock is None:
        _cache_lock = asyncio.Lock()

    if origin not in _parser_cache:
        async with _cache_lock:
            if origin not in _parser_cache:  # re-check after await
                _parser_cache[origin] = await asyncio.to_thread(_read_parser, origin)

    parser = _parser_cache.get(origin)
    if parser is None:
        return True
    try:
        allowed = parser.can_fetch(user_agent, url)
    except Exception:
        return True
    if not allowed:
        logger.info("robots.txt disallows %s — skipping", url)
    return allowed
