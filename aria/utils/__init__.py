"""Shared ARIA utilities."""

from aria.utils.logger import configure_logging
from aria.utils.url import normalize_url, get_url_domain

__all__ = ["configure_logging", "normalize_url", "get_url_domain"]
