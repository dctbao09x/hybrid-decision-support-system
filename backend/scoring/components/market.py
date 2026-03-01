# backend/scoring/components/market.py
"""
Market Score Component: Market attractiveness assessment.

SIMGR Market Formula: M = 0.3*AI + 0.3*Growth + 0.2*Salary + 0.2*InvComp
  - AI: AI relevance (automation resilience)
  - Growth: Market growth rate
  - Salary: Normalized salary attractiveness
  - InvComp: Inverse competition (1 - saturation)

This component measures how attractive the career market is.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from backend.scoring.models import UserProfile, CareerData, ScoreResult
from backend.scoring.config import ScoringConfig
from backend.scoring.normalizer import DataNormalizer
from backend.market.cache_loader import MarketCacheLoader

logger = logging.getLogger(__name__)

_cache_loader = MarketCacheLoader()


# =====================================================
# Market Component Weights
# =====================================================
WEIGHT_AI_RELEVANCE = 0.3      # AI/automation resilience
WEIGHT_GROWTH_RATE = 0.3       # Market growth
WEIGHT_SALARY = 0.2            # Salary attractiveness
WEIGHT_INVERSE_COMP = 0.2      # Inverse competition


# =====================================================
# Salary Dataset (normalized values)
# Reference: BLS, Glassdoor, LinkedIn Salary Insights
# =====================================================
SALARY_DATASET: Dict[str, float] = {
    # Tech
    "software engineer": 0.85,
    "software developer": 0.80,
    "data scientist": 0.90,
    "Machine Learning Engineer": 0.95,
    "devops engineer": 0.85,
    "full stack developer": 0.80,
    "frontend developer": 0.75,
    "backend developer": 0.80,
    "cloud architect": 0.92,
    "data engineer": 0.85,
    "AI Engineer": 0.95,
    "cybersecurity analyst": 0.80,
    "security engineer": 0.85,
    
    # Management
    "product manager": 0.88,
    "project manager": 0.75,
    "engineering manager": 0.92,
    "cto": 0.98,
    "vp engineering": 0.95,
    
    # Finance
    "financial analyst": 0.70,
    "investment banker": 0.95,
    "quantitative analyst": 0.95,
    "data analyst": 0.70,
    "business analyst": 0.72,
    
    # Healthcare
    "physician": 0.95,
    "nurse": 0.65,
    "pharmacist": 0.80,
    "healthcare administrator": 0.75,
    
    # Design
    "ux designer": 0.75,
    "ui designer": 0.72,
    "product designer": 0.78,
    "graphic designer": 0.60,
    
    # Marketing
    "marketing manager": 0.75,
    "digital marketing specialist": 0.65,
    "seo specialist": 0.62,
    "content manager": 0.60,
    
    # Default
    "default": 0.60,
}


def _get_salary_score(career_name: str) -> float:
    """Get normalized salary score for career.
    
    Looks up salary data from dataset, falls back to default.
    
    Returns:
        Float in [0, 1] representing salary attractiveness.
    """
    if not career_name:
        return SALARY_DATASET["default"]
    
    name_lower = career_name.lower().strip()
    
    # Exact match
    if name_lower in SALARY_DATASET:
        return SALARY_DATASET[name_lower]
    
    # Partial match
    for key, value in SALARY_DATASET.items():
        if key != "default" and (key in name_lower or name_lower in key):
            return value
    
    return SALARY_DATASET["default"]


def score(
    job: CareerData,
    user: UserProfile,
    config: ScoringConfig
) -> ScoreResult:
    """Compute market score: M = 0.3*AI + 0.3*Growth + 0.2*Salary + 0.2*InvComp.

    Args:
        job: Career profile with market data
        user: User profile (unused for market score)
        config: Scoring config with component weights

    Returns:
        ScoreResult with value [0,1] and meta dict
    """
    normalizer = DataNormalizer()

    market_record = _cache_loader.lookup_by_title(job.name)

    # Never call realtime APIs in scoring; use cache if available, else fallback to input fields.
    if market_record:
        ai_relevance = normalizer.clamp(float(market_record.get("ai_relevance", job.ai_relevance)))
        growth_rate = normalizer.clamp(float(market_record.get("growth_rate", job.growth_rate)))
        competition = normalizer.clamp(float(market_record.get("competition", job.competition)))
        source = "cache"
    else:
        ai_relevance = normalizer.clamp(job.ai_relevance)
        growth_rate = normalizer.clamp(job.growth_rate)
        competition = normalizer.clamp(job.competition)
        source = "career_input"
        logger.debug("Market cache miss for career=%s, using career input fields", job.name)

    # Get salary score from dataset
    salary_score = _get_salary_score(job.name)

    # Inverse competition (high competition = low attractiveness)
    inverse_competition = 1.0 - competition

    # Apply SIMGR Market formula: M = 0.3*AI + 0.3*Growth + 0.2*Salary + 0.2*InvComp
    market_score = (
        WEIGHT_AI_RELEVANCE * ai_relevance +
        WEIGHT_GROWTH_RATE * growth_rate +
        WEIGHT_SALARY * salary_score +
        WEIGHT_INVERSE_COMP * inverse_competition
    )

    # Clamp result to [0, 1]
    market_score = normalizer.clamp(market_score)

    # Meta details
    meta = {
        "formula": "M = 0.3*AI + 0.3*Growth + 0.2*Salary + 0.2*InvComp",
        "source": source,
        "ai_relevance": round(ai_relevance, 4),
        "growth_rate": round(growth_rate, 4),
        "salary_score": round(salary_score, 4),
        "competition": round(competition, 4),
        "inverse_competition": round(inverse_competition, 4),
        "weights_used": {
            "ai_relevance": WEIGHT_AI_RELEVANCE,
            "growth_rate": WEIGHT_GROWTH_RATE,
            "salary": WEIGHT_SALARY,
            "inverse_competition": WEIGHT_INVERSE_COMP,
        },
    }

    return ScoreResult(value=market_score, meta=meta)
