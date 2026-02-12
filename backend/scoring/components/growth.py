# backend/scoring/components/growth.py
"""
Growth Score Component: Career growth potential.

Evaluates skill growth opportunity and salary growth potential.
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
    """Compute growth score: potential for career advancement.

    Args:
        job: Career profile
        user: User profile (unused for this version)
        config: Scoring config with component weights

    Returns:
        ScoreResult with value [0,1] and meta dict
    """
    normalizer = DataNormalizer()
    weights = config.component_weights

    # Use growth_rate and ai_relevance as proxies for growth potential
    # Growth opportunities increase with AI relevance and industry growth

    # Skill growth opportunity (higher growth rate = more opportunity)
    skill_growth = normalizer.clamp(job.growth_rate)

    # Salary growth potential (correlate with AI relevance + growth)
    salary_growth = normalizer.clamp(
        (job.ai_relevance + job.growth_rate) / 2.0
    )

    # Weighted combination
    growth_score = (
        skill_growth * weights.skill_growth_opportunity +
        salary_growth * weights.salary_growth_potential
    )

    # Clamp to [0, 1]
    growth_score = normalizer.clamp(growth_score)

    # Meta details
    meta = {
        "skill_growth_opportunity": round(skill_growth, 4),
        "salary_growth_potential": round(salary_growth, 4),
        "growth_score": round(growth_score, 4),
        "growth_rate": round(job.growth_rate, 4),
        "ai_relevance": round(job.ai_relevance, 4),
    }

    return ScoreResult(value=growth_score, meta=meta)
