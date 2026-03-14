# Opportunity Matrix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python CLI that scrapes Reddit, HN, GitHub, and X/Twitter for software opportunity signals, scores them by engagement/cross-platform validation/feasibility, and stores results in SQLite for querying.

**Architecture:** Monolithic Python CLI (`om`) with async collectors, a three-axis scoring engine, and SQLite storage. Deploys to Oracle Cloud as a Zeroclaw skill invoked on cron. Each platform collector runs concurrently via asyncio.gather().

**Tech Stack:** Python 3.11+, httpx (async HTTP), Typer (CLI), Pydantic (config/models), SQLite (stdlib), scikit-learn (TF-IDF matching)

**Design doc:** `docs/plans/2026-03-14-opportunity-matrix-design.md`

---

## Task 1: Project Scaffold + Initial Commit

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `CLAUDE.md`
- Create: `config.yaml`
- Create: `opportunity_matrix/__init__.py`
- Create: `opportunity_matrix/__main__.py`
- Create: `tests/__init__.py`

**Step 1: Clone the empty repo**

```bash
cd /c/Users/OmarAl-Bakri
git clone https://github.com/OmarA1-Bakri-Org/Opportunity-Matrix-.git
cd Opportunity-Matrix-
git checkout -b feature/initial-scaffold
```

**Step 2: Create pyproject.toml**

```toml
[project]
name = "opportunity-matrix"
version = "0.1.0"
description = "Real-time market intelligence for solo-developer software opportunities"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "typer>=0.12",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "pyyaml>=6.0",
    "scikit-learn>=1.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "respx>=0.21",
]

[project.scripts]
om = "opportunity_matrix.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.env
*.db
*.sqlite
.mcp/tool-results/
.venv/
dist/
*.egg-info/
.pytest_cache/
.coverage
```

**Step 4: Create .env.example**

```bash
# Reddit OAuth (script app)
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USERNAME=
REDDIT_PASSWORD=

# GitHub Personal Access Token
GITHUB_TOKEN=

# Rube MCP (for X/Twitter)
RUBE_MCP=https://rube.app/mcp
RUBE_TOKEN=

# LLM (for feasibility scoring - optional)
LLM_API_KEY=
LLM_MODEL=
```

**Step 5: Create config.yaml**

```yaml
collectors:
  reddit:
    enabled: true
    subreddits:
      - SaaS
      - sideproject
      - startups
      - indiehackers
      - webdev
      - programming
      - selfhosted
      - Entrepreneur
    frequency_hours: 6
    max_results_per_sub: 50

  hackernews:
    enabled: true
    feeds:
      - showstories
      - askstories
    frequency_hours: 2
    algolia_search: true
    max_results: 200

  github:
    enabled: true
    frequency_hours: 12
    languages:
      - python
      - typescript
      - javascript
      - go
      - rust
    min_stars: 10
    max_results: 100

  twitter:
    enabled: false  # blocked: client-not-enrolled
    frequency_hours: 6
    max_results: 100

  producthunt:
    enabled: false  # deferred: needs OAuth app
    frequency_hours: 24

keywords:
  pain_points:
    - "I wish there was"
    - "looking for a tool"
    - "frustrated with"
    - "anyone built"
    - "need a solution"
    - "pain point"
    - "hate using"
    - "why is there no"

  launches:
    - "Show HN"
    - "just launched"
    - "side project"
    - "open source alternative"
    - "built this"
    - "weekend project"
    - "my first SaaS"

  gaps:
    - "no good solution"
    - "why isn't there"
    - "someone should build"
    - "missing from"
    - "gap in the market"
    - "underserved"

scoring:
  weights:
    engagement: 0.25
    cross_platform: 0.45
    feasibility: 0.30

  feasibility_rules:
    boosters:
      - pattern: "API wrapper"
        score: 0.3
      - pattern: "CLI tool"
        score: 0.3
      - pattern: "browser extension"
        score: 0.3
      - pattern: "Chrome extension"
        score: 0.2
      - pattern: "VS Code extension"
        score: 0.2
      - pattern: "open source alternative"
        score: 0.2
    penalties:
      - pattern: "enterprise"
        score: -0.3
      - pattern: "requires team"
        score: -0.3
      - pattern: "ML infrastructure"
        score: -0.3
      - pattern: "regulatory"
        score: -0.4
      - pattern: "compliance"
        score: -0.4
      - pattern: "healthcare"
        score: -0.4

  llm:
    enabled: false  # enable when LLM_API_KEY is set
    min_feasibility: 0.6
    min_composite: 0.5

cross_platform:
  similarity_threshold: 0.65
  recency_window_hours: 168  # 7 days
  high_recency_hours: 48
```

