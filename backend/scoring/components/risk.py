# backend/scoring/components/risk.py
"""
Risk Score Component: Career risk assessment (inverted).

Evaluates market saturation, skill obsolescence, and competition risks.
Returns inverted score where 1.0 = low risk, 0.0 = high risk.
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
    """Compute risk score (inverted: 1.0 = low risk).

    Args:
        job: Career profile
        user: User profile
        config: Scoring config with component weights

    Returns:
        ScoreResult with value [0,1] and meta dict where 1.0 = low risk
    """
    normalizer = DataNormalizer()
    weights = config.component_weights

    # Market saturation risk (high competition = high risk)
    market_saturation_risk = normalizer.clamp(job.competition)

    # Skill obsolescence risk (inverse of growth = risk)
    # High growth = low obsolescence risk
    skill_obsolescence_risk = normalizer.clamp(
        1.0 - job.growth_rate
    )

    # Competition risk (inverse of AI relevance)
    # High AI relevance = less competition in future
    competition_risk = normalizer.clamp(
        1.0 - job.ai_relevance
    )

    # Weighted combination of risks
    total_risk = (
        market_saturation_risk * weights.market_saturation_risk +
        skill_obsolescence_risk * weights.skill_obsolescence_risk +
        competition_risk * weights.competition_risk
    )

    # Invert risk to get score (1.0 = low risk, 0.0 = high risk)
    risk_score = normalizer.clamp(1.0 - total_risk)

    # Meta details
    meta = {
        "market_saturation_risk": round(market_saturation_risk, 4),
        "skill_obsolescence_risk": round(skill_obsolescence_risk, 4),
        "competition_risk": round(competition_risk, 4),
        "total_risk": round(total_risk, 4),
        "risk_score": round(risk_score, 4),
        "competition": round(job.competition, 4),
        "growth_rate": round(job.growth_rate, 4),
        "ai_relevance": round(job.ai_relevance, 4),
    }

    return ScoreResult(value=risk_score, meta=meta)
