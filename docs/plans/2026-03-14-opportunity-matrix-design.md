# Opportunity Matrix — Architecture Design

**Date**: 2026-03-14
**Status**: Approved
**Repo**: https://github.com/OmarA1-Bakri-Org/Opportunity-Matrix-

## Overview

A real-time market intelligence platform that monitors Reddit, X/Twitter, Product Hunt, GitHub, and Hacker News to surface validated software opportunities scored by engagement, cross-platform validation, and solo-developer feasibility.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python-only | Plays to existing skills, simple deployment, path to dashboard later |
| Storage | SQLite | Zero-ops, single file, deploys cleanly to Oracle Cloud alongside Zeroclaw |
| Architecture | Monolithic CLI | 4-5 sources don't justify plugin complexity. Clean module structure inside a monolith |
| Data collection | Mixed API approach | Reddit/HN/GitHub via direct APIs, X/Twitter via Rube MCP, Product Hunt deferred |
| Scoring | Hybrid (rules + LLM) | Rules filter cheaply, LLM refines top 20% for nuanced judgment |
| Output | Queryable SQLite + CLI | Foundation layer. Zeroclaw layers digest formatting on top as separate skill |
| Deployment | Oracle Cloud terminal | Alongside Zeroclaw agent. OM becomes a Zeroclaw skill |
| Dev workflow | mcp2cli conventions | Documentation-first, skills in .claude/skills/, context window hygiene |

## Data Model

### signals — raw data from each platform

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (UUID) | Primary key |
| platform | TEXT | reddit / hackernews / github / twitter / producthunt |
| platform_id | TEXT | Native ID from the source |
| title | TEXT | Post/tweet/repo title |
| body | TEXT | Full text content |
| url | TEXT | Permalink |
| author | TEXT | Username |
| upvotes | INTEGER | Platform-native engagement metric |
| comments_count | INTEGER | Comment/reply count |
| created_at | DATETIME | When posted on the platform |
| collected_at | DATETIME | When we scraped it |
| raw_json | TEXT | Full API response for replay |
| metadata | TEXT (JSON) | Platform-specific fields (subreddit, stars, forks, etc.) |

### opportunities — deduplicated, scored entities

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (UUID) | Primary key |
| title | TEXT | Normalized opportunity name |
| description | TEXT | What the opportunity is |
| category | TEXT | api-wrapper / cli-tool / browser-ext / saas / library / other |
| engagement_score | REAL | 0.0-1.0 normalized |
| cross_platform_score | REAL | 0.0-1.0 based on platform count + recency |
| feasibility_score | REAL | 0.0-1.0 hybrid (rules + LLM) |
| composite_score | REAL | Weighted combination |
| platform_count | INTEGER | How many platforms mention this |
| first_seen | DATETIME | Earliest signal |
| last_seen | DATETIME | Most recent signal |
| status | TEXT | new / reviewed / archived / building |
| llm_analysis | TEXT | LLM feasibility rationale (when scored) |

### signal_opportunities — junction table (many-to-many)

| Column | Type | Description |
|--------|------|-------------|
| signal_id | TEXT FK | Links to signals |
| opportunity_id | TEXT FK | Links to opportunities |

## Collectors

Each collector inherits from `BaseCollector`, runs async, returns `list[Signal]`.

| Collector | API | Auth | Frequency |
|-----------|-----|------|-----------|
| Reddit | REST (`/r/{sub}/new`, `/search`) | OAuth 2.0 (script app) | Every 6 hours |
| Hacker News | Firebase REST + Algolia | None | Every 2 hours |
| GitHub | REST search + GraphQL metrics | Personal access token | Every 12 hours |
| X/Twitter | Rube MCP (`TWITTER_RECENT_SEARCH`) | Via Rube (once enrolled) | Every 6 hours |
| Product Hunt | GraphQL | OAuth (deferred) | TBD |

### Keyword Strategy (config.yaml, not hardcoded)

Pain points: "I wish there was", "looking for a tool", "frustrated with", "anyone built"
Launches: "Show HN", "just launched", "side project", "open source alternative"
Gaps: "no good solution", "why isn't there", "someone should build"

### Execution Model

All collectors run concurrently via `asyncio.gather()`. If one fails, others continue. Failures logged, not fatal.

## Scoring Engine

Three independent scorers producing 0.0-1.0, combined into weighted composite.

### Engagement Score

Per-platform normalization against rolling 30-day 90th percentile (auto-calibrates):
- Reddit: `min(1.0, (upvotes * 0.6 + comments * 0.4) / p90)`
- HN: `min(1.0, (points * 0.5 + comments * 0.5) / p90)`
- GitHub: `min(1.0, (stars * 0.4 + forks * 0.3 + issues * 0.3) / p90)`
- Twitter: `min(1.0, (likes * 0.4 + retweets * 0.4 + replies * 0.2) / p90)`

