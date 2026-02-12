# backend/scoring/__init__.py
"""
Scoring & Ranking Engine (SIMGR Standard)

Primary entry point: SIMGRScorer (unified public API)

Usage:
    from backend.scoring import SIMGRScorer
    
    scorer = SIMGRScorer(strategy="weighted")
    output = scorer.score({
        "user": {"skills": ["python"], "interests": ["AI"]},
        "careers": [{"name": "Data Scientist", "required_skills": ["python"]}]
    })
    
    print(output["ranked_careers"])
    print(output["config_used"])

Legacy API (still available):
    from backend.scoring import RankingEngine, rank_careers
    from backend.scoring.models import UserProfile, CareerData
    from backend.scoring.config import ScoringConfig
"""

from backend.scoring.scoring import SIMGRScorer
from backend.scoring.engine import (
    RankingEngine,
    rank_careers,
    score_jobs,
    create_engine,
    RankingContext,
)
from backend.scoring.config import (
    ScoringConfig,
    SIMGRWeights,
    ComponentWeights,
    DEFAULT_CONFIG,
)
from backend.scoring.models import (
    UserProfile,
    CareerData,
    ScoredCareer,
    ScoreBreakdown,
    RankingInput,
    RankingOutput,
)
from backend.scoring.strategies import (
    ScoringStrategy,
    WeightedScoringStrategy,
    PersonalizedScoringStrategy,
    StrategyFactory,
)
from backend.scoring.calculator import (
    SIMGRCalculator,
)

__all__ = [
    # Primary entry point
    "SIMGRScorer",

    # Engine
    "RankingEngine",
    "rank_careers",
    "score_jobs",
    "create_engine",
    "RankingContext",
    
    # Configuration
    "ScoringConfig",
    "SIMGRWeights",
    "ComponentWeights",
    "DEFAULT_CONFIG",
    
    # Models
    "UserProfile",
    "CareerData",
    "ScoredCareer",
    "ScoreBreakdown",
    "RankingInput",
    "RankingOutput",
    
    # Strategies
    "ScoringStrategy",
    "WeightedScoringStrategy",
    "PersonalizedScoringStrategy",
    "StrategyFactory",
    
    # Calculator
    "SIMGRCalculator",
]
