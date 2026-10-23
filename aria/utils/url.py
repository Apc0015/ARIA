"""URL normalization helpers."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
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


def is_safe_public_http_url(url: str) -> bool:
    """Return whether a URL is safe for a server-side public web request.

    Collectors handle URLs discovered from external services and documents.
    This rejects local/private literal addresses and local hostnames before a
    request can reach deployment metadata services or the private network.
    """
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False
        host = parsed.hostname.rstrip(".").lower()
        if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
            return False
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return True
        return address.is_global
    except (TypeError, ValueError):
        return False


async def is_safe_public_http_destination(url: str) -> bool:
    """Also verify that a hostname resolves exclusively to public addresses."""
    if not is_safe_public_http_url(url):
        return False
    host = urlparse(url.strip()).hostname
    if not host:
        return False
    try:
        # Literal IPs were already checked above. Resolve hostnames before the
        # collector hands them to an HTTP client, rejecting any private answer.
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    try:
        records = await asyncio.get_running_loop().getaddrinfo(
            host, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
        )
    except OSError:
        return False
    addresses = {record[4][0] for record in records}
    if not addresses:
        return False
    try:
        return all(ipaddress.ip_address(address).is_global for address in addresses)
    except ValueError:
        return False
