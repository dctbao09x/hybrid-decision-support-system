# backend/scoring/calculator.py
"""
Scoring calculators (production version)
"""

from typing import List, Dict, Tuple, Set, Optional
import logging

from .models import UserProfile, CareerData
from .config import (
    SkillMatchWeights,
    MarketScoreWeights,
    AbilityScoreWeights,
    ScoringConfig
)
from .normalizer import DataNormalizer


logger = logging.getLogger(__name__)


# =====================================================
# Base Calculator
# =====================================================

class BaseCalculator:
    """Base class for all calculators"""

    normalizer = DataNormalizer()

    @staticmethod
    def _normalize_set(values: Optional[List[str]]) -> Set[str]:
        """Normalize string list → lowercase set"""

        if not values:
            return set()

        return {
            str(v).strip().lower()
            for v in values
            if v is not None
        }


# =====================================================
# Skill Matching
# =====================================================

class SkillMatchCalculator(BaseCalculator):
    """Skill coverage based matching"""

    def __init__(self, weights: SkillMatchWeights):
        self.weights = weights


    def calculate(
        self,
        user_skills: List[str],
        required_skills: List[str],
        preferred_skills: List[str]
    ) -> Tuple[float, Dict]:

        user = self._normalize_set(user_skills)
        required = self._normalize_set(required_skills)
        preferred = self._normalize_set(preferred_skills)

        # Required coverage
        if required:
            req_score = len(user & required) / len(required)
        else:
            req_score = 1.0

        # Preferred coverage
        if preferred:
            pref_score = len(user & preferred) / len(preferred)
        else:
            pref_score = 0.5

        total = (
            req_score * self.weights.required_skills +
            pref_score * self.weights.preferred_skills
        )

        details = {
            "required_coverage": round(req_score, 4),
            "preferred_coverage": round(pref_score, 4),
            "matched_required": len(user & required),
            "total_required": len(required),
            "matched_preferred": len(user & preferred),
            "total_preferred": len(preferred)
        }

        return self.normalizer.clamp(total), details


# =====================================================
# Interest Matching
# =====================================================

class InterestMatchCalculator(BaseCalculator):
    """Domain-interest similarity"""

    def calculate(
        self,
        user_interests: List[str],
        domain: str,
        domain_interests: List[str]
    ) -> Tuple[float, Dict]:

        user = self._normalize_set(user_interests)

        career = self._normalize_set(domain_interests)

        if domain:
            career.add(domain.strip().lower())

        if not user or not career:
            return 0.0, {"status": "insufficient_data"}

        score = self.normalizer.jaccard_similarity(user, career)

        details = {
            "method": "jaccard",
            "matched": sorted(user & career),
            "user_count": len(user),
            "career_count": len(career)
        }

        return score, details


# =====================================================
# Market Score
# =====================================================

class MarketScoreCalculator(BaseCalculator):
    """Market attractiveness"""

    def __init__(self, weights: MarketScoreWeights):
        self.weights = weights


    def calculate(
        self,
        ai_relevance: float,
        growth_rate: float,
        competition: float
    ) -> Tuple[float, Dict]:

        ai = self.normalizer.clamp(ai_relevance)
        growth = self.normalizer.clamp(growth_rate)
        comp = self.normalizer.clamp(competition)

        inv_comp = 1.0 - comp

        total = (
            ai * self.weights.ai_relevance +
            growth * self.weights.growth_rate +
            inv_comp * self.weights.inverse_competition
        )

        details = {
            "ai_relevance": round(ai, 4),
            "growth_rate": round(growth, 4),
            "competition": round(comp, 4),
            "inverse_competition": round(inv_comp, 4)
        }

        return self.normalizer.clamp(total), details


# =====================================================
# Ability Score
# =====================================================

class AbilityScoreCalculator(BaseCalculator):
    """User ability estimator"""

    def __init__(self, weights: AbilityScoreWeights):
        self.weights = weights


    def calculate(
        self,
        ability: float,
        confidence: float
    ) -> Tuple[float, Dict]:

        ab = self.normalizer.clamp(ability)
        cf = self.normalizer.clamp(confidence)

        total = (
            ab * self.weights.ability +
            cf * self.weights.confidence
        )

        details = {
            "ability": round(ab, 4),
            "confidence": round(cf, 4)
        }

        return self.normalizer.clamp(total), details


# =====================================================
# Composite Engine
# =====================================================

class CompositeScoreCalculator:
    """Final decision engine"""

    def __init__(self, config: ScoringConfig):

        if not isinstance(config, ScoringConfig):
            raise TypeError("Invalid scoring config")

        self.config = config

        self.skill = SkillMatchCalculator(config.skill_weights)
        self.interest = InterestMatchCalculator()
        self.market = MarketScoreCalculator(config.market_weights)
        self.ability = AbilityScoreCalculator(config.ability_weights)

        self.normalizer = DataNormalizer()


    def calculate(
        self,
        user: UserProfile,
        career: CareerData
    ) -> Tuple[float, Dict]:

        skill_s, skill_d = self.skill.calculate(
            user.skills,
            career.required_skills,
            career.preferred_skills
        )

        interest_s, interest_d = self.interest.calculate(
            user.interests,
            career.domain,
            career.domain_interests
        )

        market_s, market_d = self.market.calculate(
            career.ai_relevance,
            career.growth_rate,
            career.competition
        )

        ability_s, ability_d = self.ability.calculate(
            user.ability_score,
            user.confidence_score
        )

        w = self.config.main_weights

        total = (
            skill_s * w.skill_match +
            interest_s * w.interest_match +
            market_s * w.market_score +
            ability_s * w.ability_score
        )

        total = self.normalizer.clamp(total)

        breakdown = {
            "skill_match": round(skill_s, 4),
            "interest_match": round(interest_s, 4),
            "market_score": round(market_s, 4),
            "ability_score": round(ability_s, 4)
        }

        if self.config.debug_mode:

            breakdown["skill_details"] = skill_d
            breakdown["interest_details"] = interest_d
            breakdown["market_details"] = market_d
            breakdown["ability_details"] = ability_d

        return total, breakdown
