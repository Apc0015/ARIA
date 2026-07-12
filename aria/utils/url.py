"""URL normalization helpers."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "igshid",
    "mc_cid",
    "mc_eid",
}


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication and comparison."""
    if not url:
        return ""

    raw = url.strip()
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw

    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower() if parsed.hostname else parsed.netloc.lower()

    # Preserve non-default ports.
    if parsed.port:
        default_port = 443 if scheme == "https" else 80
        if parsed.port != default_port:
            host = f"{host}:{parsed.port}"

    path = parsed.path or ""
    if path != "/":
        path = path.rstrip("/")

    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k and k not in _TRACKING_PARAMS
    ]
    query = urlencode(sorted(query_pairs)) if query_pairs else ""

    return urlunparse((scheme, host, path, "", query, ""))


def get_url_domain(url: str) -> str:
    """Return the normalized hostname for a URL."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    return parsed.hostname.lower() if parsed.hostname else ""
