# backend/scoring/components/market.py
"""
Market Score Component: Market attractiveness assessment.

Combines AI relevance, growth rate, and inverse competition.
"""

from __future__ import annotations

from backend.scoring.models import UserProfile, CareerData, ScoreResult
from backend.scoring.config import ScoringConfig
from backend.scoring.normalizer import DataNormalizer


def score(
    job: CareerData,
    user: UserProfile,
    config: ScoringConfig
) -> ScoreResult:
    """Compute market score: attractiveness of career.

    Args:
        job: Career profile with market data
        user: User profile (unused for market score)
        config: Scoring config with component weights

    Returns:
        ScoreResult with value [0,1] and meta dict
    """
    normalizer = DataNormalizer()
    weights = config.component_weights

    # Clamp all inputs to [0, 1]
    ai_relevance = normalizer.clamp(job.ai_relevance)
    growth_rate = normalizer.clamp(job.growth_rate)
    competition = normalizer.clamp(job.competition)

    # Inverse competition (high competition = low attractiveness)
    inverse_competition = 1.0 - competition

    # Weighted combination
    market_score = (
        ai_relevance * weights.ai_relevance +
        growth_rate * weights.growth_rate +
        inverse_competition * weights.inverse_competition
    )

    # Clamp result to [0, 1]
    market_score = normalizer.clamp(market_score)

    # Meta details
    meta = {
        "ai_relevance": round(ai_relevance, 4),
        "growth_rate": round(growth_rate, 4),
        "competition": round(competition, 4),
        "inverse_competition": round(inverse_competition, 4),
        "market_score": round(market_score, 4),
    }

    return ScoreResult(value=market_score, meta=meta)
