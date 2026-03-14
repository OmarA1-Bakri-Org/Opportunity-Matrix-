"""Engagement scorer — per-platform normalization with auto-calibrating percentiles."""

from __future__ import annotations

import logging
from typing import Optional

from opportunity_matrix.storage.models import Platform, Signal

logger = logging.getLogger(__name__)

# Default p90 values for cold start (before calibration)
DEFAULT_P90 = {
    Platform.REDDIT: 500.0,
    Platform.HACKERNEWS: 300.0,
    Platform.GITHUB: 1000.0,
    Platform.TWITTER: 500.0,
    Platform.PRODUCTHUNT: 200.0,
}


class EngagementScorer:
    def __init__(self):
        self._p90: dict[Platform, float] = dict(DEFAULT_P90)

    def score(self, signal: Signal) -> float:
        """Score a signal's engagement from 0.0 to 1.0."""
        raw = self._raw_engagement(signal)
        p90 = self._p90.get(signal.platform, 500.0)
        if p90 <= 0:
            return 0.0
        return min(1.0, raw / p90)

    def _raw_engagement(self, signal: Signal) -> float:
        """Calculate raw engagement metric per platform formula."""
        if signal.platform == Platform.REDDIT:
            return signal.upvotes * 0.6 + signal.comments_count * 0.4
        elif signal.platform == Platform.HACKERNEWS:
            return signal.upvotes * 0.5 + signal.comments_count * 0.5
        elif signal.platform == Platform.GITHUB:
            forks = signal.metadata.get("forks", 0) if signal.metadata else 0
            return signal.upvotes * 0.4 + forks * 0.3 + signal.comments_count * 0.3
        elif signal.platform == Platform.TWITTER:
            return signal.upvotes * 0.4 + signal.comments_count * 0.2
        else:
            return signal.upvotes * 0.5 + signal.comments_count * 0.5

    def update_percentiles(self, signals: list[Signal]) -> None:
        """Recalculate p90 from real data for auto-calibration."""
        by_platform: dict[Platform, list[float]] = {}
        for s in signals:
            raw = self._raw_engagement(s)
            by_platform.setdefault(s.platform, []).append(raw)

        for platform, values in by_platform.items():
            if len(values) >= 10:
                sorted_vals = sorted(values)
                idx = int(len(sorted_vals) * 0.9)
                p90 = sorted_vals[min(idx, len(sorted_vals) - 1)]
                if p90 > 0:
                    self._p90[platform] = p90
                    logger.info(f"Updated {platform.value} p90 to {p90:.1f}")
