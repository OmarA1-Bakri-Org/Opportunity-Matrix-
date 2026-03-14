"""Integration test — full scan-score-query pipeline end-to-end."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from opportunity_matrix.config import (
    AppConfig,
    CrossPlatformConfig,
    FeasibilityRule,
    FeasibilityRules,
    ScoringConfig,
    ScoringWeights,
)
from opportunity_matrix.scoring.cross_platform import CrossPlatformScorer
from opportunity_matrix.scoring.engagement import EngagementScorer
from opportunity_matrix.scoring.feasibility import FeasibilityScorer
from opportunity_matrix.storage.db import Database
from opportunity_matrix.storage.models import Opportunity, Platform, Signal


@pytest.fixture
def db(tmp_path):
    """Create a fresh temporary database for each test."""
    db = Database(str(tmp_path / "test_integration.db"))
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def config():
    """Provide a deterministic scoring config."""
    return AppConfig(
        scoring=ScoringConfig(
            weights=ScoringWeights(
                engagement=0.25,
                cross_platform=0.45,
                feasibility=0.30,
            ),
            feasibility_rules=FeasibilityRules(
                boosters=[
                    FeasibilityRule(pattern="CLI tool", score=0.10),
                    FeasibilityRule(pattern="solo developer", score=0.10),
                ],
                penalties=[
                    FeasibilityRule(pattern="enterprise", score=-0.15),
                ],
            ),
        ),
        cross_platform=CrossPlatformConfig(
            similarity_threshold=0.50,  # Lower for test reliability
            recency_window_hours=168,
            high_recency_hours=48,
        ),
    )


def _make_signal(
    platform: Platform,
    title: str,
    body: str = "",
    upvotes: int = 50,
    comments: int = 10,
    hours_ago: int = 200,
    **kwargs,
) -> Signal:
    """Helper to create a Signal with a stable, old timestamp (outside recency window)."""
    created = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return Signal(
        id=str(uuid.uuid4()),
        platform=platform,
        platform_id=f"{platform.value}_{uuid.uuid4().hex[:8]}",
        title=title,
        body=body,
        upvotes=upvotes,
        comments_count=comments,
        created_at=created,
        collected_at=created,
        **kwargs,
    )


class TestIntegrationPipeline:
    """End-to-end integration tests for the scan→score→query pipeline."""

    def test_full_pipeline_cross_platform_detection(self, db, config):
        """Insert similar signals from 2 platforms → run scoring → verify cross-platform grouping."""
        # --- Arrange: Insert signals with similar titles from Reddit and HN ---
        reddit_signal = _make_signal(
            Platform.REDDIT,
            title="CLI tool for Docker container management",
            body="I wish there was a better CLI tool for managing Docker containers",
            upvotes=120,
            comments=45,
        )
        hn_signal = _make_signal(
            Platform.HACKERNEWS,
            title="CLI tool for Docker container management and orchestration",
            body="Show HN: Built a CLI tool for Docker management",
            upvotes=80,
            comments=30,
        )
        # Unrelated signal — should NOT group with the Docker signals
        github_signal = _make_signal(
            Platform.GITHUB,
            title="machine-learning-pipeline-visualization",
            body="A library for visualizing ML pipelines",
            upvotes=200,
            comments=15,
        )

        db.insert_signal(reddit_signal)
        db.insert_signal(hn_signal)
        db.insert_signal(github_signal)

        # Verify signals stored
        assert db.get_signal_count() == 3
        assert db.get_signal_count(Platform.REDDIT) == 1
        assert db.get_signal_count(Platform.HACKERNEWS) == 1

        # --- Act: Run the scoring pipeline (mirrors cli.py score command) ---
        engagement_scorer = EngagementScorer()
        cross_platform_scorer = CrossPlatformScorer(config.cross_platform)
        feasibility_scorer = FeasibilityScorer(config.scoring)

        signals = db.get_unlinked_signals()
        assert len(signals) == 3

        groups = cross_platform_scorer.group_signals(signals)

        # --- Assert: Docker signals should be grouped together ---
        # Find the group containing the Docker-related signals
        docker_group = None
        for group in groups:
            titles = [s.title for s in group]
            if any("Docker" in t for t in titles):
                docker_group = group
                break

        assert docker_group is not None, "Docker signals should be grouped together"
        docker_platforms = set(s.platform for s in docker_group)
        assert len(docker_platforms) >= 2, "Docker group should span 2+ platforms"

        # Score and store opportunities
        scored_count = 0
        for group in groups:
            platforms = set(s.platform for s in group)
            cross_score = cross_platform_scorer.score_group(group)
            best_signal = max(group, key=lambda s: engagement_scorer.score(s))
            eng_score = engagement_scorer.score(best_signal)
            feas_score = feasibility_scorer.score(best_signal)

            weights = config.scoring.weights
            composite = (
                eng_score * weights.engagement
                + cross_score * weights.cross_platform
                + feas_score * weights.feasibility
            )

            opp = Opportunity(
                title=best_signal.title,
                description=best_signal.body[:500],
                engagement_score=eng_score,
                cross_platform_score=cross_score,
                feasibility_score=feas_score,
                composite_score=round(composite, 4),
                platform_count=len(platforms),
            )
            db.insert_opportunity(opp)
            for s in group:
                db.link_signal_opportunity(s.id, opp.id)
            scored_count += 1

        assert scored_count == len(groups)

        # --- Assert: Query opportunities ---
        all_opps = db.get_opportunities(min_score=0.0)
        assert len(all_opps) >= 2  # At least Docker group + ML group

        # Docker opportunity should have platform_count >= 2
        docker_opp = [o for o in all_opps if "Docker" in o.title]
        assert len(docker_opp) == 1
        assert docker_opp[0].platform_count >= 2
        assert docker_opp[0].cross_platform_score >= 0.5  # 2 platforms → 0.5 base
        assert docker_opp[0].composite_score > 0.0

    def test_composite_score_calculation(self, db, config):
        """Verify composite score = weighted sum of engagement, cross-platform, feasibility."""
        signal = _make_signal(
            Platform.REDDIT,
            title="CLI tool for solo developer workflow automation",
            body="Solo developer looking for a CLI tool to automate tasks",
            upvotes=100,
            comments=20,
        )
        db.insert_signal(signal)

        engagement_scorer = EngagementScorer()
        feasibility_scorer = FeasibilityScorer(config.scoring)

        eng_score = engagement_scorer.score(signal)
        feas_score = feasibility_scorer.score(signal)
        # Single platform → cross-platform score = 0.2
        cross_score = 0.2

        weights = config.scoring.weights
        expected_composite = (
            eng_score * weights.engagement
            + cross_score * weights.cross_platform
            + feas_score * weights.feasibility
        )

        opp = Opportunity(
            title=signal.title,
            description=signal.body,
            engagement_score=eng_score,
            cross_platform_score=cross_score,
            feasibility_score=feas_score,
            composite_score=round(expected_composite, 4),
            platform_count=1,
        )
        db.insert_opportunity(opp)
        db.link_signal_opportunity(signal.id, opp.id)

        # Verify the composite calculation
        assert eng_score > 0.0  # Reddit 100*0.6 + 20*0.4 = 68, /500 p90 = 0.136
        assert feas_score > 0.5  # Base 0.5 + "CLI tool" 0.1 + "solo developer" 0.1 = 0.7

        stored = db.get_opportunities(min_score=0.0)
        assert len(stored) == 1
        assert stored[0].composite_score == round(expected_composite, 4)

        # Verify linked signals
        linked = db.get_signals_for_opportunity(stored[0].id)
        assert len(linked) == 1
        assert linked[0].id == signal.id

    def test_unlinked_signals_cleared_after_scoring(self, db, config):
        """After scoring, signals should be linked to opportunities (no longer unlinked)."""
        signals = [
            _make_signal(Platform.REDDIT, "Open source project for data viz"),
            _make_signal(Platform.HACKERNEWS, "New data visualization framework"),
        ]
        for s in signals:
            db.insert_signal(s)

        # Before scoring: all signals are unlinked
        unlinked = db.get_unlinked_signals()
        assert len(unlinked) == 2

        # Score and link
        engagement_scorer = EngagementScorer()
        cross_platform_scorer = CrossPlatformScorer(config.cross_platform)
        feasibility_scorer = FeasibilityScorer(config.scoring)

        groups = cross_platform_scorer.group_signals(unlinked)
        for group in groups:
            best = max(group, key=lambda s: engagement_scorer.score(s))
            opp = Opportunity(
                title=best.title,
                engagement_score=engagement_scorer.score(best),
                cross_platform_score=cross_platform_scorer.score_group(group),
                feasibility_score=feasibility_scorer.score(best),
                platform_count=len(set(s.platform for s in group)),
            )
            db.insert_opportunity(opp)
            for s in group:
                db.link_signal_opportunity(s.id, opp.id)

        # After scoring: no unlinked signals remain
        unlinked_after = db.get_unlinked_signals()
        assert len(unlinked_after) == 0

    def test_query_filters(self, db, config):
        """Verify query filters work: min_score, min_platforms, status."""
        # Insert two opportunities with different scores and platform counts
        high_opp = Opportunity(
            title="High-score multi-platform opportunity",
            composite_score=0.85,
            platform_count=3,
            status="new",
        )
        low_opp = Opportunity(
            title="Low-score single-platform opportunity",
            composite_score=0.15,
            platform_count=1,
            status="new",
        )
        db.insert_opportunity(high_opp)
        db.insert_opportunity(low_opp)

        # All opportunities
        all_opps = db.get_opportunities(min_score=0.0)
        assert len(all_opps) == 2

        # Filter by min_score
        high_only = db.get_opportunities(min_score=0.5)
        assert len(high_only) == 1
        assert high_only[0].title == "High-score multi-platform opportunity"

        # Filter by min_platforms
        multi_platform = db.get_opportunities(min_score=0.0, min_platforms=2)
        assert len(multi_platform) == 1
        assert multi_platform[0].platform_count == 3

    def test_feasibility_boosters_affect_composite(self, db, config):
        """Signals matching booster patterns should have higher feasibility and composite scores."""
        # Signal with booster keywords
        boosted = _make_signal(
            Platform.REDDIT,
            title="CLI tool for solo developer automation",
            upvotes=50,
            comments=10,
        )
        # Signal without booster keywords
        neutral = _make_signal(
            Platform.REDDIT,
            title="Random project discussion thread",
            upvotes=50,
            comments=10,
        )

        feasibility_scorer = FeasibilityScorer(config.scoring)
        boosted_feas = feasibility_scorer.score(boosted)
        neutral_feas = feasibility_scorer.score(neutral)

        # Boosted should be higher: base 0.5 + "CLI tool" 0.1 + "solo developer" 0.1 = 0.7
        assert boosted_feas == pytest.approx(0.7, abs=0.01)
        assert neutral_feas == pytest.approx(0.5, abs=0.01)
        assert boosted_feas > neutral_feas
