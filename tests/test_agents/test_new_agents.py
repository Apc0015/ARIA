"""Tests for new agent wrappers — GitHub, Government, Multilingual, News."""

from __future__ import annotations

import pytest


def test_github_agent_imports_real_collector():
    from aria.agents.github import GitHubAgent
    from aria.engine.collectors.knowledge.github import GitHubCollector
    assert GitHubAgent is GitHubCollector


def test_government_agent_imports_real_collector():
    from aria.agents.government import GovernmentAgent
    from aria.engine.collectors.specialized.government import GovernmentCollector
    assert GovernmentAgent is GovernmentCollector


def test_multilingual_agent_imports_real_collector():
    from aria.agents.multilingual import MultilingualAgent
    from aria.engine.collectors.specialized.multilingual import MultilingualCollector
    assert MultilingualAgent is MultilingualCollector


def test_news_agent_imports_real_collector():
    from aria.agents.news import NewsAgent
    from aria.engine.collectors.specialized.news import NewsCollector
    assert NewsAgent is NewsCollector


def test_github_agent_not_web_agent():
    """Ensure GitHubAgent is no longer aliasing WebAgent."""
    from aria.agents.github import GitHubAgent
    from aria.agents.web import WebAgent
    assert GitHubAgent is not WebAgent


def test_government_agent_not_web_agent():
    from aria.agents.government import GovernmentAgent
    from aria.agents.web import WebAgent
    assert GovernmentAgent is not WebAgent


def test_multilingual_agent_not_web_agent():
    from aria.agents.multilingual import MultilingualAgent
    from aria.agents.web import WebAgent
    assert MultilingualAgent is not WebAgent


def test_news_agent_not_web_agent():
    from aria.agents.news import NewsAgent
    from aria.agents.web import WebAgent
    assert NewsAgent is not WebAgent
