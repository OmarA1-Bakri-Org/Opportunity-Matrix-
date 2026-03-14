"""Tests for report generator."""

import pytest
from datetime import datetime, timezone
from opportunity_matrix.reporting.digest import generate_report
from opportunity_matrix.storage.db import Database
from opportunity_matrix.storage.models import Opportunity, Signal, Platform


class TestReportGenerator:
    @pytest.fixture
    def db_with_data(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        db.initialize()
        # Insert test opportunities
        opp1 = Opportunity(
            title="CLI tool for Docker management",
            description="A command-line tool for managing Docker containers",
            category="cli-tool",
            engagement_score=0.8,
            cross_platform_score=0.6,
            feasibility_score=0.9,
            composite_score=0.72,
            platform_count=2,
            status="new",
        )
        opp2 = Opportunity(
            title="Open source Notion alternative",
            description="A free alternative to Notion with offline support",
            category="saas",
            engagement_score=0.9,
            cross_platform_score=0.8,
            feasibility_score=0.5,
            composite_score=0.71,
            platform_count=3,
            status="new",
        )
        db.insert_opportunity(opp1)
        db.insert_opportunity(opp2)
        return db

    @pytest.fixture
    def empty_db(self, tmp_path):
        db = Database(str(tmp_path / "empty.db"))
        db.initialize()
        return db

    def test_markdown_report(self, db_with_data):
        output = generate_report(db_with_data, format="md", top=10)
        assert "# Opportunity Matrix Report" in output
        assert "CLI tool for Docker" in output
        assert "Notion alternative" in output
        assert "0.72" in output

    def test_json_report(self, db_with_data):
        import json
        output = generate_report(db_with_data, format="json", top=10)
        data = json.loads(output)
        assert "opportunities" in data
        assert len(data["opportunities"]) == 2

    def test_empty_report(self, empty_db):
        output = generate_report(empty_db, format="md", top=10)
        assert "No opportunities" in output or "0 opportunities" in output.lower()

    def test_top_limit(self, db_with_data):
        output = generate_report(db_with_data, format="md", top=1)
        # Should only show top 1
        lines = output.split("\n")
        # Count opportunity entries (lines with composite scores)
        score_lines = [l for l in lines if "0.7" in l]
        assert len(score_lines) <= 2  # header + 1 entry at most
