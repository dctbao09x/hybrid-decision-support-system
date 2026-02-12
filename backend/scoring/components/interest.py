# backend/scoring/components/interest.py
"""
Interest Score Component: Interest-career alignment.

Computes Jaccard similarity between user interests and career domain interests.
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
    """Compute interest score via Jaccard similarity.

    Args:
        job: Career profile
        user: User profile
        config: Scoring config

    Returns:
        ScoreResult with value [0,1] and meta dict
    """
    normalizer = DataNormalizer()

    # Normalize interest sets
    user_interests = _normalize_set(user.interests)
    career_interests = _normalize_set(job.domain_interests)

    # Add domain as implicit interest if present
    if job.domain:
        career_interests.add(job.domain.strip().lower())

    # Both empty = no match possible
    if not user_interests or not career_interests:
        return ScoreResult(
            value=0.0,
            meta={
                "method": "jaccard",
                "status": "insufficient_data",
                "matched": 0,
                "user_count": len(user_interests),
                "career_count": len(career_interests),
            }
        )

    # Jaccard similarity: intersection / union
    intersection = len(user_interests & career_interests)
    union = len(user_interests | career_interests)

    if union == 0:
        score = 0.0
    else:
        score = intersection / union

    # Clamp to [0, 1]
    score = normalizer.clamp(score)

    # Meta details
    matched_interests = sorted(user_interests & career_interests)

    meta = {
        "method": "jaccard",
        "score": round(score, 4),
        "matched": matched_interests,
        "matched_count": len(matched_interests),
        "user_count": len(user_interests),
        "career_count": len(career_interests),
    }

    if config.debug_mode:
        meta["user_interests"] = sorted(user_interests)
        meta["career_interests"] = sorted(career_interests)

    return ScoreResult(value=score, meta=meta)
