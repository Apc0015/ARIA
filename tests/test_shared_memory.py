"""Tests for aria.engine.memory.shared_memory.SharedMemory."""

from __future__ import annotations

import pytest

from aria.engine.memory.shared_memory import SharedMemory


def test_add_url_first_time_returns_true():
    mem = SharedMemory()
    assert mem.add_url("https://example.com/page1") is True


def test_add_url_duplicate_returns_false():
    mem = SharedMemory()
    mem.add_url("https://example.com/page1")
    assert mem.add_url("https://example.com/page1") is False


def test_add_url_case_insensitive():
    mem = SharedMemory()
    mem.add_url("https://Example.COM/Page")
    assert mem.add_url("https://example.com/page") is False


def test_add_url_strips_whitespace():
    mem = SharedMemory()
    mem.add_url("  https://example.com/a  ")
    assert mem.add_url("https://example.com/a") is False


def test_add_different_urls():
    mem = SharedMemory()
    assert mem.add_url("https://site1.com") is True
    assert mem.add_url("https://site2.com") is True


def test_add_fingerprint_first_time_returns_true():
    mem = SharedMemory()
    assert mem.add_fingerprint("abc123hash") is True


def test_add_fingerprint_duplicate_returns_false():
    mem = SharedMemory()
    mem.add_fingerprint("abc123hash")
    assert mem.add_fingerprint("abc123hash") is False


def test_add_different_fingerprints():
    mem = SharedMemory()
    assert mem.add_fingerprint("fp1") is True
    assert mem.add_fingerprint("fp2") is True


def test_set_and_get():
    mem = SharedMemory()
    mem.set("key1", "value1")
    assert mem.get("key1") == "value1"


def test_get_missing_key_returns_default():
    mem = SharedMemory()
    assert mem.get("nonexistent") is None
    assert mem.get("nonexistent", "fallback") == "fallback"


def test_clear_resets_urls():
    mem = SharedMemory()
    mem.add_url("https://example.com")
    mem.clear()
    assert mem.add_url("https://example.com") is True


def test_clear_resets_fingerprints():
    mem = SharedMemory()
    mem.add_fingerprint("fp1")
    mem.clear()
    assert mem.add_fingerprint("fp1") is True


def test_clear_resets_store():
    mem = SharedMemory()
    mem.set("k", "v")
    mem.clear()
    assert mem.get("k") is None


def test_dict_backend_by_default():
    mem = SharedMemory(backend="dict")
    assert mem._redis is None


def test_redis_backend_falls_back_to_dict_when_unavailable():
    mem = SharedMemory(backend="redis", redis_url="redis://nonexistent:6379/0")
    assert mem._backend == "dict"
    assert mem._redis is None
    assert mem.add_url("https://example.com") is True