**Step 6: Create CLAUDE.md**

Copy the mcp2cli tenants from Omar's CLAUDE.md template (the content he shared from Downloads). Add project-specific section at top:

```markdown
# Opportunity Matrix

## Project Overview
Real-time market intelligence CLI. See `docs/plans/2026-03-14-opportunity-matrix-design.md` for full architecture.

## Quick Reference
- `om scan` — run collectors
- `om score` — score signals
- `om query` — query opportunities
- `om report` — generate digest
- `om status` — health check
- Tests: `pytest`
- Install: `pip install -e ".[dev]"`

## Conventions
- Async-first: all IO uses httpx + asyncio
- Config from config.yaml, secrets from .env
- All collector failures are non-fatal (log + continue)
- TDD: tests before implementation

[... mcp2cli tenants from Omar's template ...]
```

**Step 7: Create package init files**

`opportunity_matrix/__init__.py`:
```python
"""Opportunity Matrix — market intelligence for solo developers."""

__version__ = "0.1.0"
```

`opportunity_matrix/__main__.py`:
```python
"""Allow running as `python -m opportunity_matrix`."""

from opportunity_matrix.cli import app

app()
```

`tests/__init__.py`: empty file

**Step 8: Create directory structure**

```bash
mkdir -p opportunity_matrix/collectors
mkdir -p opportunity_matrix/scoring
mkdir -p opportunity_matrix/storage
mkdir -p opportunity_matrix/reporting
mkdir -p zeroclaw
mkdir -p docs/plans
mkdir -p .claude/skills
mkdir -p .mcp/tool-results
touch opportunity_matrix/collectors/__init__.py
touch opportunity_matrix/scoring/__init__.py
touch opportunity_matrix/storage/__init__.py
touch opportunity_matrix/reporting/__init__.py
```

**Step 9: Commit**

```bash
git add -A
git commit -m "feat: scaffold project structure with config and dependencies"
```

---

## Task 2: Pydantic Models + Storage Layer

**Files:**
- Create: `opportunity_matrix/storage/models.py`
- Create: `opportunity_matrix/storage/db.py`
- Create: `tests/test_storage.py`

**Step 1: Write the failing test**

`tests/test_storage.py`:
```python
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
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_storage.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'opportunity_matrix.storage.models'`

**Step 3: Implement models.py**

`opportunity_matrix/storage/models.py`:
```python
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
```

**Step 4: Implement db.py**