### Cross-Platform Score

Entity matching via keyword overlap + TF-IDF cosine similarity on title+body.

| Platforms | Score |
|-----------|-------|
| 1 | 0.2 |
| 2 | 0.5 |
| 3 | 0.8 |
| 4 | 1.0 |

Weighted by recency: signals within 48h count more than 7-day-old ones.

### Feasibility Score (Hybrid)

**Rule-based first pass (free, instant):**

| Pattern | Adjustment |
|---------|------------|
| "API wrapper", "CLI tool", "browser extension" | +0.3 |
| "Chrome extension", "VS Code extension" | +0.2 |
| "open source alternative to X" | +0.2 |
| "enterprise", "requires team", "ML infrastructure" | -0.3 |
| "regulatory", "compliance", "healthcare" | -0.4 |
| Existing competitors < 3 | +0.2 |

Base = 0.5, clamped to [0.0, 1.0].

**LLM refinement (top 20% only):**
Signals with rule-based feasibility > 0.6 AND composite > 0.5 get LLM scoring via Zeroclaw's configured model. Prompt asks for 1-10 rating + 2-sentence rationale on solo-developer feasibility for 2-4 week MVP.

### Composite Score

```
composite = (engagement * 0.25) + (cross_platform * 0.45) + (feasibility * 0.30)
```

Cross-platform gets highest weight — strongest signal that an opportunity is real.

## CLI Interface

```
om scan [--source reddit|hn|github|twitter] [--dry-run]
om score [--rescore] [--llm]
om query [--min-score 0.7] [--platforms 2] [--days 7] [--category cli-tool] [--status new]
om report [--format md|json] [--top 10]
om status
```

## Zeroclaw Integration

OM is a Zeroclaw skill. Zeroclaw invokes it via shell on a cron schedule.

Skill manifest at `zeroclaw/skill.toml`:
- `scan` tool: runs all collectors + scoring
- `report` tool: generates top-10 digest in markdown
- `query` tool: filtered opportunity lookup

Zeroclaw cron: `scan` every 6 hours, `report` once daily.

## Project Layout

```
Opportunity-Matrix-/
├── .claude/
│   └── skills/                    # mcp2cli skills for dev workflow
├── .mcp/
│   └── tool-results/              # ephemeral MCP output (gitignored)
├── docs/
│   └── plans/                     # design docs
├── opportunity_matrix/
│   ├── __init__.py
│   ├── __main__.py                # python -m entry point
│   ├── cli.py                     # Typer CLI
│   ├── config.py                  # Settings from env/yaml
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py                # BaseCollector ABC
│   │   ├── reddit.py
│   │   ├── hackernews.py
│   │   ├── github_trending.py
│   │   └── twitter.py
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── engagement.py
│   │   ├── cross_platform.py
│   │   └── feasibility.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── models.py              # dataclasses / Pydantic models
│   │   └── db.py                  # SQLite operations
│   └── reporting/
│       ├── __init__.py
│       └── digest.py              # markdown/JSON report generation
├── zeroclaw/
│   └── skill.toml                 # Zeroclaw skill manifest
├── config.yaml                    # keywords, subreddits, scoring weights
├── .env.example                   # required env vars template
├── .gitignore
├── pyproject.toml                 # uv/pip, dependencies
├── CLAUDE.md                      # dev conventions (mcp2cli tenants)
└── tests/
    ├── test_collectors.py
    ├── test_scoring.py
    └── test_storage.py
```

## Dependencies

- httpx — async HTTP for Reddit, HN, GitHub APIs
- typer — CLI framework
- pydantic — config + data validation
- sqlite3 — stdlib
- scikit-learn — TF-IDF for cross-platform entity matching

## API Research Summary

### Reddit
- Free tier with OAuth: 60-100 req/min
- Endpoints: `/r/{subreddit}/new`, `/search`
- OAuth 2.0 script app authentication

### Hacker News
- Free, no auth, no rate limits
- Firebase REST: `/showstories`, `/askstories`, `/item/{id}.json`
- Algolia API for full-text search (10,000 req/hr)

### GitHub
- 5,000 req/hr authenticated (free personal token)
- REST search for discovery, GraphQL for batch metrics
- No native trending endpoint — use search + star velocity tracking

### X/Twitter (via Rube MCP)
- 16 tools available including `TWITTER_RECENT_SEARCH` (7-day window)
- **Blocker**: `client-not-enrolled` error — needs enrollment in Twitter Developer Portal
- Design the collector, defer activation until enrollment fixed

### Product Hunt (deferred)
- GraphQL API, OAuth required
- 6,250 complexity points per 15 min
- Add when OAuth app approved

## Known Blockers

- X/Twitter: `client-not-enrolled` — fix in Twitter Developer Portal
- Product Hunt: needs OAuth app approval
- OpenAI billing limit (for LLM scoring) — use Zeroclaw's model or Gemini instead
