"""Tests for CLI interface."""

import pytest
from typer.testing import CliRunner
from opportunity_matrix.cli import app

runner = CliRunner()


class TestCLI:
    def test_status_command(self, tmp_path):
        result = runner.invoke(app, ["status", "--db-path", str(tmp_path / "test.db")])
        assert result.exit_code == 0
        assert "Opportunity Matrix" in result.stdout or "Status" in result.stdout or "signals" in result.stdout.lower()

    def test_query_command_empty_db(self, tmp_path):
        result = runner.invoke(app, ["query", "--db-path", str(tmp_path / "test.db")])
        assert result.exit_code == 0
        # Empty DB should show no results or a message
        assert "0" in result.stdout or "No" in result.stdout or "opportunities" in result.stdout.lower()

    def test_report_command_empty_db(self, tmp_path):
        result = runner.invoke(app, ["report", "--db-path", str(tmp_path / "test.db"), "--format", "md"])
        assert result.exit_code == 0

    def test_scan_dry_run(self, tmp_path):
        result = runner.invoke(app, ["scan", "--dry-run", "--db-path", str(tmp_path / "test.db")])
        assert result.exit_code == 0
        assert "dry" in result.stdout.lower() or "would" in result.stdout.lower() or "scan" in result.stdout.lower()