`opportunity_matrix/storage/db.py`:
```python
"""SQLite database operations."""

from __future__ import annotations

import json
import sqlite3
from typing import Optional

from opportunity_matrix.storage.models import Opportunity, Platform, Signal


class Database:
    def __init__(self, db_path: str = "opportunity_matrix.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def initialize(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS signals (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT DEFAULT '',
                url TEXT DEFAULT '',
                author TEXT DEFAULT '',
                upvotes INTEGER DEFAULT 0,
                comments_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                raw_json TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                UNIQUE(platform, platform_id)
            );

            CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT 'other',
                engagement_score REAL DEFAULT 0.0,
                cross_platform_score REAL DEFAULT 0.0,
                feasibility_score REAL DEFAULT 0.0,
                composite_score REAL DEFAULT 0.0,
                platform_count INTEGER DEFAULT 0,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                llm_analysis TEXT
            );

            CREATE TABLE IF NOT EXISTS signal_opportunities (
                signal_id TEXT NOT NULL REFERENCES signals(id),
                opportunity_id TEXT NOT NULL REFERENCES opportunities(id),
                PRIMARY KEY (signal_id, opportunity_id)
            );

            CREATE INDEX IF NOT EXISTS idx_signals_platform ON signals(platform);
            CREATE INDEX IF NOT EXISTS idx_signals_collected ON signals(collected_at);
            CREATE INDEX IF NOT EXISTS idx_opportunities_score ON opportunities(composite_score);
            CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status);
        """)

    def list_tables(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return [r["name"] for r in rows]

    def insert_signal(self, signal: Signal) -> None:
        try:
            self.conn.execute(
                """INSERT INTO signals
                   (id, platform, platform_id, title, body, url, author,
                    upvotes, comments_count, created_at, collected_at, raw_json, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    signal.id, signal.platform.value, signal.platform_id,
                    signal.title, signal.body, signal.url, signal.author,
                    signal.upvotes, signal.comments_count,
                    signal.created_at.isoformat(), signal.collected_at.isoformat(),
                    signal.raw_json, json.dumps(signal.metadata),
                ),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass  # duplicate platform+platform_id — skip silently

    def get_signal_by_platform_id(self, platform: Platform, platform_id: str) -> Optional[Signal]:
        row = self.conn.execute(
            "SELECT * FROM signals WHERE platform = ? AND platform_id = ?",
            (platform.value, platform_id),
        ).fetchone()
        return self._row_to_signal(row) if row else None

    def get_signals(self, platform: Optional[Platform] = None, days: int = 30) -> list[Signal]:
        query = "SELECT * FROM signals WHERE 1=1"
        params: list = []
        if platform:
            query += " AND platform = ?"
            params.append(platform.value)
        query += " ORDER BY collected_at DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_signal(r) for r in rows]

    def get_unlinked_signals(self) -> list[Signal]:
        rows = self.conn.execute(
            """SELECT s.* FROM signals s
               LEFT JOIN signal_opportunities so ON s.id = so.signal_id
               WHERE so.signal_id IS NULL
               ORDER BY s.collected_at DESC"""
        ).fetchall()
        return [self._row_to_signal(r) for r in rows]

    def insert_opportunity(self, opp: Opportunity) -> None:
        self.conn.execute(
            """INSERT INTO opportunities
               (id, title, description, category, engagement_score, cross_platform_score,
                feasibility_score, composite_score, platform_count, first_seen, last_seen,
                status, llm_analysis)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                opp.id, opp.title, opp.description, opp.category,
                opp.engagement_score, opp.cross_platform_score,
                opp.feasibility_score, opp.composite_score,
                opp.platform_count, opp.first_seen.isoformat(),
                opp.last_seen.isoformat(), opp.status, opp.llm_analysis,
            ),
        )
        self.conn.commit()

    def update_opportunity(self, opp: Opportunity) -> None:
        self.conn.execute(
            """UPDATE opportunities SET
               title=?, description=?, category=?, engagement_score=?,
               cross_platform_score=?, feasibility_score=?, composite_score=?,
               platform_count=?, first_seen=?, last_seen=?, status=?, llm_analysis=?
               WHERE id=?""",
            (
                opp.title, opp.description, opp.category,
                opp.engagement_score, opp.cross_platform_score,
                opp.feasibility_score, opp.composite_score,
                opp.platform_count, opp.first_seen.isoformat(),
                opp.last_seen.isoformat(), opp.status, opp.llm_analysis,
                opp.id,
            ),
        )
        self.conn.commit()

    def get_opportunities(
        self,
        min_score: float = 0.0,
        min_platforms: int = 0,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[Opportunity]:
        query = "SELECT * FROM opportunities WHERE composite_score >= ? AND platform_count >= ?"
        params: list = [min_score, min_platforms]
        if category:
            query += " AND category = ?"
            params.append(category)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY composite_score DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_opportunity(r) for r in rows]

    def link_signal_opportunity(self, signal_id: str, opportunity_id: str) -> None:
        try:
            self.conn.execute(
                "INSERT INTO signal_opportunities (signal_id, opportunity_id) VALUES (?, ?)",
                (signal_id, opportunity_id),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def get_signals_for_opportunity(self, opportunity_id: str) -> list[Signal]:
        rows = self.conn.execute(
            """SELECT s.* FROM signals s
               JOIN signal_opportunities so ON s.id = so.signal_id
               WHERE so.opportunity_id = ?""",
            (opportunity_id,),
        ).fetchall()
        return [self._row_to_signal(r) for r in rows]

    def get_signal_count(self, platform: Optional[Platform] = None) -> int:
        if platform:
            row = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM signals WHERE platform = ?",
                (platform.value,),
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) as cnt FROM signals").fetchone()
        return row["cnt"]

    def _row_to_signal(self, row: sqlite3.Row) -> Signal:
        return Signal(
            id=row["id"],
            platform=Platform(row["platform"]),
            platform_id=row["platform_id"],
            title=row["title"],
            body=row["body"],
            url=row["url"],
            author=row["author"],
            upvotes=row["upvotes"],
            comments_count=row["comments_count"],
            created_at=row["created_at"],
            collected_at=row["collected_at"],
            raw_json=row["raw_json"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def _row_to_opportunity(self, row: sqlite3.Row) -> Opportunity:
        return Opportunity(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            category=row["category"],
            engagement_score=row["engagement_score"],
            cross_platform_score=row["cross_platform_score"],
            feasibility_score=row["feasibility_score"],
            composite_score=row["composite_score"],
            platform_count=row["platform_count"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            status=row["status"],
            llm_analysis=row["llm_analysis"],
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
```

