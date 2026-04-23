"""Robots.txt compliance helpers."""

from __future__ import annotations

from urllib.parse import urlparse
import urllib.robotparser


def is_allowed(user_agent: str, url: str) -> bool:
    """Return whether robots.txt permits fetching the URL."""

    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception:
        return True
    return parser.can_fetch(user_agent, url)
