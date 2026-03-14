"""Tests for GitHub collector."""

import pytest
import respx
from opportunity_matrix.collectors.github_trending import GitHubCollector
from opportunity_matrix.config import GitHubConfig, KeywordsConfig
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

    @respx.mock
    @pytest.mark.asyncio
    async def test_collect_trending_repos(self, github_config, keywords):
        respx.get("https://api.github.com/search/repositories").respond(
            json={
                "total_count": 2,
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
                ],
            }
        )

        collector = GitHubCollector(github_config, keywords, token="ghp_test")
        signals = await collector.collect()

        assert len(signals) >= 1
        assert all(s.platform == Platform.GITHUB for s in signals)
        cli_repos = [s for s in signals if "awesome-cli" in s.title]
        assert len(cli_repos) == 1
        assert cli_repos[0].upvotes == 150  # stars mapped to upvotes

    @respx.mock
    @pytest.mark.asyncio
    async def test_collect_handles_api_error(self, github_config, keywords):
        respx.get("https://api.github.com/search/repositories").respond(status_code=403)
        collector = GitHubCollector(github_config, keywords, token="ghp_test")
        signals = await collector.collect()
        assert signals == []

    @respx.mock
    @pytest.mark.asyncio
    async def test_collect_no_token(self, github_config, keywords):
        respx.get("https://api.github.com/search/repositories").respond(
            json={"total_count": 0, "items": []}
        )
        collector = GitHubCollector(github_config, keywords, token="")
        signals = await collector.collect()
        assert signals == []  # no token = no results
