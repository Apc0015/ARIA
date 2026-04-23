"""Tests for SourceRegistry and BaseCollector."""

from __future__ import annotations

from typing import Any, AsyncGenerator

import pytest

from aria.sources.base import BaseCollector, CollectorConfig
from aria.sources.registry import SourceRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _MockCollector(BaseCollector):
    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        for q in queries:
            yield {"url": f"https://mock.com/{q}", "title": q, "text": "mock"}


@pytest.fixture(autouse=True)
def reset_registry():
    """Each test gets a clean registry."""
    original = dict(SourceRegistry._collectors)
    yield
    SourceRegistry._collectors.clear()
    SourceRegistry._collectors.update(original)


# ---------------------------------------------------------------------------
# CollectorConfig
# ---------------------------------------------------------------------------

def test_collector_config_defaults():
    cfg = CollectorConfig(name="test")
    assert cfg.enabled is True
    assert cfg.timeout == 30
    assert cfg.max_results == 100
    assert cfg.rate_limit is None
    assert cfg.extra is None


def test_collector_config_custom():
    cfg = CollectorConfig(name="web", enabled=False, timeout=60, max_results=50)
    assert cfg.enabled is False
    assert cfg.timeout == 60


# ---------------------------------------------------------------------------
# BaseCollector
# ---------------------------------------------------------------------------

def test_base_collector_name_from_config():
    cfg = CollectorConfig(name="my_collector")
    collector = _MockCollector(cfg)
    assert collector.name == "my_collector"


def test_base_collector_repr():
    cfg = CollectorConfig(name="my_collector", enabled=True)
    collector = _MockCollector(cfg)
    assert "my_collector" in repr(collector)
    assert "True" in repr(collector)


@pytest.mark.asyncio
async def test_base_collector_validate_returns_true():
    cfg = CollectorConfig(name="test")
    collector = _MockCollector(cfg)
    assert await collector.validate() is True


@pytest.mark.asyncio
async def test_mock_collector_yields_docs():
    cfg = CollectorConfig(name="mock")
    collector = _MockCollector(cfg)
    docs = []
    async for doc in collector.collect(["query1", "query2"]):
        docs.append(doc)
    assert len(docs) == 2
    assert docs[0]["url"] == "https://mock.com/query1"


# ---------------------------------------------------------------------------
# SourceRegistry
# ---------------------------------------------------------------------------

def test_registry_is_singleton():
    r1 = SourceRegistry()
    r2 = SourceRegistry()
    assert r1 is r2


def test_register_and_list():
    SourceRegistry.register("mock_source", _MockCollector)
    assert "mock_source" in SourceRegistry.list_sources()


def test_get_registered_collector():
    SourceRegistry.register("mock_source", _MockCollector)
    cfg = CollectorConfig(name="mock_source")
    collector = SourceRegistry.get("mock_source", cfg)
    assert isinstance(collector, _MockCollector)


def test_get_unregistered_raises_value_error():
    with pytest.raises(ValueError, match="Unknown source type"):
        SourceRegistry.get("nonexistent_source", CollectorConfig(name="x"))


def test_list_sources_sorted():
    SourceRegistry.register("zzz_source", _MockCollector)
    SourceRegistry.register("aaa_source", _MockCollector)
    sources = SourceRegistry.list_sources()
    assert sources == sorted(sources)


def test_list_by_category():
    SourceRegistry.register("web_search", _MockCollector)
    SourceRegistry.register("web_reddit", _MockCollector)
    SourceRegistry.register("academic_arxiv", _MockCollector)
    web_sources = SourceRegistry.list_by_category("web")
    assert "web_search" in web_sources
    assert "web_reddit" in web_sources
    assert "academic_arxiv" not in web_sources


def test_register_overwrites_existing():
    class _OtherCollector(BaseCollector):
        async def collect(self, queries):
            yield {}

    SourceRegistry.register("dup_source", _MockCollector)
    SourceRegistry.register("dup_source", _OtherCollector)
    cfg = CollectorConfig(name="dup_source")
    collector = SourceRegistry.get("dup_source", cfg)
    assert isinstance(collector, _OtherCollector)
