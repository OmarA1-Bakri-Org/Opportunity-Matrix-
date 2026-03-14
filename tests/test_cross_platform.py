"""Tests for cross-platform scorer."""

import pytest
from datetime import datetime, timezone, timedelta
from opportunity_matrix.scoring.cross_platform import CrossPlatformScorer
from opportunity_matrix.config import CrossPlatformConfig
from opportunity_matrix.storage.models import Signal, Platform


class TestCrossPlatformScorer:
    @pytest.fixture
    def config(self):
        return CrossPlatformConfig(
            similarity_threshold=0.3,  # lower for testing
            recency_window_hours=168,
            high_recency_hours=48,
        )

    def test_single_platform_scores_low(self, config):
        scorer = CrossPlatformScorer(config)
        old_ts = datetime.now(timezone.utc) - timedelta(hours=200)
        signals = [
            Signal(
                platform=Platform.REDDIT,
                platform_id="r1",
                title="CLI tool for managing Docker containers",
                body="A tool that helps manage Docker",
                created_at=old_ts,
            ),
        ]
        groups = scorer.group_signals(signals)
        assert len(groups) >= 1
        # Single platform = score 0.2
        for group in groups:
            score = scorer.score_group(group)
            assert score == pytest.approx(0.2, abs=0.05)

    def test_two_platforms_scores_higher(self, config):
        scorer = CrossPlatformScorer(config)
        signals = [
            Signal(
                platform=Platform.REDDIT,
                platform_id="r1",
                title="CLI tool for managing Docker containers",
                body="Docker management CLI",
                created_at=datetime.now(timezone.utc),
            ),
            Signal(
                platform=Platform.HACKERNEWS,
                platform_id="hn1",
                title="CLI tool for Docker container management",
                body="Docker CLI tool",
                created_at=datetime.now(timezone.utc),
            ),
        ]
        groups = scorer.group_signals(signals)
        # Should find a group with 2 platforms
        multi = [g for g in groups if len(set(s.platform for s in g)) >= 2]
        assert len(multi) >= 1
        score = scorer.score_group(multi[0])
        assert score >= 0.4  # 2 platforms = 0.5 base

    def test_same_platform_not_counted(self, config):
        scorer = CrossPlatformScorer(config)
        old_ts = datetime.now(timezone.utc) - timedelta(hours=200)
        signals = [
            Signal(
                platform=Platform.REDDIT,
                platform_id="r1",
                title="CLI tool for Docker",
                body="Docker CLI",
                created_at=old_ts,
            ),
            Signal(
                platform=Platform.REDDIT,
                platform_id="r2",
                title="CLI tool for Docker containers",
                body="Docker CLI tool",
                created_at=old_ts,
            ),
        ]
        groups = scorer.group_signals(signals)
        for group in groups:
            platforms = set(s.platform for s in group)
            score = scorer.score_group(group)
            if len(platforms) == 1:
                assert score == pytest.approx(0.2, abs=0.05)

    def test_score_mapping(self, config):
        """Verify platform count to score mapping."""
        scorer = CrossPlatformScorer(config)
        assert scorer._platform_count_score(1) == pytest.approx(0.2)
        assert scorer._platform_count_score(2) == pytest.approx(0.5)
        assert scorer._platform_count_score(3) == pytest.approx(0.8)
        assert scorer._platform_count_score(4) == pytest.approx(1.0)
