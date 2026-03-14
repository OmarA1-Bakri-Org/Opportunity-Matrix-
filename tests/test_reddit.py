"""Tests for Reddit collector."""

import pytest
import respx
from opportunity_matrix.collectors.reddit import RedditCollector
from opportunity_matrix.config import RedditConfig, KeywordsConfig
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

    @respx.mock
    @pytest.mark.asyncio
    async def test_collect_from_subreddits(self, reddit_config, keywords):
        respx.post("https://www.reddit.com/api/v1/access_token").respond(
            json={"access_token": "test_token", "token_type": "bearer", "expires_in": 3600}
        )
        respx.get("https://oauth.reddit.com/r/SaaS/new").respond(
            json={
                "data": {
                    "children": [
                        {
                            "data": {
                                "id": "r1",
                                "title": "I wish there was a better invoicing tool",
                                "selftext": "Current options are terrible",
                                "url": "https://reddit.com/r/SaaS/r1",
                                "author": "redditor1",
                                "ups": 85,
                                "num_comments": 30,
                                "created_utc": 1710374400,
                                "subreddit": "SaaS",
                                "permalink": "/r/SaaS/comments/r1/test/",
                            }
                        }
                    ]
                }
            }
        )
        respx.get("https://oauth.reddit.com/r/sideproject/new").respond(
            json={"data": {"children": []}}
        )

        collector = RedditCollector(
            reddit_config, keywords,
            client_id="test_id", client_secret="test_secret",
            username="test_user", password="test_pass",
        )
        signals = await collector.collect()

        assert len(signals) >= 1
        assert signals[0].platform == Platform.REDDIT
        assert "invoicing" in signals[0].title
        assert signals[0].upvotes == 85

    @respx.mock
    @pytest.mark.asyncio
    async def test_collect_handles_auth_failure(self, reddit_config, keywords):
        respx.post("https://www.reddit.com/api/v1/access_token").respond(status_code=401)

        collector = RedditCollector(
            reddit_config, keywords,
            client_id="bad", client_secret="bad",
            username="bad", password="bad",
        )
        signals = await collector.collect()
        assert signals == []
