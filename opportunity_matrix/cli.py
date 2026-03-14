"""Typer CLI for Opportunity Matrix."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import typer

from opportunity_matrix.config import Settings, load_config
from opportunity_matrix.storage.db import Database
from opportunity_matrix.storage.models import Platform

app = typer.Typer(name="om", help="Opportunity Matrix — market intelligence for solo developers")
logger = logging.getLogger(__name__)


def _get_db(db_path: str = "") -> Database:
    """Get database instance, initializing if needed."""
    path = db_path or Settings().db_path
    db = Database(path)
    db.initialize()
    return db


@app.command()
def scan(
    source: Optional[str] = typer.Option(None, "--source", help="Specific source: reddit, hn, github, twitter"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be scanned without running"),
    db_path: str = typer.Option("", "--db-path", help="Database path override"),
    config_path: str = typer.Option("config.yaml", "--config", help="Config file path"),
):
    """Run collectors to scan for signals."""
    config = load_config(config_path)
    settings = Settings()

    if dry_run:
        typer.echo("Dry run — would scan these sources:")
        if source:
            typer.echo(f"  - {source}")
        else:
            if config.collectors.hackernews.enabled:
                typer.echo("  - hackernews")
            if config.collectors.reddit.enabled:
                typer.echo("  - reddit")
            if config.collectors.github.enabled:
                typer.echo("  - github")
            if config.collectors.twitter.enabled:
                typer.echo("  - twitter (stub)")
        return

    db = _get_db(db_path)
    try:
        asyncio.run(_run_scan(config, settings, db, source))
    finally:
        db.close()


async def _run_scan(config, settings, db: Database, source: Optional[str] = None):
    """Run collectors and store signals."""
    from opportunity_matrix.collectors.hackernews import HackerNewsCollector
    from opportunity_matrix.collectors.reddit import RedditCollector
    from opportunity_matrix.collectors.github_trending import GitHubCollector
    from opportunity_matrix.collectors.twitter import TwitterCollector
    from opportunity_matrix.rube_client import RubeClient

    # Create shared Rube MCP client for Reddit, GitHub, and Twitter collectors
    rube = RubeClient(url=settings.rube_mcp, token=settings.rube_token) if settings.rube_token else None

    collectors = []

    if source is None or source == "hn":
        if config.collectors.hackernews.enabled:
            collectors.append(HackerNewsCollector(config.collectors.hackernews, config.keywords))

    if source is None or source == "reddit":
        if config.collectors.reddit.enabled:
            collectors.append(RedditCollector(
                config=config.collectors.reddit,
                keywords=config.keywords,
                rube=rube,
            ))

    if source is None or source == "github":
        if config.collectors.github.enabled:
            collectors.append(GitHubCollector(
                config=config.collectors.github,
                keywords=config.keywords,
                rube=rube,
            ))

    if source is None or source == "twitter":
        if config.collectors.twitter.enabled:
            collectors.append(TwitterCollector(
                config.collectors.twitter, config.keywords,
                rube_token=settings.rube_token,
            ))

    if not collectors:
        typer.echo("No collectors enabled or matched.")
        return

    import asyncio as _asyncio
    tasks = [c.collect() for c in collectors]
    results = await _asyncio.gather(*tasks, return_exceptions=True)

    total = 0
    for result in results:
        if isinstance(result, list):
            for signal in result:
                db.insert_signal(signal)
                total += 1
        elif isinstance(result, Exception):
            logger.error(f"Collector failed: {result}")

    typer.echo(f"Scan complete: {total} signals collected.")


@app.command()
def score(
    rescore: bool = typer.Option(False, "--rescore", help="Rescore all opportunities"),
    llm: bool = typer.Option(False, "--llm", help="Enable LLM scoring for top candidates"),
    db_path: str = typer.Option("", "--db-path", help="Database path override"),
    config_path: str = typer.Option("config.yaml", "--config", help="Config file path"),
):
    """Score collected signals and create/update opportunities."""
    config = load_config(config_path)
    db = _get_db(db_path)
    try:
        from opportunity_matrix.scoring.engagement import EngagementScorer
        from opportunity_matrix.scoring.cross_platform import CrossPlatformScorer
        from opportunity_matrix.scoring.feasibility import FeasibilityScorer
        from opportunity_matrix.storage.models import Opportunity

        engagement_scorer = EngagementScorer()
        cross_platform_scorer = CrossPlatformScorer(config.cross_platform)
        feasibility_scorer = FeasibilityScorer(config.scoring)

        signals = db.get_unlinked_signals() if not rescore else db.get_signals()
        if not signals:
            typer.echo("No signals to score.")
            return

        # Update engagement percentiles from all signals
        all_signals = db.get_signals()
        if len(all_signals) >= 10:
            engagement_scorer.update_percentiles(all_signals)

        # Group signals for cross-platform scoring
        groups = cross_platform_scorer.group_signals(signals)

        scored = 0
        for group in groups:
            platforms = set(s.platform for s in group)
            cross_score = cross_platform_scorer.score_group(group)

            # Use the highest-engagement signal as representative
            best_signal = max(group, key=lambda s: engagement_scorer.score(s))
            eng_score = engagement_scorer.score(best_signal)
            feas_score = feasibility_scorer.score(best_signal)

            weights = config.scoring.weights
            composite = (
                eng_score * weights.engagement
                + cross_score * weights.cross_platform
                + feas_score * weights.feasibility
            )

            opp = Opportunity(
                title=best_signal.title,
                description=best_signal.body[:500],
                engagement_score=eng_score,
                cross_platform_score=cross_score,
                feasibility_score=feas_score,
                composite_score=round(composite, 4),
                platform_count=len(platforms),
                first_seen=min(s.created_at for s in group) if group else best_signal.created_at,
                last_seen=max(s.created_at for s in group) if group else best_signal.created_at,
            )
            db.insert_opportunity(opp)

            for s in group:
                db.link_signal_opportunity(s.id, opp.id)
            scored += 1

        typer.echo(f"Scoring complete: {scored} opportunities created from {len(signals)} signals.")
    finally:
        db.close()


@app.command()
def query(
    min_score: float = typer.Option(0.0, "--min-score", help="Minimum composite score"),
    platforms: int = typer.Option(0, "--platforms", help="Minimum platform count"),
    days: int = typer.Option(30, "--days", help="Look back N days"),
    category: Optional[str] = typer.Option(None, "--category", help="Filter by category"),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
    db_path: str = typer.Option("", "--db-path", help="Database path override"),
):
    """Query stored opportunities."""
    db = _get_db(db_path)
    try:
        opps = db.get_opportunities(
            min_score=min_score,
            min_platforms=platforms,
            category=category,
            status=status,
        )
        if not opps:
            typer.echo("No opportunities found matching filters.")
            return

        typer.echo(f"Found {len(opps)} opportunities:\n")
        for opp in opps:
            typer.echo(f"  [{opp.composite_score:.2f}] {opp.title}")
            typer.echo(f"    Engagement: {opp.engagement_score:.2f} | Cross-platform: {opp.cross_platform_score:.2f} | Feasibility: {opp.feasibility_score:.2f}")
            typer.echo(f"    Platforms: {opp.platform_count} | Status: {opp.status}")
            typer.echo()
    finally:
        db.close()


@app.command()
def report(
    format: str = typer.Option("md", "--format", help="Output format: md or json"),
    top: int = typer.Option(10, "--top", help="Number of top opportunities"),
    db_path: str = typer.Option("", "--db-path", help="Database path override"),
):
    """Generate a report of top opportunities."""
    db = _get_db(db_path)
    try:
        from opportunity_matrix.reporting.digest import generate_report
        output = generate_report(db, format=format, top=top)
        typer.echo(output)
    finally:
        db.close()


@app.command()
def status(
    db_path: str = typer.Option("", "--db-path", help="Database path override"),
):
    """Show system status and health."""
    db = _get_db(db_path)
    try:
        signal_count = db.get_signal_count()
        opps = db.get_opportunities(min_score=0.0)

        typer.echo("Opportunity Matrix Status")
        typer.echo("=" * 40)
        typer.echo(f"Total signals: {signal_count}")
        typer.echo(f"Total opportunities: {len(opps)}")

        for platform in Platform:
            count = db.get_signal_count(platform)
            if count > 0:
                typer.echo(f"  {platform.value}: {count} signals")
    finally:
        db.close()
