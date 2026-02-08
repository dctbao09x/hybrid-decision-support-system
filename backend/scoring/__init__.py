# backend/scoring/__init__.py
"""
Scoring & Ranking Engine

Usage:
    from scoring import RankingEngine, ScoringConfig
    from scoring.models import UserProfile, CareerData
    
    engine = RankingEngine()
    ranked = engine.rank(user_profile, careers)
"""
from .engine import RankingEngine, rank_careers, default_engine
from .config import (
    ScoringConfig,
    ScoringWeights,
    SkillMatchWeights,
    MarketScoreWeights,
    AbilityScoreWeights,
    DEFAULT_CONFIG
)
from .models import (
    UserProfile,
    CareerData,
    ScoredCareer,
    ScoreBreakdown,
    RankingInput,
    RankingOutput
)
from .strategies import (
    ScoringStrategy,
    WeightedScoringStrategy,
    PersonalizedScoringStrategy
)

__all__ = [
    # Engine
    'RankingEngine',
    'rank_careers',
    'default_engine',
    
    # Config
    'ScoringConfig',
    'ScoringWeights',
    'SkillMatchWeights',
    'MarketScoreWeights',
    'AbilityScoreWeights',
    'DEFAULT_CONFIG',
    
    # Models
    'UserProfile',
    'CareerData',
    'ScoredCareer',
    'ScoreBreakdown',
    'RankingInput',
    'RankingOutput',
    
    # Strategies
    'ScoringStrategy',
    'WeightedScoringStrategy',
    'PersonalizedScoringStrategy'
]

__version__ = '1.0.0'