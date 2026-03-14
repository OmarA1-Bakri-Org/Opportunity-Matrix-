"""Feasibility scorer — rule-based patterns with LLM stub."""

from __future__ import annotations

import logging

from opportunity_matrix.config import ScoringConfig
from opportunity_matrix.storage.models import Signal

logger = logging.getLogger(__name__)

BASE_SCORE = 0.5


class FeasibilityScorer:
    def __init__(self, config: ScoringConfig):
        self.config = config

    def score(self, signal: Signal) -> float:
        """Score signal feasibility using rule-based patterns."""
        score = BASE_SCORE
        content = f"{signal.title} {signal.body}".lower()

        # Apply boosters
        for rule in self.config.feasibility_rules.boosters:
            if rule.pattern.lower() in content:
                score += rule.score

        # Apply penalties
        for rule in self.config.feasibility_rules.penalties:
            if rule.pattern.lower() in content:
                score += rule.score  # score is negative for penalties

        # Clamp to [0.0, 1.0]
        score = max(0.0, min(1.0, score))

        # LLM refinement (stub — only when enabled and thresholds met)
        if self.config.llm.enabled and score >= self.config.llm.min_feasibility:
            llm_score = self._llm_score(signal)
            if llm_score is not None:
                score = llm_score

        return score

    def _llm_score(self, signal: Signal) -> float | None:
        """LLM feasibility scoring — stub until LLM_API_KEY is configured."""
        # TODO: Implement when Zeroclaw model or Gemini is available
        logger.info("LLM scoring not yet implemented, using rule-based score")
        return None
