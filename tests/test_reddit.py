"""Tests for Reddit collector (Rube MCP)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from opportunity_matrix.collectors.reddit import RedditCollector
from opportunity_matrix.config import RedditConfig, KeywordsConfig
from opportunity_matrix.rube_client import RubeClient
from opportunity_matrix.storage.models import Platform


class TestRedditCollector:
    @pytest.fixture
    def reddit_config(self):
        return RedditConfig(
            enabled=True,
            subreddits=["SaaS", "sideproject"],
            max_results_per_sub=5,
        )

    @pytest.fixture
    def keywords(self):
        return KeywordsConfig(
            pain_points=["I wish there was"],
            launches=["just launched"],
            gaps=[],
        )

    @pytest.fixture
    def rube(self):
        return RubeClient(url="https://rube.app/mcp", token="test-token")

    @pytest.fixture
    def rube_reddit_response(self):
        """Simulates the parsed Rube REDDIT_SEARCH response structure."""
        return [{
            "response": {
                "data": {
                    "data": {
                        "children": [
                            {
                                "data": {
                                    "id": "r1",
                                    "title": "I wish there was a better invoicing tool",
                                    "selftext": "Current options are terrible",
                                    "author": "redditor1",
                                    "ups": 85,
                                    "num_comments": 30,
                                    "created_utc": 1710374400,
                                    "subreddit": "SaaS",
                                    "permalink": "/r/SaaS/comments/r1/test/",
                                }
                            },
                            {
                                "data": {
                                    "id": "r2",
                                    "title": "Random unrelated post",
                                    "selftext": "Nothing to see here",
                                    "author": "redditor2",
                                    "ups": 5,
                                    "num_comments": 1,
                                    "created_utc": 1710374400,
                                    "subreddit": "SaaS",
                                    "permalink": "/r/SaaS/comments/r2/test/",
                                }
                            },
                        ]
                    }
                }
            }
        }]

    @pytest.mark.asyncio
    async def test_collect_from_subreddits(self, reddit_config, keywords, rube, rube_reddit_response):
        rube.execute_tools = AsyncMock(return_value=rube_reddit_response)

        collector = RedditCollector(
            config=reddit_config,
            keywords=keywords,
            rube=rube,
        )
        signals = await collector.collect()

        # Only "I wish there was" should match keyword filter, not the random post
        assert len(signals) >= 1
        assert signals[0].platform == Platform.REDDIT
        assert "invoicing" in signals[0].title
        assert signals[0].upvotes == 85
        assert signals[0].author == "redditor1"
        assert signals[0].metadata["subreddit"] == "SaaS"

        # Verify Rube was called with correct tool slug
        rube.execute_tools.assert_called()
        call_args = rube.execute_tools.call_args_list[0][0][0]
        assert call_args[0]["tool_slug"] == "REDDIT_SEARCH_ACROSS_SUBREDDITS"

    @pytest.mark.asyncio
    async def test_collect_no_rube_returns_empty(self, reddit_config, keywords):
        collector = RedditCollector(
            config=reddit_config,
            keywords=keywords,
            rube=None,
        )
        signals = await collector.collect()
        assert signals == []

    @pytest.mark.asyncio
    async def test_collect_no_rube_token_returns_empty(self, reddit_config, keywords):
        rube = RubeClient(url="https://rube.app/mcp", token="")
        collector = RedditCollector(
            config=reddit_config,
            keywords=keywords,
            rube=rube,
        )
        signals = await collector.collect()
        assert signals == []

    @pytest.mark.asyncio
    async def test_collect_handles_rube_error(self, reddit_config, keywords, rube):
        rube.execute_tools = AsyncMock(side_effect=Exception("Rube connection failed"))

        collector = RedditCollector(
            config=reddit_config,
            keywords=keywords,
            rube=rube,
        )
        signals = await collector.collect()
        assert signals == []

    @pytest.mark.asyncio
    async def test_collect_empty_results(self, reddit_config, keywords, rube):
        rube.execute_tools = AsyncMock(return_value=[])

        collector = RedditCollector(
            config=reddit_config,
            keywords=keywords,
            rube=rube,
        )
        signals = await collector.collect()
        assert signals == []

    @pytest.mark.asyncio
    async def test_health_check_no_rube(self, reddit_config, keywords):
        collector = RedditCollector(
            config=reddit_config,
            keywords=keywords,
            rube=None,
        )
        healthy = await collector.health_check()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_health_check_delegates_to_rube(self, reddit_config, keywords, rube):
        rube.health_check = AsyncMock(return_value=True)

        collector = RedditCollector(
            config=reddit_config,
            keywords=keywords,
            rube=rube,
        )
        healthy = await collector.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_backwards_compat_old_params_ignored(self, reddit_config, keywords, rube):
        """Old client_id/client_secret/username/password params are accepted but unused."""
        rube.execute_tools = AsyncMock(return_value=[])

        collector = RedditCollector(
            config=reddit_config,
            keywords=keywords,
            rube=rube,
            client_id="old_id",
            client_secret="old_secret",
            username="old_user",
            password="old_pass",
        )
        # Should not raise, old params are accepted
        signals = await collector.collect()
        assert signals == []
