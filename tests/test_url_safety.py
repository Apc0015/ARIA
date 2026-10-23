import asyncio

import httpx
import pytest

from aria.utils.url import (
    UnsafeDestinationError,
    ensure_public_http_request,
    is_safe_public_http_destination,
    is_safe_public_http_url,
)


def test_public_http_url_safety_allows_public_hosts():
    assert is_safe_public_http_url("https://example.com/research")
    assert is_safe_public_http_url("http://8.8.8.8/dns")


def test_public_http_url_safety_blocks_internal_and_invalid_targets():
    blocked = [
        "http://127.0.0.1:8765/api/health",
        "http://10.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://localhost:3000/",
        "https://internal.local/",
        "file:///etc/passwd",
        "https://user:password@example.com/private",
    ]
    assert all(not is_safe_public_http_url(url) for url in blocked)


def test_hostname_resolution_rejects_private_network_answers(monkeypatch):
    class PrivateLoop:
        async def getaddrinfo(self, *_args, **_kwargs):
            return [(2, 1, 6, "", ("10.0.0.8", 0))]

    monkeypatch.setattr(asyncio, "get_running_loop", lambda: PrivateLoop())
    assert not asyncio.run(is_safe_public_http_destination("https://research.example/"))


def test_request_hook_blocks_redirect_to_private_address():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "8.8.8.8":
            return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})
        return httpx.Response(200, text="metadata")

    async def fetch() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
            event_hooks={"request": [ensure_public_http_request]},
        ) as client:
            await client.get("http://8.8.8.8/paper")

    with pytest.raises(UnsafeDestinationError):
        asyncio.run(fetch())
