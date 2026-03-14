"""Report generator — markdown and JSON digest output."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from opportunity_matrix.storage.db import Database


def generate_report(db: Database, format: str = "md", top: int = 10) -> str:
    """Generate a report of top opportunities."""
    opps = db.get_opportunities(min_score=0.0, limit=top)

    if format == "json":
        return _json_report(opps, db)
    return _markdown_report(opps, db)


def _markdown_report(opps: list, db: Database) -> str:
    """Generate markdown report."""
    lines = ["# Opportunity Matrix Report", ""]
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"Total signals: {db.get_signal_count()}")
    lines.append(f"Showing top {len(opps)} opportunities")
    lines.append("")

    if not opps:
        lines.append("No opportunities found.")
        return "\n".join(lines)

    lines.append("---")
    lines.append("")

    for i, opp in enumerate(opps, 1):
        lines.append(f"## {i}. {opp.title}")
        lines.append("")
        if opp.description:
            lines.append(f"> {opp.description[:200]}")
            lines.append("")
        lines.append(f"**Composite Score:** {opp.composite_score:.2f}")
        lines.append(f"- Engagement: {opp.engagement_score:.2f}")
        lines.append(f"- Cross-platform: {opp.cross_platform_score:.2f}")
        lines.append(f"- Feasibility: {opp.feasibility_score:.2f}")
        lines.append("")
        lines.append(f"**Platforms:** {opp.platform_count} | **Category:** {opp.category} | **Status:** {opp.status}")

        # Get linked signals
        signals = db.get_signals_for_opportunity(opp.id)
        if signals:
            lines.append("")
            lines.append("**Sources:**")
            for s in signals:
                lines.append(f"- [{s.platform.value}] {s.title} ({s.upvotes} upvotes)")

        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _json_report(opps: list, db: Database) -> str:
    """Generate JSON report."""
    data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_signals": db.get_signal_count(),
        "opportunities": [],
    }

    for opp in opps:
        signals = db.get_signals_for_opportunity(opp.id)
        data["opportunities"].append({
            "title": opp.title,
            "description": opp.description,
            "category": opp.category,
            "scores": {
                "composite": opp.composite_score,
                "engagement": opp.engagement_score,
                "cross_platform": opp.cross_platform_score,
                "feasibility": opp.feasibility_score,
            },
            "platform_count": opp.platform_count,
            "status": opp.status,
            "first_seen": str(opp.first_seen),
            "last_seen": str(opp.last_seen),
            "sources": [
                {
                    "platform": s.platform.value,
                    "title": s.title,
                    "url": s.url,
                    "upvotes": s.upvotes,
                }
                for s in signals
            ],
        })

    return json.dumps(data, indent=2)
