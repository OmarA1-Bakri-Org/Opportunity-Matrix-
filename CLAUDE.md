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
