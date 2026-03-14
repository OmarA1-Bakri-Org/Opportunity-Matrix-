"""Tests for engagement scorer."""

import pytest
from datetime import datetime, timezone
from opportunity_matrix.scoring.engagement import EngagementScorer
from opportunity_matrix.storage.models import Signal, Platform


class TestEngagementScorer:
    def test_score_reddit_signal(self):
        scorer = EngagementScorer()
        signal = Signal(
            platform=Platform.REDDIT,
            platform_id="r1",
            title="Test",
            upvotes=200,
            comments_count=50,
            created_at=datetime.now(timezone.utc),
        )
        score = scorer.score(signal)
        assert 0.0 <= score <= 1.0

    def test_score_hackernews_signal(self):
        scorer = EngagementScorer()
        signal = Signal(
            platform=Platform.HACKERNEWS,
            platform_id="hn1",
            title="Show HN: Test",
            upvotes=500,
            comments_count=200,
            created_at=datetime.now(timezone.utc),
        )
        score = scorer.score(signal)
        assert score > 0.5  # 500 points + 200 comments is strong

    def test_score_github_signal(self):
        scorer = EngagementScorer()
        signal = Signal(
            platform=Platform.GITHUB,
            platform_id="gh1",
            title="user/repo",
            upvotes=1000,  # stars
            comments_count=50,  # issues
            metadata={"forks": 200},
            created_at=datetime.now(timezone.utc),
        )
        score = scorer.score(signal)
        assert 0.0 <= score <= 1.0

    def test_score_clamped_to_1(self):
        scorer = EngagementScorer()
        signal = Signal(
            platform=Platform.REDDIT,
            platform_id="r_huge",
            title="Viral post",
            upvotes=50000,
            comments_count=10000,
            created_at=datetime.now(timezone.utc),
        )
        score = scorer.score(signal)
        assert score == 1.0

    def test_score_zero_engagement(self):
        scorer = EngagementScorer()
        signal = Signal(
            platform=Platform.REDDIT,
            platform_id="r_zero",
            title="No engagement",
            upvotes=0,
            comments_count=0,
            created_at=datetime.now(timezone.utc),
        )
        score = scorer.score(signal)
        assert score == 0.0

    def test_update_percentiles(self):
        scorer = EngagementScorer()
        signals = [
            Signal(platform=Platform.REDDIT, platform_id=f"r_{i}",
                   title=f"Post {i}", upvotes=i * 10, comments_count=i * 3,
                   created_at=datetime.now(timezone.utc))
            for i in range(100)
        ]
        scorer.update_percentiles(signals)
        mid_signal = signals[50]
        score = scorer.score(mid_signal)
        assert 0.3 <= score <= 0.8
