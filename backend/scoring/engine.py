# backend/scoring/engine.py
"""
Ranking Decision Engine (production architecture)
"""

from typing import List, Optional, Dict
import uuid
import logging

from .models import (
    UserProfile,
    CareerData,
    ScoredCareer,
    RankingInput,
    RankingOutput
)

from .config import ScoringConfig, DEFAULT_CONFIG
from .strategies import (
    ScoringStrategy,
    StrategyFactory
)


logger = logging.getLogger(__name__)


# =====================================================
# Execution Context
# =====================================================

class RankingContext:
    """Execution metadata"""

    def __init__(self):
        self.request_id = str(uuid.uuid4())


# =====================================================
# Engine
# =====================================================

class RankingEngine:
    """Central decision engine"""

    def __init__(
        self,
        default_config: Optional[ScoringConfig] = None,
        default_strategy: str = "weighted"
    ):

        self._default_config = default_config or DEFAULT_CONFIG
        self._default_strategy_name = default_strategy


    # -------------------------------------------------
    # Core
    # -------------------------------------------------

    def _build_strategy(
        self,
        config: ScoringConfig,
        name: Optional[str] = None
    ) -> ScoringStrategy:

        strategy_name = name or self._default_strategy_name

        return StrategyFactory.create(
            strategy_name,
            config
        )


    def rank(
        self,
        user: UserProfile,
        careers: List[CareerData],
        config_override: Optional[ScoringConfig] = None,
        strategy_name: Optional[str] = None,
        context: Optional[RankingContext] = None
    ) -> List[ScoredCareer]:

        ctx = context or RankingContext()
        config = config_override or self._default_config

        if not careers:

            logger.warning(
                "Ranking aborted | req=%s | empty input",
                ctx.request_id
            )

            return []


        strategy = self._build_strategy(
            config,
            strategy_name
        )


        logger.info(
            "Ranking start | req=%s | user_skills=%d | careers=%d | strategy=%s",
            ctx.request_id,
            len(user.skills),
            len(careers),
            strategy.__class__.__name__
        )


        try:

            results = strategy.rank(
                user,
                careers
            )


            logger.info(
                "Ranking done | req=%s | returned=%d",
                ctx.request_id,
                len(results)
            )

            return results


        except Exception:

            logger.exception(
                "Ranking failed | req=%s",
                ctx.request_id
            )

            if config.debug_mode:
                raise

            return []


    # -------------------------------------------------
    # DTO interface
    # -------------------------------------------------

    def rank_from_input(
        self,
        ranking_input: RankingInput,
        strategy_name: Optional[str] = None
    ) -> RankingOutput:

        context = RankingContext()

        results = self.rank(
            user=ranking_input.user_profile,
            careers=ranking_input.eligible_careers,
            strategy_name=strategy_name,
            context=context
        )

        return RankingOutput(
            ranked_careers=results,
            total_evaluated=len(ranking_input.eligible_careers),
            config_used=self._default_config.main_weights.to_dict()
        )


# =====================================================
# Stateless Facade
# =====================================================

_engine = RankingEngine()


def rank_careers(
    user: UserProfile,
    careers: List[CareerData],
    *,
    config: Optional[ScoringConfig] = None,
    strategy: Optional[str] = None
) -> List[ScoredCareer]:
    """Stateless ranking facade"""

    return _engine.rank(
        user=user,
        careers=careers,
        config_override=config,
        strategy_name=strategy
    )
