# backend/scoring/config.py
"""
Scoring configuration and weight management
"""
from typing import Dict
from dataclasses import dataclass, field


@dataclass
class ScoringWeights:
    """Weights for main scoring formula"""
    skill_match: float = 0.4
    interest_match: float = 0.3
    market_score: float = 0.2
    ability_score: float = 0.1
    
    def __post_init__(self):
        """Validate weights sum to 1.0"""
        total = self.skill_match + self.interest_match + self.market_score + self.ability_score
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary"""
        return {
            "skill_match": self.skill_match,
            "interest_match": self.interest_match,
            "market_score": self.market_score,
            "ability_score": self.ability_score
        }


@dataclass
class SkillMatchWeights:
    """Weights for skill matching sub-score"""
    required_skills: float = 0.7
    preferred_skills: float = 0.3
    
    def __post_init__(self):
        total = self.required_skills + self.preferred_skills
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Skill weights must sum to 1.0, got {total}")


@dataclass
class MarketScoreWeights:
    """Weights for market score sub-score"""
    ai_relevance: float = 0.4
    growth_rate: float = 0.4
    inverse_competition: float = 0.2
    
    def __post_init__(self):
        total = self.ai_relevance + self.growth_rate + self.inverse_competition
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Market weights must sum to 1.0, got {total}")


@dataclass
class AbilityScoreWeights:
    """Weights for ability score"""
    ability: float = 0.6
    confidence: float = 0.4
    
    def __post_init__(self):
        total = self.ability + self.confidence
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Ability weights must sum to 1.0, got {total}")


@dataclass
class ScoringConfig:
    """Complete scoring configuration"""
    main_weights: ScoringWeights = field(default_factory=ScoringWeights)
    skill_weights: SkillMatchWeights = field(default_factory=SkillMatchWeights)
    market_weights: MarketScoreWeights = field(default_factory=MarketScoreWeights)
    ability_weights: AbilityScoreWeights = field(default_factory=AbilityScoreWeights)
    
    debug_mode: bool = False
    min_score_threshold: float = 0.0
    
    @classmethod
    def create_custom(
        cls,
        skill_match: float = 0.4,
        interest_match: float = 0.3,
        market_score: float = 0.2,
        ability_score: float = 0.1,
        debug: bool = False
    ) -> 'ScoringConfig':
        """Create config with custom main weights"""
        return cls(
            main_weights=ScoringWeights(
                skill_match=skill_match,
                interest_match=interest_match,
                market_score=market_score,
                ability_score=ability_score
            ),
            debug_mode=debug
        )


# Default configuration instance
DEFAULT_CONFIG = ScoringConfig()