# backend/scoring/components/study.py
"""
Study Score Component: Skill match and education fit.

Computes how well user's skills and education match career requirements.
"""

from __future__ import annotations

from typing import Optional, Set
from backend.scoring.models import UserProfile, CareerData, ScoreResult
from backend.scoring.config import ScoringConfig
from backend.scoring.normalizer import DataNormalizer


def _normalize_set(values: Optional[list[str]]) -> Set[str]:
    """Normalize string list to lowercase set."""
    if not values:
        return set()
    return {str(v).strip().lower() for v in values if v}


def score(
    job: CareerData,
    user: UserProfile,
    config: ScoringConfig
) -> ScoreResult:
    """Compute study score: skill match and education fit.

    Args:
        job: Career profile
        user: User profile
        config: Scoring config with component weights

    Returns:
        ScoreResult with value [0,1] and meta dict
    """
    normalizer = DataNormalizer()
    weights = config.component_weights

    # Normalize skill sets
    user_skills = _normalize_set(user.skills)
    required_skills = _normalize_set(job.required_skills)
    preferred_skills = _normalize_set(job.preferred_skills)

    # Required skill coverage (required skills match)
    if required_skills:
        required_coverage = len(user_skills & required_skills) / len(required_skills)
    else:
        required_coverage = 1.0  # No requirements = satisfied

    # Preferred skill coverage
    if preferred_skills:
        preferred_coverage = len(user_skills & preferred_skills) / len(preferred_skills)
    else:
        preferred_coverage = 0.5  # No preferences = neutral

    # Weighted combination
    skill_score = (
        required_coverage * weights.required_skill_match +
        preferred_coverage * weights.preferred_skill_match
    )

    # Clamp to [0, 1]
    skill_score = normalizer.clamp(skill_score)

    # Meta details
    meta = {
        "required_coverage": round(required_coverage, 4),
        "preferred_coverage": round(preferred_coverage, 4),
        "matched_required": len(user_skills & required_skills),
        "total_required": len(required_skills),
        "matched_preferred": len(user_skills & preferred_skills),
        "total_preferred": len(preferred_skills),
    }

    if config.debug_mode:
        meta["user_skills"] = sorted(user_skills)
        meta["required_skills"] = sorted(required_skills)
        meta["preferred_skills"] = sorted(preferred_skills)

    return ScoreResult(value=skill_score, meta=meta)
