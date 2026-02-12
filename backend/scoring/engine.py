# backend/scoring/engine.py
"""
Ranking Engine: Central orchestration of scoring pipeline.

Responsibilities:
- Accept RankingInput and produce RankingOutput
- Support strategy switching
- Inject configuration properly
- Expose rank_careers() stateless facade
"""

from __future__ import annotations

from typing import List, Optional
import uuid
import logging
from datetime import datetime

from backend.scoring.models import (
    UserProfile,
    CareerData,
    ScoredCareer,
    RankingInput,
    RankingOutput,
)
from backend.scoring.config import ScoringConfig, DEFAULT_CONFIG
from backend.scoring.strategies import (
    ScoringStrategy,
    StrategyFactory,
)

logger = logging.getLogger(__name__)


# =====================================================
# Execution Context
# =====================================================

class RankingContext:
    """Execution context for ranking request."""
    
    def __init__(self):
        """Initialize context."""
        self.request_id = str(uuid.uuid4())
        self.timestamp = datetime.now()
    
    def to_dict(self) -> dict:
        """Export as dict."""
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
        }


# =====================================================
# Ranking Engine
# =====================================================

class RankingEngine:
    """Central decision engine for career ranking.
    
    Orchestrates the scoring pipeline:
    1. Accept user profile and careers
    2. Select/build strategy
    3. Delegate to strategy for ranking
    4. Return sorted, ranked results
    """
    
    def __init__(
        self,
        default_config: Optional[ScoringConfig] = None,
        default_strategy: str = "weighted",
    ):
        """Initialize engine.
        
        Args:
            default_config: Default scoring config (uses DEFAULT_CONFIG if None)
            default_strategy: Default strategy name ("weighted" or "personalized")
        """
        self._default_config = default_config or DEFAULT_CONFIG
        self._default_strategy_name = default_strategy.lower()
        
        # Validate strategy exists
        try:
            StrategyFactory.create(
                self._default_strategy_name,
                self._default_config
            )
        except ValueError as e:
            logger.warning(f"Invalid default strategy: {e}")
            self._default_strategy_name = "weighted"
    
    def _build_strategy(
        self,
        config: ScoringConfig,
        name: Optional[str] = None,
    ) -> ScoringStrategy:
        """Build strategy instance.
        
        Args:
            config: Scoring configuration
            name: Strategy name (uses default if None)
        
        Returns:
            ScoringStrategy instance
        """
        strategy_name = (name or self._default_strategy_name).lower()
        return StrategyFactory.create(strategy_name, config)
    
    def rank(
        self,
        user: UserProfile,
        careers: List[CareerData],
        config_override: Optional[ScoringConfig] = None,
        strategy_name: Optional[str] = None,
        context: Optional[RankingContext] = None,
    ) -> List[ScoredCareer]:
        """Rank careers for user.
        
        Args:
            user: User profile (required)
            careers: Careers to rank (required)
            config_override: Optional config override
            strategy_name: Optional strategy override
            context: Optional execution context (auto-created if None)
        
        Returns:
            List of ranked ScoredCareer results
        """
        ctx = context or RankingContext()
        config = config_override or self._default_config
        
        # Input validation
        if not careers:
            logger.warning(
                f"Ranking aborted (empty career list) | req={ctx.request_id}"
            )
            return []
        
        if not isinstance(user, UserProfile):
            logger.error(f"Invalid user type | req={ctx.request_id}")
            return []
        
        # Build strategy
        try:
            strategy = self._build_strategy(config, strategy_name)
        except ValueError as e:
            logger.error(
                f"Strategy creation failed: {e} | req={ctx.request_id}"
            )
            if config.debug_mode:
                raise
            return []
        
        # Execute ranking
        logger.info(
            f"Ranking start | req={ctx.request_id} "
            f"| user_skills={len(user.skills)} "
            f"| careers={len(careers)} "
            f"| strategy={strategy.__class__.__name__}"
        )
        
        try:
            results = strategy.rank(user, careers)
            
            logger.info(
                f"Ranking complete | req={ctx.request_id} "
                f"| returned={len(results)}"
            )
            
            return results
        
        except Exception as e:
            logger.exception(
                f"Ranking failed: {e} | req={ctx.request_id}"
            )
            
            if config.debug_mode:
                raise
            
            return []
    
    def rank_from_input(
        self,
        ranking_input: RankingInput,
        strategy_name: Optional[str] = None,
    ) -> RankingOutput:
        """Rank using RankingInput DTO.
        
        Args:
            ranking_input: Input containing user and careers
            strategy_name: Optional strategy override
        
        Returns:
            RankingOutput with results
        """
        context = RankingContext()
        
        # Use provided weights if present, else default
        config = self._default_config
        
        results = self.rank(
            user=ranking_input.user_profile,
            careers=ranking_input.eligible_careers,
            config_override=config,
            strategy_name=strategy_name,
            context=context,
        )
        
        return RankingOutput(
            ranked_careers=results,
            total_evaluated=len(ranking_input.eligible_careers),
            config_used=config.simgr_weights.to_dict(),
        )


