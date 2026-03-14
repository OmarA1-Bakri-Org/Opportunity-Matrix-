"""Tests for GitHub collector (Rube MCP)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from opportunity_matrix.collectors.github_trending import GitHubCollector
from opportunity_matrix.config import GitHubConfig, KeywordsConfig
from opportunity_matrix.rube_client import RubeClient
from opportunity_matrix.storage.models import Platform


class TestGitHubCollector:
    @pytest.fixture
    def github_config(self):
        return GitHubConfig(
            enabled=True,
            languages=["python", "typescript"],
            min_stars=10,
            max_results=5,
        )

    @pytest.fixture
    def keywords(self):
        return KeywordsConfig(
            pain_points=["I wish there was"],
            launches=["open source alternative"],
            gaps=[],
        )

    @pytest.fixture
    def rube(self):
        return RubeClient(url="https://rube.app/mcp", token="test-token")

    @pytest.fixture
    def rube_github_response(self):
        """Simulates the parsed Rube GITHUB_FIND_REPOSITORIES response structure."""
        return [{
            "response": {
                "data": {
                    "items": [
                        {
                            "id": 12345,
                            "full_name": "user/awesome-cli",
                            "name": "awesome-cli",
                            "description": "Open source alternative to expensive CLI tools",
                            "html_url": "https://github.com/user/awesome-cli",
                            "stargazers_count": 150,
                            "forks_count": 30,
                            "open_issues_count": 10,
                            "language": "Python",
                            "topics": ["cli", "developer-tools"],
                            "created_at": "2026-03-10T00:00:00Z",
                            "owner": {"login": "user"},
                        },
                        {
                            "id": 67890,
                            "full_name": "dev/enterprise-platform",
                            "name": "enterprise-platform",
                            "description": "Enterprise deployment platform",
                            "html_url": "https://github.com/dev/enterprise-platform",
                            "stargazers_count": 500,
                            "forks_count": 100,
                            "open_issues_count": 50,
                            "language": "TypeScript",
                            "topics": ["enterprise"],
                            "created_at": "2026-03-10T00:00:00Z",
                            "owner": {"login": "dev"},
                        },
                    ]
                }
            }
        }]

    @pytest.mark.asyncio
    async def test_collect_trending_repos(self, github_config, keywords, rube, rube_github_response):
        rube.execute_tools = AsyncMock(return_value=rube_github_response)

        collector = GitHubCollector(
            config=github_config,
            keywords=keywords,
            rube=rube,
        )
        signals = await collector.collect()

        assert len(signals) >= 1
        assert all(s.platform == Platform.GITHUB for s in signals)
        cli_repos = [s for s in signals if "awesome-cli" in s.title]
        assert len(cli_repos) == 1
        assert cli_repos[0].upvotes == 150  # stars mapped to upvotes
        assert cli_repos[0].author == "user"
        assert cli_repos[0].metadata["language"] == "Python"

        # Verify Rube was called with correct tool slug
        rube.execute_tools.assert_called()
        call_args = rube.execute_tools.call_args_list[0][0][0]
        assert call_args[0]["tool_slug"] == "GITHUB_FIND_REPOSITORIES"

    @pytest.mark.asyncio
    async def test_collect_no_rube_returns_empty(self, github_config, keywords):
        collector = GitHubCollector(
            config=github_config,
            keywords=keywords,
            rube=None,
        )
        signals = await collector.collect()
        assert signals == []

    @pytest.mark.asyncio
    async def test_collect_no_rube_token_returns_empty(self, github_config, keywords):
        rube = RubeClient(url="https://rube.app/mcp", token="")
        collector = GitHubCollector(
            config=github_config,
            keywords=keywords,
            rube=rube,
        )
        signals = await collector.collect()
        assert signals == []

    @pytest.mark.asyncio
    async def test_collect_handles_rube_error(self, github_config, keywords, rube):
        rube.execute_tools = AsyncMock(side_effect=Exception("Rube connection failed"))

        collector = GitHubCollector(
            config=github_config,
            keywords=keywords,
            rube=rube,
        )
        signals = await collector.collect()
        assert signals == []

    @pytest.mark.asyncio
    async def test_collect_deduplicates_across_languages(self, github_config, keywords, rube, rube_github_response):
        """Same repo returned for both languages should only appear once."""
        rube.execute_tools = AsyncMock(return_value=rube_github_response)

        collector = GitHubCollector(
            config=github_config,
            keywords=keywords,
            rube=rube,
        )
        signals = await collector.collect()

        # Both languages call execute_tools, so rube.execute_tools called twice
        assert rube.execute_tools.call_count == 2
        # But deduplication should prevent duplicate platform_ids
        ids = [s.platform_id for s in signals]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_health_check_no_rube(self, github_config, keywords):
        collector = GitHubCollector(
            config=github_config,
            keywords=keywords,
            rube=None,
        )
        healthy = await collector.health_check()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_health_check_delegates_to_rube(self, github_config, keywords, rube):
        rube.health_check = AsyncMock(return_value=True)

        collector = GitHubCollector(
            config=github_config,
            keywords=keywords,
            rube=rube,
        )
        healthy = await collector.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_backwards_compat_token_param_ignored(self, github_config, keywords, rube):
        """Old token param is accepted but unused."""
        rube.execute_tools = AsyncMock(return_value=[])

        collector = GitHubCollector(
            config=github_config,
            keywords=keywords,
            rube=rube,
            token="ghp_old_token",
        )
        # Should not raise, old token param is accepted
        signals = await collector.collect()
        assert signals == []
