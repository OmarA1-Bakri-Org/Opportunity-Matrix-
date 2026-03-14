"""Configuration from config.yaml + environment variables."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# --- Environment secrets ---

class Settings(BaseSettings):
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_username: str = ""
    reddit_password: str = ""
    github_token: str = ""
    rube_mcp: str = "https://rube.app/mcp"
    rube_token: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    db_path: str = "opportunity_matrix.db"

    model_config = {"env_file": ".env", "extra": "ignore"}


# --- YAML config models ---

class RedditConfig(BaseModel):
    enabled: bool = True
    subreddits: list[str] = Field(default_factory=list)
    frequency_hours: int = 6
    max_results_per_sub: int = 50

class HackerNewsConfig(BaseModel):
    enabled: bool = True
    feeds: list[str] = Field(default_factory=lambda: ["showstories", "askstories"])
    frequency_hours: int = 2
    algolia_search: bool = True
    max_results: int = 200

class GitHubConfig(BaseModel):
    enabled: bool = True
    frequency_hours: int = 12
    languages: list[str] = Field(default_factory=list)
    min_stars: int = 10
    max_results: int = 100

class TwitterConfig(BaseModel):
    enabled: bool = False
    frequency_hours: int = 6
    max_results: int = 100

class ProductHuntConfig(BaseModel):
    enabled: bool = False
    frequency_hours: int = 24

class CollectorsConfig(BaseModel):
    reddit: RedditConfig = Field(default_factory=RedditConfig)
    hackernews: HackerNewsConfig = Field(default_factory=HackerNewsConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    twitter: TwitterConfig = Field(default_factory=TwitterConfig)
    producthunt: ProductHuntConfig = Field(default_factory=ProductHuntConfig)

class KeywordsConfig(BaseModel):
    pain_points: list[str] = Field(default_factory=list)
    launches: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)

    @property
    def all_keywords(self) -> list[str]:
        return self.pain_points + self.launches + self.gaps

class ScoringWeights(BaseModel):
    engagement: float = 0.25
    cross_platform: float = 0.45
    feasibility: float = 0.30

class FeasibilityRule(BaseModel):
    pattern: str
    score: float

class FeasibilityRules(BaseModel):
    boosters: list[FeasibilityRule] = Field(default_factory=list)
    penalties: list[FeasibilityRule] = Field(default_factory=list)

class LLMConfig(BaseModel):
    enabled: bool = False
    min_feasibility: float = 0.6
    min_composite: float = 0.5

class ScoringConfig(BaseModel):
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    feasibility_rules: FeasibilityRules = Field(default_factory=FeasibilityRules)
    llm: LLMConfig = Field(default_factory=LLMConfig)

class CrossPlatformConfig(BaseModel):
    similarity_threshold: float = 0.65
    recency_window_hours: int = 168
    high_recency_hours: int = 48

class AppConfig(BaseModel):
    collectors: CollectorsConfig = Field(default_factory=CollectorsConfig)
    keywords: KeywordsConfig = Field(default_factory=KeywordsConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    cross_platform: CrossPlatformConfig = Field(default_factory=CrossPlatformConfig)


def load_config(config_path: str = "config.yaml") -> AppConfig:
    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return AppConfig(**data)
    return AppConfig()
