"""Tests for configuration loading."""

import pytest
from opportunity_matrix.config import Settings, load_config


class TestConfig:
    def test_load_config_from_yaml(self, tmp_path):
        yaml_content = """
collectors:
  reddit:
    enabled: true
    subreddits: ["SaaS", "sideproject"]
    frequency_hours: 6
    max_results_per_sub: 50
  hackernews:
    enabled: true
    feeds: ["showstories"]
    frequency_hours: 2
keywords:
  pain_points: ["I wish there was"]
scoring:
  weights:
    engagement: 0.25
    cross_platform: 0.45
    feasibility: 0.30
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)
        config = load_config(str(config_file))
        assert config.collectors.reddit.enabled is True
        assert "SaaS" in config.collectors.reddit.subreddits
        assert config.scoring.weights.engagement == 0.25

    def test_settings_from_env(self, monkeypatch):
        monkeypatch.setenv("REDDIT_CLIENT_ID", "test_id")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "test_secret")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        settings = Settings()
        assert settings.reddit_client_id == "test_id"
        assert settings.github_token == "ghp_test"

    def test_settings_defaults(self):
        settings = Settings()
        assert settings.db_path == "opportunity_matrix.db"
