"""Tests for feasibility scorer."""

import pytest
from opportunity_matrix.scoring.feasibility import FeasibilityScorer
from opportunity_matrix.config import ScoringConfig, FeasibilityRules, FeasibilityRule, LLMConfig
from opportunity_matrix.storage.models import Signal, Platform
from datetime import datetime, timezone


class TestFeasibilityScorer:
    @pytest.fixture
    def scoring_config(self):
        return ScoringConfig(
            feasibility_rules=FeasibilityRules(
                boosters=[
                    FeasibilityRule(pattern="CLI tool", score=0.3),
                    FeasibilityRule(pattern="browser extension", score=0.3),
                    FeasibilityRule(pattern="API wrapper", score=0.3),
                    FeasibilityRule(pattern="open source alternative", score=0.2),
                ],
                penalties=[
                    FeasibilityRule(pattern="enterprise", score=-0.3),
                    FeasibilityRule(pattern="requires team", score=-0.3),
                    FeasibilityRule(pattern="healthcare", score=-0.4),
                ],
            ),
            llm=LLMConfig(enabled=False),
        )

    def test_cli_tool_boosted(self, scoring_config):
        scorer = FeasibilityScorer(scoring_config)
        signal = Signal(
            platform=Platform.REDDIT,
            platform_id="r1",
            title="I wish there was a CLI tool for managing logs",
            body="Current tools are terrible",
            created_at=datetime.now(timezone.utc),
        )
        score = scorer.score(signal)
        assert score == pytest.approx(0.8, abs=0.01)  # base 0.5 + 0.3

    def test_enterprise_penalized(self, scoring_config):
        scorer = FeasibilityScorer(scoring_config)
        signal = Signal(
            platform=Platform.HACKERNEWS,
            platform_id="hn1",
            title="Enterprise deployment platform needed",
            body="For large teams",
            created_at=datetime.now(timezone.utc),
        )
        score = scorer.score(signal)
        assert score == pytest.approx(0.2, abs=0.01)  # base 0.5 - 0.3

    def test_multiple_rules_stack(self, scoring_config):
        scorer = FeasibilityScorer(scoring_config)
        signal = Signal(
            platform=Platform.REDDIT,
            platform_id="r2",
            title="Open source alternative CLI tool",
            body="A CLI tool that is also an open source alternative",
            created_at=datetime.now(timezone.utc),
        )
        score = scorer.score(signal)
        assert score == pytest.approx(1.0, abs=0.01)  # base 0.5 + 0.3 + 0.2 = 1.0 (clamped)

    def test_clamped_to_zero(self, scoring_config):
        scorer = FeasibilityScorer(scoring_config)
        signal = Signal(
            platform=Platform.REDDIT,
            platform_id="r3",
            title="Enterprise healthcare platform requires team",
            body="Regulatory compliance needed",
            created_at=datetime.now(timezone.utc),
        )
        score = scorer.score(signal)
        assert score == 0.0  # base 0.5 - 0.3 - 0.4 - 0.3 = -0.5 → clamped to 0.0

    def test_no_matching_rules(self, scoring_config):
        scorer = FeasibilityScorer(scoring_config)
        signal = Signal(
            platform=Platform.REDDIT,
            platform_id="r4",
            title="A random project idea",
            body="Something interesting",
            created_at=datetime.now(timezone.utc),
        )
        score = scorer.score(signal)
        assert score == pytest.approx(0.5, abs=0.01)  # just base score

    def test_llm_disabled_returns_rule_score(self, scoring_config):
        scorer = FeasibilityScorer(scoring_config)
        signal = Signal(
            platform=Platform.REDDIT,
            platform_id="r5",
            title="API wrapper for payments",
            body="Wrap Stripe API",
            created_at=datetime.now(timezone.utc),
        )
        score = scorer.score(signal)
        # LLM disabled, should just return rule-based score
        assert score == pytest.approx(0.8, abs=0.01)  # base 0.5 + 0.3