**Step 5: Run tests to verify they pass**

```bash
pip install -e ".[dev]"
pytest tests/test_storage.py -v
```
Expected: All PASS

**Step 6: Commit**

```bash
git add opportunity_matrix/storage/ tests/test_storage.py
git commit -m "feat: add Pydantic models and SQLite storage layer with full CRUD"
```

---

## Task 3: Config Layer

**Files:**
- Create: `opportunity_matrix/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

`tests/test_config.py`:
```python
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
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```
Expected: FAIL

**Step 3: Implement config.py**

`opportunity_matrix/config.py`:
```python
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
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```
Expected: All PASS

**Step 5: Commit**

```bash
git add opportunity_matrix/config.py tests/test_config.py
git commit -m "feat: add config layer — YAML for app config, env vars for secrets"
```

---

## Task 4: Base Collector + Hacker News Collector

**Files:**
- Create: `opportunity_matrix/collectors/base.py`
- Create: `opportunity_matrix/collectors/hackernews.py`
- Create: `tests/test_collectors.py`

**Step 1: Write the failing test**

`tests/test_collectors.py`:
```python
"""Tests for collectors."""

import pytest
import httpx
import respx
from opportunity_matrix.collectors.base import BaseCollector
from opportunity_matrix.collectors.hackernews import HackerNewsCollector
from opportunity_matrix.config import HackerNewsConfig, KeywordsConfig
from opportunity_matrix.storage.models import Platform


class TestBaseCollector:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseCollector()


