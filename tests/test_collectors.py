"""Tests for collectors."""

import pytest
import httpx
import respx
from opportunity_matrix.collectors.base import BaseCollector
from opportunity_matrix.collectors.hackernews import HackerNewsCollector
from opportunity_matrix.config import HackerNewsConfig, KeywordsConfig
from opportunity_matrix.storage.models import Platform


class TestBaseCollector:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseCollector()


class TestHackerNewsCollector:
    @pytest.fixture
    def hn_config(self):
        return HackerNewsConfig(
            enabled=True,
            feeds=["showstories"],
            max_results=5,
        )

    @pytest.fixture
    def keywords(self):
        return KeywordsConfig(
            pain_points=["I wish there was"],
            launches=["Show HN"],
            gaps=[],
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_collect_show_hn(self, hn_config, keywords):
        respx.get("https://hacker-news.firebaseio.com/v0/showstories.json").respond(
            json=[100, 101, 102]
        )
        respx.get("https://hacker-news.firebaseio.com/v0/item/100.json").respond(
            json={
                "id": 100, "type": "story",
                "title": "Show HN: My CLI tool for developers",
                "text": "I built this because I wish there was a better option",
                "url": "https://example.com/tool", "by": "testuser",
                "score": 150, "descendants": 42, "time": 1710374400,
            }
        )
        respx.get("https://hacker-news.firebaseio.com/v0/item/101.json").respond(
            json={
                "id": 101, "type": "story",
                "title": "Unrelated post about cooking",
                "text": "Best recipe for pasta",
                "url": "https://example.com/pasta", "by": "chef",
                "score": 5, "descendants": 2, "time": 1710374400,
            }
        )
        respx.get("https://hacker-news.firebaseio.com/v0/item/102.json").respond(
            json={
                "id": 102, "type": "story",
                "title": "Show HN: Open source alternative to Notion",
                "text": "Built over the weekend",
                "url": "https://example.com/notion-alt", "by": "builder",
                "score": 300, "descendants": 85, "time": 1710374400,
            }
        )

        collector = HackerNewsCollector(hn_config, keywords)
        signals = await collector.collect()

        assert len(signals) >= 1
        assert all(s.platform == Platform.HACKERNEWS for s in signals)
        show_hn = [s for s in signals if "CLI tool" in s.title]
        assert len(show_hn) == 1
        assert show_hn[0].upvotes == 150
        assert show_hn[0].comments_count == 42

    @respx.mock
    @pytest.mark.asyncio
    async def test_collect_handles_api_error(self, hn_config, keywords):
        respx.get("https://hacker-news.firebaseio.com/v0/showstories.json").respond(
            status_code=500
        )
        collector = HackerNewsCollector(hn_config, keywords)
        signals = await collector.collect()
        assert signals == []

    @pytest.mark.asyncio
    async def test_health_check(self, hn_config, keywords):
        collector = HackerNewsCollector(hn_config, keywords)
        healthy = await collector.health_check()
        assert isinstance(healthy, bool)
