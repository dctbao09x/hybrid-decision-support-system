# backend/scoring/strategies.py
"""
Scoring strategies (production architecture)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import logging
import copy

from .models import (
    UserProfile,
    CareerData,
    ScoredCareer,
    ScoreBreakdown
)
from .config import ScoringConfig
from .calculator import CompositeScoreCalculator


logger = logging.getLogger(__name__)


# =====================================================
# Base Strategy
# =====================================================

class ScoringStrategy(ABC):
    """Abstract scoring strategy"""

    def __init__(self, config: ScoringConfig):
        self.config = config
        self._calculator = CompositeScoreCalculator(config)


    # -----------------------------
    # Lifecycle hooks
    # -----------------------------

    def pre_rank(
        self,
        user: UserProfile,
        careers: List[CareerData]
    ) -> None:
        """Hook before ranking"""
        pass


    def post_rank(
        self,
        results: List[ScoredCareer]
    ) -> None:
        """Hook after ranking"""
        pass


    # -----------------------------
    # Core
    # -----------------------------

    def score_one(
        self,
        user: UserProfile,
        career: CareerData
    ) -> Optional[ScoredCareer]:

        try:
            total, breakdown = self._calculator.calculate(user, career)

            if total < self.config.min_score_threshold:
                return None

            return ScoredCareer(
                career_name=career.name,
                total_score=total,
                breakdown=ScoreBreakdown(**breakdown)
            )

        except Exception:

            logger.exception(
                "Scoring failed | user=%s career=%s",
                user.education_level,
                career.name
            )

            if self.config.debug_mode:
                raise

            return None


    def rank(
        self,
        user: UserProfile,
        careers: List[CareerData]
    ) -> List[ScoredCareer]:

        if not careers:
            logger.warning("Ranking aborted: empty career list")
            return []

        self.pre_rank(user, careers)

        results: List[ScoredCareer] = []

        for career in careers:

            scored = self.score_one(user, career)

            if scored:
                results.append(scored)

        # Sort descending
        results.sort(
            key=lambda x: x.total_score,
            reverse=True
        )

        # Ranking
        for i, item in enumerate(results, start=1):
            item.rank = i

        self.post_rank(results)

        return results


# =====================================================
# Standard Weighted Strategy
# =====================================================

class WeightedScoringStrategy(ScoringStrategy):
    """Standard weighted scoring"""

    pass


# =====================================================
# Personalized Strategy
# =====================================================

class PersonalizedScoringStrategy(ScoringStrategy):
    """Adaptive weight strategy"""

    def __init__(self, config: ScoringConfig):
        super().__init__(config)


    def _build_personalized_config(
        self,
        user: UserProfile
    ) -> ScoringConfig:

        cfg = copy.deepcopy(self.config)

        w = cfg.main_weights

        # Rule-based personalization
        if user.confidence_score >= 0.8:

            w.skill_match = 0.35
            w.interest_match = 0.30
            w.market_score = 0.20
            w.ability_score = 0.15

        if user.ability_score <= 0.3:

            w.skill_match += 0.05
            w.ability_score -= 0.05

        # Revalidate
        cfg.main_weights = type(w)(
            **w.to_dict()
        )

        return cfg


    def pre_rank(
        self,
        user: UserProfile,
        careers: List[CareerData]
    ) -> None:

        personalized = self._build_personalized_config(user)

        self.config = personalized
        self._calculator = CompositeScoreCalculator(personalized)

        logger.debug(
            "Personalized weights applied: %s",
            personalized.main_weights.to_dict()
        )


# =====================================================
# Strategy Factory
# =====================================================

class StrategyFactory:
    """Scoring strategy registry"""

    _registry = {
        "weighted": WeightedScoringStrategy,
        "personalized": PersonalizedScoringStrategy
    }

    @classmethod
    def create(
        cls,
        name: str,
        config: ScoringConfig
    ) -> ScoringStrategy:

        strategy_cls = cls._registry.get(name)

        if not strategy_cls:
            raise ValueError(f"Unknown strategy: {name}")

        return strategy_cls(config)