class TestHackerNewsCollector:
    @pytest.fixture
    def hn_config(self):
        return HackerNewsConfig(
            enabled=True,
            feeds=["showstories"],
            max_results=5,
        )

    @pytest.fixture
    def keywords(self):
        return KeywordsConfig(
            pain_points=["I wish there was"],
            launches=["Show HN"],
            gaps=[],
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_collect_show_hn(self, hn_config, keywords):
        # Mock the showstories endpoint
        respx.get("https://hacker-news.firebaseio.com/v0/showstories.json").respond(
            json=[100, 101, 102]
        )
        # Mock individual items
        respx.get("https://hacker-news.firebaseio.com/v0/item/100.json").respond(
            json={
                "id": 100,
                "type": "story",
                "title": "Show HN: My CLI tool for developers",
                "text": "I built this because I wish there was a better option",
                "url": "https://example.com/tool",
                "by": "testuser",
                "score": 150,
                "descendants": 42,
                "time": 1710374400,
            }
        )
        respx.get("https://hacker-news.firebaseio.com/v0/item/101.json").respond(
            json={
                "id": 101,
                "type": "story",
                "title": "Unrelated post about cooking",
                "text": "Best recipe for pasta",
                "url": "https://example.com/pasta",
                "by": "chef",
                "score": 5,
                "descendants": 2,
                "time": 1710374400,
            }
        )
        respx.get("https://hacker-news.firebaseio.com/v0/item/102.json").respond(
            json={
                "id": 102,
                "type": "story",
                "title": "Show HN: Open source alternative to Notion",
                "text": "Built over the weekend",
                "url": "https://example.com/notion-alt",
                "by": "builder",
                "score": 300,
                "descendants": 85,
                "time": 1710374400,
            }
        )

        collector = HackerNewsCollector(hn_config, keywords)
        signals = await collector.collect()

        # Should return signals (keyword filtering may or may not reduce count
        # depending on implementation — at minimum the Show HN posts match)
        assert len(signals) >= 1
        assert all(s.platform == Platform.HACKERNEWS for s in signals)
        show_hn = [s for s in signals if "CLI tool" in s.title]
        assert len(show_hn) == 1
        assert show_hn[0].upvotes == 150
        assert show_hn[0].comments_count == 42

    @respx.mock
    @pytest.mark.asyncio
    async def test_collect_handles_api_error(self, hn_config, keywords):
        respx.get("https://hacker-news.firebaseio.com/v0/showstories.json").respond(
            status_code=500
        )
        collector = HackerNewsCollector(hn_config, keywords)
        signals = await collector.collect()
        assert signals == []  # graceful failure

    @pytest.mark.asyncio
    async def test_health_check(self, hn_config, keywords):
        collector = HackerNewsCollector(hn_config, keywords)
        # Real HTTP call — just verifies the endpoint is reachable
        healthy = await collector.health_check()
        assert isinstance(healthy, bool)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_collectors.py -v
```
Expected: FAIL

**Step 3: Implement base.py**

`opportunity_matrix/collectors/base.py`:
```python
"""Abstract base class for all collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from opportunity_matrix.storage.models import Signal


class BaseCollector(ABC):
    @abstractmethod
    async def collect(self) -> list[Signal]:
        """Collect signals from the platform. Returns empty list on failure."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the platform API is reachable."""
        ...
```

**Step 4: Implement hackernews.py**

`opportunity_matrix/collectors/hackernews.py`:
```python
"""Hacker News collector — Firebase API + keyword filtering."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from opportunity_matrix.collectors.base import BaseCollector
from opportunity_matrix.config import HackerNewsConfig, KeywordsConfig
from opportunity_matrix.storage.models import Platform, Signal

logger = logging.getLogger(__name__)

HN_BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsCollector(BaseCollector):
    def __init__(self, config: HackerNewsConfig, keywords: KeywordsConfig):
        self.config = config
        self.keywords = keywords

    async def collect(self) -> list[Signal]:
        signals: list[Signal] = []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                for feed in self.config.feeds:
                    feed_signals = await self._collect_feed(client, feed)
                    signals.extend(feed_signals)
        except Exception as e:
            logger.error(f"HN collection failed: {e}")
        return signals

    async def _collect_feed(self, client: httpx.AsyncClient, feed: str) -> list[Signal]:
        try:
            resp = await client.get(f"{HN_BASE}/{feed}.json")
            resp.raise_for_status()
            item_ids = resp.json()
        except (httpx.HTTPError, Exception) as e:
            logger.error(f"HN feed {feed} failed: {e}")
            return []

        item_ids = item_ids[: self.config.max_results]

        # Fetch items concurrently in batches of 20
        signals: list[Signal] = []
        for batch_start in range(0, len(item_ids), 20):
            batch = item_ids[batch_start : batch_start + 20]
            tasks = [self._fetch_item(client, item_id) for item_id in batch]
            items = await asyncio.gather(*tasks, return_exceptions=True)
            for item in items:
                if isinstance(item, Signal):
                    signals.append(item)

        return signals

    async def _fetch_item(self, client: httpx.AsyncClient, item_id: int) -> Signal | None:
        try:
            resp = await client.get(f"{HN_BASE}/item/{item_id}.json")
            resp.raise_for_status()
            data = resp.json()
            if not data or data.get("type") != "story":
                return None

            title = data.get("title", "")
            text = data.get("text", "")
            content = f"{title} {text}".lower()

            # Check if any keyword matches
            all_keywords = self.keywords.all_keywords
            if all_keywords and not any(kw.lower() in content for kw in all_keywords):
                return None

            return Signal(
                platform=Platform.HACKERNEWS,
                platform_id=str(data["id"]),
                title=title,
                body=text,
                url=data.get("url", f"https://news.ycombinator.com/item?id={data['id']}"),
                author=data.get("by", ""),
                upvotes=data.get("score", 0),
                comments_count=data.get("descendants", 0),
                created_at=datetime.fromtimestamp(data.get("time", 0), tz=timezone.utc),
                raw_json=str(data),
                metadata={"feed": "showstories" if "Show HN" in title else "askstories"},
            )
        except Exception as e:
            logger.warning(f"HN item {item_id} failed: {e}")
            return None

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{HN_BASE}/topstories.json")
                return resp.status_code == 200
        except Exception:
            return False
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/test_collectors.py -v
```
Expected: All PASS

**Step 6: Commit**

```bash
git add opportunity_matrix/collectors/ tests/test_collectors.py
git commit -m "feat: add base collector + Hacker News collector with keyword filtering"
```

---

## Task 5: Reddit Collector

**Files:**
- Create: `opportunity_matrix/collectors/reddit.py`
- Modify: `tests/test_collectors.py` (add Reddit tests)

**Step 1: Write the failing test**

Append to `tests/test_collectors.py`:
```python
from opportunity_matrix.collectors.reddit import RedditCollector
from opportunity_matrix.config import RedditConfig


class TestRedditCollector:
    @pytest.fixture
    def reddit_config(self):
        return RedditConfig(
            enabled=True,
            subreddits=["SaaS", "sideproject"],
            max_results_per_sub=5,
        )

    @pytest.fixture
    def keywords(self):
        return KeywordsConfig(
            pain_points=["I wish there was"],
            launches=["just launched"],
            gaps=[],
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_collect_from_subreddits(self, reddit_config, keywords):
        # Mock OAuth token
        respx.post("https://www.reddit.com/api/v1/access_token").respond(
            json={"access_token": "test_token", "token_type": "bearer", "expires_in": 3600}
        )
        # Mock subreddit listing
        respx.get("https://oauth.reddit.com/r/SaaS/new").respond(
            json={
                "data": {
                    "children": [
                        {
                            "data": {
                                "id": "r1",
                                "title": "I wish there was a better invoicing tool",
                                "selftext": "Current options are terrible",
                                "url": "https://reddit.com/r/SaaS/r1",
                                "author": "redditor1",
                                "ups": 85,
                                "num_comments": 30,
                                "created_utc": 1710374400,
                                "subreddit": "SaaS",
                                "permalink": "/r/SaaS/comments/r1/test/",
                            }
                        }
                    ]
                }
            }
        )
        respx.get("https://oauth.reddit.com/r/sideproject/new").respond(
            json={"data": {"children": []}}
        )

        collector = RedditCollector(
            reddit_config, keywords,
            client_id="test_id", client_secret="test_secret",
            username="test_user", password="test_pass",
        )
        signals = await collector.collect()

        assert len(signals) >= 1
        assert signals[0].platform == Platform.REDDIT
        assert "invoicing" in signals[0].title
        assert signals[0].upvotes == 85

    @respx.mock
    @pytest.mark.asyncio
    async def test_collect_handles_auth_failure(self, reddit_config, keywords):
        respx.post("https://www.reddit.com/api/v1/access_token").respond(status_code=401)

        collector = RedditCollector(
            reddit_config, keywords,
            client_id="bad", client_secret="bad",
            username="bad", password="bad",
        )
        signals = await collector.collect()
        assert signals == []
```

**Step 2: Run tests, verify fail, implement, verify pass, commit**

Implement `opportunity_matrix/collectors/reddit.py` with OAuth token fetch, subreddit iteration, keyword filtering. Follow the same async pattern as HN.

```bash
git commit -m "feat: add Reddit collector with OAuth and keyword filtering"
```

---

## Task 6: GitHub Collector

**Files:**
- Create: `opportunity_matrix/collectors/github_trending.py`
- Modify: `tests/test_collectors.py` (add GitHub tests)

Same TDD cycle. GitHub collector uses REST search API with keyword queries, authenticated via personal token. Extracts: repo name, description, stars, forks, open issues, language, topics.

```bash
git commit -m "feat: add GitHub collector with search API and star tracking"
```

---

## Task 7: Twitter Collector (Stub)

**Files:**
- Create: `opportunity_matrix/collectors/twitter.py`
- Modify: `tests/test_collectors.py` (add Twitter tests)

Implement as a stub that checks `config.twitter.enabled` and returns `[]` if disabled. When enabled, it would call Rube MCP's `TWITTER_RECENT_SEARCH` via subprocess (mcp2cli). Tests verify the disabled path and mock the enabled path.

```bash
git commit -m "feat: add Twitter collector stub (blocked on API enrollment)"
```

---

## Task 8: Engagement Scorer

**Files:**
- Create: `opportunity_matrix/scoring/engagement.py`
- Create: `tests/test_scoring.py`

**Step 1: Write the failing test**

`tests/test_scoring.py`:
```python
"""Tests for scoring engine."""

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
        # Without historical data, should use default p90
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
        # After calibration, median-ish signal should score ~0.5
        mid_signal = signals[50]
        score = scorer.score(mid_signal)
        assert 0.3 <= score <= 0.8
```

**Step 2-5: Standard TDD cycle**

Implement `EngagementScorer` with per-platform normalization formulas from the design doc. Default p90 values for cold start, updated from real data via `update_percentiles()`.

```bash
git commit -m "feat: add engagement scorer with auto-calibrating percentiles"
```

---

## Task 9: Cross-Platform Scorer

**Files:**
- Create: `opportunity_matrix/scoring/cross_platform.py`
- Modify: `tests/test_scoring.py` (add cross-platform tests)

Implement TF-IDF cosine similarity for entity matching across platforms. Group signals into clusters, score by platform count weighted by recency.

Tests:
- Two signals from different platforms with similar titles → high score
- Signals from same platform → not counted as cross-platform
- Older signals weighted less than recent ones
- Score mapping: 1 platform = 0.2, 2 = 0.5, 3 = 0.8, 4 = 1.0

```bash
git commit -m "feat: add cross-platform scorer with TF-IDF entity matching"
```

---

## Task 10: Feasibility Scorer

**Files:**
- Create: `opportunity_matrix/scoring/feasibility.py`
- Modify: `tests/test_scoring.py` (add feasibility tests)

Implement rule-based scoring with pattern matching from config.yaml. LLM path as a stub (returns rule-based score when LLM disabled).

Tests:
- Signal mentioning "CLI tool" → boosted
- Signal mentioning "enterprise" → penalized
- Base score = 0.5, clamped to [0.0, 1.0]
- Multiple rules stack correctly

```bash
git commit -m "feat: add feasibility scorer with rule-based patterns and LLM stub"
```

---

## Task 11: CLI Interface

**Files:**
- Create: `opportunity_matrix/cli.py`
- Modify: `opportunity_matrix/__main__.py`

Implement Typer CLI with commands: `scan`, `score`, `query`, `report`, `status`. Each command wires together the appropriate collectors, scorers, and database operations.

Tests: Use Typer's `CliRunner` to verify each command produces expected output.

```bash
git commit -m "feat: add Typer CLI with scan/score/query/report/status commands"
```

---

## Task 12: Report Generator

**Files:**
- Create: `opportunity_matrix/reporting/digest.py`
- Create: `tests/test_reporting.py`

Generates markdown or JSON digest of top opportunities. Includes: title, composite score breakdown, platform sources, first/last seen, category.

```bash
git commit -m "feat: add report generator for markdown and JSON digest output"
```

---

## Task 13: Zeroclaw Skill Manifest

**Files:**
- Create: `zeroclaw/skill.toml`

```toml
[skill]
name = "opportunity-matrix"
description = "Scan social platforms for validated software opportunities"
version = "0.1.0"

[[tools]]
name = "scan"
command = "cd /opt/opportunity-matrix && python -m opportunity_matrix scan"
description = "Run all collectors, score results, store in SQLite"

[[tools]]
name = "scan-source"
command = "cd /opt/opportunity-matrix && python -m opportunity_matrix scan --source {source}"
description = "Scan a single source (reddit, hn, github, twitter)"

[[tools]]
name = "report"
command = "cd /opt/opportunity-matrix && python -m opportunity_matrix report --format md --top 10"
description = "Generate top-10 opportunities digest in markdown"

[[tools]]
name = "query"
command = "cd /opt/opportunity-matrix && python -m opportunity_matrix query --min-score {min_score} --days {days}"
description = "Query stored opportunities with filters"

[[tools]]
name = "status"
command = "cd /opt/opportunity-matrix && python -m opportunity_matrix status"
description = "Show collector health, signal counts, last scan times"
```

```bash
git commit -m "feat: add Zeroclaw skill manifest for cron-driven scanning"
```

---

## Task 14: Integration Test + Final Polish

**Files:**
- Create: `tests/test_integration.py`

End-to-end test: create DB → insert mock signals from 2 platforms with similar titles → run scoring pipeline → verify cross-platform detection → verify composite score → verify query returns results.

```bash
git commit -m "test: add integration test for full scan-score-query pipeline"
```

---

## Execution Order

Tasks 1-3 are sequential (scaffold → storage → config — each depends on the previous).

Tasks 4-7 can be parallelized (each collector is independent).

Tasks 8-10 can be parallelized (each scorer is independent).

Tasks 11-12 depend on 1-10 (CLI wires everything together).

Task 13 is independent (just a TOML file).

Task 14 depends on everything.

```
[1] → [2] → [3] → [4,5,6,7] → [8,9,10] → [11,12] → [13] → [14]
                   (parallel)    (parallel)   (parallel)
```