# =====================================================
# Stateless Facade
# =====================================================

# Global engine instance
_engine = RankingEngine()


def rank_careers(
    user: UserProfile,
    careers: List[CareerData],
    *,
    config: Optional[ScoringConfig] = None,
    strategy: Optional[str] = None,
) -> List[ScoredCareer]:
    """Stateless facade for career ranking.
    
    Recommended usage for simple ranking operations.
    
    Args:
        user: User profile
        careers: Careers to rank
        config: Optional config override (keyword-only)
        strategy: Optional strategy override (keyword-only)
    
    Returns:
        List of ranked ScoredCareer results
    
    Example:
        ranked = rank_careers(user_profile, career_list)
    """
    return _engine.rank(
        user=user,
        careers=careers,
        config_override=config,
        strategy_name=strategy,
    )


def score_jobs(
    clean_jobs: List[CareerData],
    user_profile: UserProfile,
    *,
    config: Optional[ScoringConfig] = None,
    strategy: Optional[str] = None,
) -> List[ScoringResult]:
    """Score jobs for user profile.

    Args:
        clean_jobs: List of cleaned job/career data
        user_profile: User profile for scoring
        config: Optional scoring config override
        strategy: Optional strategy override

    Returns:
        List of ScoringResult with contributions mapping
    """
    from backend.scoring.models import ScoringResult

    # Use global engine
    results = _engine.rank(
        user=user_profile,
        careers=clean_jobs,
        config_override=config,
        strategy_name=strategy,
    )

    # Convert to ScoringResult with contributions
    scoring_results = []
    for result in results:
        # Calculate contributions: component -> {weight: contribution}
        weights = _engine._default_config.simgr_weights
        contributions = {
            "study": {
                "weight": weights.study_score,
                "contribution": result.breakdown.study_score * weights.study_score
            },
            "interest": {
                "weight": weights.interest_score,
                "contribution": result.breakdown.interest_score * weights.interest_score
            },
            "market": {
                "weight": weights.market_score,
                "contribution": result.breakdown.market_score * weights.market_score
            },
            "growth": {
                "weight": weights.growth_score,
                "contribution": result.breakdown.growth_score * weights.growth_score
            },
            "risk": {
                "weight": weights.risk_score,
                "contribution": result.breakdown.risk_score * weights.risk_score
            },
        }

        scoring_result = ScoringResult(
            career_name=result.career_name,
            total_score=result.total_score,
            breakdown=result.breakdown,
            contributions=contributions,
            rank=result.rank,
        )
        scoring_results.append(scoring_result)

    return scoring_results


def create_engine(
    config: Optional[ScoringConfig] = None,
    strategy: str = "weighted",
) -> RankingEngine:
    """Create new engine instance.

    Args:
        config: Optional default config
        strategy: Optional default strategy

    Returns:
        New RankingEngine instance
    """
    return RankingEngine(default_config=config, default_strategy=strategy)
