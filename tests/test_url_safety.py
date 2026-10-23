import asyncio

from aria.utils.url import is_safe_public_http_destination, is_safe_public_http_url


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
