"""Data models for signals and opportunities."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Platform(str, Enum):
    REDDIT = "reddit"
    HACKERNEWS = "hackernews"
    GITHUB = "github"
    TWITTER = "twitter"
    PRODUCTHUNT = "producthunt"


class Signal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    platform: Platform
    platform_id: str
    title: str
    body: str = ""
    url: str = ""
    author: str = ""
    upvotes: int = 0
    comments_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_json: str = ""
    metadata: dict = Field(default_factory=dict)


class Opportunity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str = ""
    category: str = "other"
    engagement_score: float = 0.0
    cross_platform_score: float = 0.0
    feasibility_score: float = 0.0
    composite_score: float = 0.0
    platform_count: int = 0
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "new"
    llm_analysis: Optional[str] = None
