"""Tests for new agent wrappers — GitHub, Government, Multilingual, News."""

from __future__ import annotations

import pytest


def test_github_agent_imports_real_collector():
    from aria.engine.collectors.knowledge.github import GitHubCollector as GitHubAgent
    from aria.engine.collectors.knowledge.github import GitHubCollector
    assert GitHubAgent is GitHubCollector


def test_government_agent_imports_real_collector():
    from aria.engine.collectors.specialized.government import GovernmentCollector as GovernmentAgent
    from aria.engine.collectors.specialized.government import GovernmentCollector
    assert GovernmentAgent is GovernmentCollector


def test_multilingual_agent_imports_real_collector():
    from aria.engine.collectors.specialized.multilingual import MultilingualCollector as MultilingualAgent
    from aria.engine.collectors.specialized.multilingual import MultilingualCollector
    assert MultilingualAgent is MultilingualCollector


def test_news_agent_imports_real_collector():
    from aria.engine.collectors.specialized.news import NewsCollector as NewsAgent
    from aria.engine.collectors.specialized.news import NewsCollector
    assert NewsAgent is NewsCollector


def test_github_agent_not_web_agent():
    """Ensure GitHubAgent is no longer aliasing WebAgent."""
    from aria.engine.collectors.knowledge.github import GitHubCollector as GitHubAgent
    from aria.engine.collectors.web.agent import WebAgent
    assert GitHubAgent is not WebAgent


def test_government_agent_not_web_agent():
    from aria.engine.collectors.specialized.government import GovernmentCollector as GovernmentAgent
    from aria.engine.collectors.web.agent import WebAgent
    assert GovernmentAgent is not WebAgent


def test_multilingual_agent_not_web_agent():
    from aria.engine.collectors.specialized.multilingual import MultilingualCollector as MultilingualAgent
    from aria.engine.collectors.web.agent import WebAgent
    assert MultilingualAgent is not WebAgent


def test_news_agent_not_web_agent():
    from aria.engine.collectors.specialized.news import NewsCollector as NewsAgent
    from aria.engine.collectors.web.agent import WebAgent
    assert NewsAgent is not WebAgent
