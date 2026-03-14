"""Tests for Twitter collector stub."""

import pytest
from opportunity_matrix.collectors.twitter import TwitterCollector
from opportunity_matrix.config import TwitterConfig, KeywordsConfig
from opportunity_matrix.storage.models import Platform


class TestTwitterCollector:
    @pytest.fixture
    def twitter_config_disabled(self):
        return TwitterConfig(enabled=False)

    @pytest.fixture
    def twitter_config_enabled(self):
        return TwitterConfig(enabled=True, max_results=10)

    @pytest.fixture
    def keywords(self):
        return KeywordsConfig(
            pain_points=["I wish there was"],
            launches=[],
            gaps=[],
        )

    @pytest.mark.asyncio
    async def test_disabled_returns_empty(self, twitter_config_disabled, keywords):
        collector = TwitterCollector(twitter_config_disabled, keywords)
        signals = await collector.collect()
        assert signals == []

    @pytest.mark.asyncio
    async def test_enabled_but_no_rube_returns_empty(self, twitter_config_enabled, keywords):
        collector = TwitterCollector(twitter_config_enabled, keywords, rube_token="")
        signals = await collector.collect()
        assert signals == []

    @pytest.mark.asyncio
    async def test_health_check_disabled(self, twitter_config_disabled, keywords):
        collector = TwitterCollector(twitter_config_disabled, keywords)
        healthy = await collector.health_check()
        assert healthy is False  # disabled = not healthy
