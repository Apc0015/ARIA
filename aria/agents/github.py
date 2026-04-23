"""GitHub agent — searches repositories and issues via PyGithub or DuckDuckGo fallback."""

from aria.engine.collectors.knowledge.github import GitHubCollector as GitHubAgent

__all__ = ["GitHubAgent"]
