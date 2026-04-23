"""GitHub collector — searches repositories and issues via PyGithub or DuckDuckGo fallback."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

from .base import BaseCollector

logger = logging.getLogger("aria")


class GitHubCollector(BaseCollector):
    """Collects GitHub repositories and issues matching research queries.

    Authenticated mode (GITHUB_TOKEN set): uses PyGithub API — 5,000 req/hr.
    Unauthenticated fallback: DuckDuckGo site:github.com search.
    """

    def __init__(self, max_results: int = 20) -> None:
        self._max_results = max_results
        self._token = os.getenv("GITHUB_TOKEN", "")

    async def validate(self) -> bool:
        # Always valid — fallback to DDG if no token
        if self._token:
            try:
                from github import Github
                g = Github(self._token)
                g.get_user().login  # noqa: B018 — validate token
                return True
            except Exception:
                return False
        return True

    async def collect(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Search GitHub for repositories and issues matching queries.

        Args:
            queries: Research query strings.

        Yields:
            Document dicts with platform='github', source_type='technical_doc'.
        """
        if self._token:
            async for doc in self._collect_authenticated(queries):
                yield doc
        else:
            logger.info("GitHubCollector: no GITHUB_TOKEN set, using DuckDuckGo fallback")
            async for doc in self._collect_public(queries):
                yield doc

    async def _collect_authenticated(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Search GitHub via PyGithub API."""
        try:
            from github import Github, GithubException
        except ImportError:
            logger.warning("GitHubCollector: PyGithub not installed, falling back to public")
            async for doc in self._collect_public(queries):
                yield doc
            return

        g = Github(self._token)
        seen_urls: set[str] = set()
        count = 0

        for query in queries:
            if count >= self._max_results:
                break

            # Search repositories
            try:
                repos = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda q=query: list(g.search_repositories(q, sort="stars")[:5]),
                )
                for repo in repos:
                    if count >= self._max_results:
                        break
                    url = repo.html_url
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # Get README excerpt
                    text = repo.description or ""
                    try:
                        readme = await asyncio.get_event_loop().run_in_executor(
                            None, repo.get_readme
                        )
                        raw = readme.decoded_content.decode("utf-8", errors="ignore")
                        # Strip markdown headers and take first 2000 chars
                        text_lines = [ln for ln in raw.splitlines() if ln.strip() and not ln.startswith("#")]
                        text = (repo.description or "") + "\n\n" + "\n".join(text_lines[:50])
                        text = text[:3000]
                    except Exception:
                        pass

                    if not text.strip():
                        continue

                    yield {
                        "url": url,
                        "title": f"{repo.full_name} — {repo.description or 'GitHub Repository'}",
                        "text": text.strip(),
                        "source_type": "technical_doc",
                        "platform": "github",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "stars": repo.stargazers_count,
                            "forks": repo.forks_count,
                            "repo_language": repo.language or "",
                            "topics": repo.get_topics()[:5] if hasattr(repo, "get_topics") else [],
                            "query": query,
                        },
                    }
                    count += 1

                await asyncio.sleep(0.5)

            except GithubException as exc:
                logger.warning("GitHubCollector: repo search error for '%s': %s", query, exc)

            # Search issues
            try:
                issues = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda q=query: list(
                        g.search_issues(q + " type:issue", sort="reactions")[:5]
                    ),
                )
                for issue in issues:
                    if count >= self._max_results:
                        break
                    url = issue.html_url
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    body = issue.body or ""
                    text = f"{issue.title}\n\n{body[:2000]}".strip()
                    if len(text) < 30:
                        continue

                    yield {
                        "url": url,
                        "title": f"{issue.title} [{issue.repository.full_name}]",
                        "text": text,
                        "source_type": "technical_doc",
                        "platform": "github",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "repo": issue.repository.full_name,
                            "state": issue.state,
                            "comments": issue.comments,
                            "reactions": getattr(issue.reactions, "total_count", 0),
                            "query": query,
                            "item_type": "issue",
                        },
                    }
                    count += 1

                await asyncio.sleep(0.5)

            except GithubException as exc:
                logger.warning("GitHubCollector: issue search error for '%s': %s", query, exc)

    async def _collect_public(self, queries: list[str]) -> AsyncGenerator[dict[str, Any], None]:
        """Search GitHub via DuckDuckGo site:github.com."""
        seen_urls: set[str] = set()
        count = 0

        for query in queries:
            if count >= self._max_results:
                break
            try:
                search_query = f"site:github.com {query}"
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS

                results: list[dict] = []
                with DDGS() as ddgs:
                    for r in ddgs.text(search_query, max_results=5):
                        results.append(r)

                for result in results:
                    if count >= self._max_results:
                        break
                    url = result.get("href", "")
                    if not url or "github.com" not in url:
                        continue
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = result.get("title", "")
                    body = result.get("body", "")
                    text = f"{title}\n\n{body}".strip()
                    if len(text) < 30:
                        continue

                    yield {
                        "url": url,
                        "title": title,
                        "text": text,
                        "source_type": "technical_doc",
                        "platform": "github",
                        "language": "en",
                        "word_count": len(text.split()),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {"query": query, "method": "duckduckgo_fallback"},
                    }
                    count += 1

                await asyncio.sleep(0.3)

            except Exception as exc:
                logger.warning("GitHubCollector: public search error for '%s': %s", query, exc)
