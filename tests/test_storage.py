"""Tests for storage layer — models and database operations."""

import pytest
from datetime import datetime, timezone
from opportunity_matrix.storage.models import Signal, Opportunity, Platform
from opportunity_matrix.storage.db import Database


class TestModels:
    def test_signal_creation(self):
        signal = Signal(
            platform=Platform.REDDIT,
            platform_id="abc123",
            title="I wish there was a CLI tool for X",
            body="Full body text here",
            url="https://reddit.com/r/SaaS/abc123",
            author="testuser",
            upvotes=150,
            comments_count=42,
            created_at=datetime(2026, 3, 14, tzinfo=timezone.utc),
        )
        assert signal.platform == Platform.REDDIT
        assert signal.id is not None  # auto-generated UUID
        assert signal.collected_at is not None

    def test_opportunity_defaults(self):
        opp = Opportunity(
            title="CLI tool for X",
            description="A command-line tool that does X",
        )
        assert opp.status == "new"
        assert opp.composite_score == 0.0
        assert opp.platform_count == 0

    def test_platform_enum(self):
        assert Platform.REDDIT.value == "reddit"
        assert Platform.HACKERNEWS.value == "hackernews"
        assert Platform.GITHUB.value == "github"
        assert Platform.TWITTER.value == "twitter"
        assert Platform.PRODUCTHUNT.value == "producthunt"


class TestDatabase:
    @pytest.fixture
    def db(self, tmp_path):
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.initialize()
        return db

    def test_initialize_creates_tables(self, db):
        tables = db.list_tables()
        assert "signals" in tables
        assert "opportunities" in tables
        assert "signal_opportunities" in tables

    def test_insert_and_get_signal(self, db):
        signal = Signal(
            platform=Platform.HACKERNEWS,
            platform_id="hn_999",
            title="Show HN: My side project",
            body="I built this thing",
            url="https://news.ycombinator.com/item?id=999",
            author="hnuser",
            upvotes=200,
            comments_count=85,
            created_at=datetime(2026, 3, 14, tzinfo=timezone.utc),
        )
        db.insert_signal(signal)
        retrieved = db.get_signal_by_platform_id(Platform.HACKERNEWS, "hn_999")
        assert retrieved is not None
        assert retrieved.title == "Show HN: My side project"
        assert retrieved.upvotes == 200

    def test_duplicate_signal_skipped(self, db):
        signal = Signal(
            platform=Platform.REDDIT,
            platform_id="dup_1",
            title="Duplicate test",
            body="",
            url="https://reddit.com/dup",
            author="user",
            upvotes=10,
            comments_count=2,
            created_at=datetime(2026, 3, 14, tzinfo=timezone.utc),
        )
        db.insert_signal(signal)
        db.insert_signal(signal)  # should not raise
        signals = db.get_signals(platform=Platform.REDDIT)
        dupes = [s for s in signals if s.platform_id == "dup_1"]
        assert len(dupes) == 1

    def test_insert_and_get_opportunity(self, db):
        opp = Opportunity(
            title="CLI tool for managing X",
            description="Automates X via command line",
            category="cli-tool",
        )
        db.insert_opportunity(opp)
        retrieved = db.get_opportunities(min_score=0.0)
        assert len(retrieved) == 1
        assert retrieved[0].title == "CLI tool for managing X"

    def test_link_signal_to_opportunity(self, db):
        signal = Signal(
            platform=Platform.HACKERNEWS,
            platform_id="link_test",
            title="Show HN: CLI for X",
            body="Built it",
            url="https://hn.com/1",
            author="u",
            upvotes=50,
            comments_count=10,
            created_at=datetime(2026, 3, 14, tzinfo=timezone.utc),
        )
        opp = Opportunity(title="CLI for X", description="Does X")
        db.insert_signal(signal)
        db.insert_opportunity(opp)
        db.link_signal_opportunity(signal.id, opp.id)
        linked = db.get_signals_for_opportunity(opp.id)
        assert len(linked) == 1
        assert linked[0].platform_id == "link_test"

    def test_query_opportunities_filters(self, db):
        opp1 = Opportunity(title="High score", description="Good", composite_score=0.8, platform_count=3)
        opp2 = Opportunity(title="Low score", description="Bad", composite_score=0.2, platform_count=1)
        db.insert_opportunity(opp1)
        db.insert_opportunity(opp2)
        results = db.get_opportunities(min_score=0.5, min_platforms=2)
        assert len(results) == 1
        assert results[0].title == "High score"

    def test_get_signals_for_scoring(self, db):
        """Signals without linked opportunities should be returned for scoring."""
        signal = Signal(
            platform=Platform.REDDIT,
            platform_id="unscored_1",
            title="Unscored signal",
            body="Needs scoring",
            url="https://reddit.com/1",
            author="u",
            upvotes=100,
            comments_count=20,
            created_at=datetime(2026, 3, 14, tzinfo=timezone.utc),
        )
        db.insert_signal(signal)
        unscored = db.get_unlinked_signals()
        assert len(unscored) >= 1

    def test_update_opportunity_scores(self, db):
        opp = Opportunity(title="Update test", description="Test")
        db.insert_opportunity(opp)
        opp.engagement_score = 0.7
        opp.cross_platform_score = 0.9
        opp.feasibility_score = 0.6
        opp.composite_score = 0.77
        db.update_opportunity(opp)
        retrieved = db.get_opportunities(min_score=0.0)
        match = [o for o in retrieved if o.title == "Update test"]
        assert match[0].composite_score == pytest.approx(0.77)
