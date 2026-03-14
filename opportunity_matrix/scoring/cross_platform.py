"""Cross-platform scorer — TF-IDF entity matching across platforms."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from opportunity_matrix.config import CrossPlatformConfig
from opportunity_matrix.storage.models import Signal

logger = logging.getLogger(__name__)


class CrossPlatformScorer:
    def __init__(self, config: CrossPlatformConfig):
        self.config = config

    def group_signals(self, signals: list[Signal]) -> list[list[Signal]]:
        """Group similar signals using TF-IDF cosine similarity."""
        if not signals:
            return []

        if len(signals) == 1:
            return [signals]

        # Build text corpus from title + body
        texts = [f"{s.title} {s.body}" for s in signals]

        try:
            vectorizer = TfidfVectorizer(stop_words="english", min_df=1)
            tfidf_matrix = vectorizer.fit_transform(texts)
            sim_matrix = cosine_similarity(tfidf_matrix)
        except ValueError:
            # All documents empty or identical
            return [[s] for s in signals]

        # Greedy clustering by similarity threshold
        assigned = set()
        groups: list[list[Signal]] = []

        for i in range(len(signals)):
            if i in assigned:
                continue
            group = [signals[i]]
            assigned.add(i)
            for j in range(i + 1, len(signals)):
                if j in assigned:
                    continue
                if sim_matrix[i, j] >= self.config.similarity_threshold:
                    group.append(signals[j])
                    assigned.add(j)
            groups.append(group)

        return groups

    def score_group(self, group: list[Signal]) -> float:
        """Score a group of similar signals by platform diversity."""
        platforms = set(s.platform for s in group)
        base_score = self._platform_count_score(len(platforms))

        # Weight by recency
        now = datetime.now(timezone.utc)
        high_recency = timedelta(hours=self.config.high_recency_hours)
        recency_window = timedelta(hours=self.config.recency_window_hours)

        recent_count = 0
        total_count = 0
        for s in group:
            created = s.created_at
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except ValueError:
                    continue
            if not created.tzinfo:
                created = created.replace(tzinfo=timezone.utc)

            age = now - created
            if age <= high_recency:
                recent_count += 1
            elif age <= recency_window:
                total_count += 1

        total_count += recent_count
        if total_count > 0:
            recency_bonus = (recent_count / total_count) * 0.1
            base_score = min(1.0, base_score + recency_bonus)

        return base_score

    def _platform_count_score(self, count: int) -> float:
        """Map platform count to base score."""
        mapping = {1: 0.2, 2: 0.5, 3: 0.8}
        if count >= 4:
            return 1.0
        return mapping.get(count, 0.2)
