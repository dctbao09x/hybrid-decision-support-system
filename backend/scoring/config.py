# backend/scoring/config.py
"""
Scoring configuration and weight management (SIMGR standard).

SIMGR = Study, Interest, Market, Growth, Risk scoring components.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Type, Callable, Optional
import logging

logger = logging.getLogger(__name__)


# =====================================================
# Weight Classes (SIMGR Standard)
# =====================================================

@dataclass
class SIMGRWeights:
    """Main scoring weights - SIMGR standard."""
    study_score: float = 0.25
    interest_score: float = 0.25
    market_score: float = 0.25
    growth_score: float = 0.15
    risk_score: float = 0.10
    
    def __post_init__(self) -> None:
        """Validate weights sum to 1.0."""
        total = (
            self.study_score
            + self.interest_score
            + self.market_score
            + self.growth_score
            + self.risk_score
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"SIMGR weights must sum to 1.0, got {total:.4f}"
            )
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "study_score": self.study_score,
            "interest_score": self.interest_score,
            "market_score": self.market_score,
            "growth_score": self.growth_score,
            "risk_score": self.risk_score,
        }
    
    def normalize(self) -> None:
        """Normalize weights to sum to 1.0."""
        total = (
            self.study_score
            + self.interest_score
            + self.market_score
            + self.growth_score
            + self.risk_score
        )
        if total > 0:
            self.study_score /= total
            self.interest_score /= total
            self.market_score /= total
            self.growth_score /= total
            self.risk_score /= total


@dataclass
class ComponentWeights:
    """Sub-component weights for detailed scoring."""
    
    # Study component weights
    required_skill_match: float = 0.7
    preferred_skill_match: float = 0.3
    
    # Interest component weights
    # Uses Jaccard similarity by default
    
    # Market component weights
    ai_relevance: float = 0.4
    growth_rate: float = 0.4
    inverse_competition: float = 0.2
    
    # Growth component weights
    skill_growth_opportunity: float = 0.5
    salary_growth_potential: float = 0.5
    
    # Risk component weights
    market_saturation_risk: float = 0.4
    skill_obsolescence_risk: float = 0.3
    competition_risk: float = 0.3
    
    def __post_init__(self) -> None:
        """Validate sub-weights."""
        # Study weights
        study_total = (
            self.required_skill_match + self.preferred_skill_match
        )
        if abs(study_total - 1.0) > 0.001:
            raise ValueError(
                f"Study weights must sum to 1.0, got {study_total:.4f}"
            )
        
        # Market weights
        market_total = (
            self.ai_relevance
            + self.growth_rate
            + self.inverse_competition
        )
        if abs(market_total - 1.0) > 0.001:
            raise ValueError(
                f"Market weights must sum to 1.0, got {market_total:.4f}"
            )
        
        # Growth weights
        growth_total = (
            self.skill_growth_opportunity + self.salary_growth_potential
        )
        if abs(growth_total - 1.0) > 0.001:
            raise ValueError(
                f"Growth weights must sum to 1.0, got {growth_total:.4f}"
            )
        
        # Risk weights
        risk_total = (
            self.market_saturation_risk
            + self.skill_obsolescence_risk
            + self.competition_risk
        )
        if abs(risk_total - 1.0) > 0.001:
            raise ValueError(
                f"Risk weights must sum to 1.0, got {risk_total:.4f}"
            )


# =====================================================
# Scoring Configuration
# =====================================================

@dataclass
class ScoringConfig:
    """Complete scoring pipeline configuration.
    
    Properties:
        simgr_weights: Main SIMGR component weights
        component_weights: Sub-component weights
        min_score_threshold: Minimum score to include result
        debug_mode: Enable detailed logging and breakdown
        deterministic: Forbid non-deterministic operations
        component_map: Callable map for dynamic component loading
        personalization_enabled: Allow strategy-based weight personalization
    """
    
    simgr_weights: SIMGRWeights = field(default_factory=SIMGRWeights)
    component_weights: ComponentWeights = field(
        default_factory=ComponentWeights
    )
    
    min_score_threshold: float = 0.0
    debug_mode: bool = False
    deterministic: bool = True
    personalization_enabled: bool = True
    
    # Dynamic component loading (no hardcoded imports)
    component_map: Dict[str, Callable] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Initialize component map with default components."""
        if not self.component_map:
            self._init_default_components()
    
    def _init_default_components(self) -> None:
        """Lazy-load default components to avoid circular imports."""
        try:
            from backend.scoring.components import study
            from backend.scoring.components import interest
            from backend.scoring.components import market
            from backend.scoring.components import growth
            from backend.scoring.components import risk

            self.component_map = {
                "study": study.score,
                "interest": interest.score,
                "market": market.score,
                "growth": growth.score,
                "risk": risk.score,
            }
        except ImportError as e:
            logger.warning(f"Failed to load default components: {e}")
            self.component_map = {}
    
    def validate(self) -> None:
        """Full configuration validation."""
        if not (0.0 <= self.min_score_threshold <= 1.0):
            raise ValueError(
                f"min_score_threshold must be in [0, 1], "
                f"got {self.min_score_threshold}"
            )
        
        # Weights already validated in __post_init__
        # Component map validation happens at compute time
    
    @classmethod
    def create_custom(
        cls,
        study: float = None,
        interest: float = None,
        market: float = None,
        growth: float = None,
        risk: float = None,
        debug: bool = False,
        deterministic: bool = True,
    ) -> ScoringConfig:
        """Create config with custom SIMGR weights.
        
        If not all weights are specified, distributes remaining weight
        proportionally among unspecified components.
        """
        # Use defaults for unspecified weights
        weights_dict = {
            'study': study if study is not None else 0.25,
            'interest': interest if interest is not None else 0.25,
            'market': market if market is not None else 0.25,
            'growth': growth if growth is not None else 0.15,
            'risk': risk if risk is not None else 0.10,
        }
        
        # Normalize to ensure sum = 1.0
        total = sum(weights_dict.values())
        if total != 1.0 and total > 0:
            scale = 1.0 / total
            weights_dict = {k: v * scale for k, v in weights_dict.items()}
        
        return cls(
            simgr_weights=SIMGRWeights(
                study_score=weights_dict['study'],
                interest_score=weights_dict['interest'],
                market_score=weights_dict['market'],
                growth_score=weights_dict['growth'],
                risk_score=weights_dict['risk'],
            ),
            debug_mode=debug,
            deterministic=deterministic,
        )
    
    def copy_with_weights(
        self,
        study: Optional[float] = None,
        interest: Optional[float] = None,
        market: Optional[float] = None,
        growth: Optional[float] = None,
        risk: Optional[float] = None,
    ) -> ScoringConfig:
        """Create copy with modified SIMGR weights (for personalization).

        Note: Weights are NOT re-normalized. Caller is responsible for ensuring
        they sum to 1.0 if strict validation is required.
        """
        from copy import deepcopy

        cfg = deepcopy(self)

        # Override specified weights without re-normalizing
        if study is not None:
            cfg.simgr_weights.study_score = study
        if interest is not None:
            cfg.simgr_weights.interest_score = interest
        if market is not None:
            cfg.simgr_weights.market_score = market
        if growth is not None:
            cfg.simgr_weights.growth_score = growth
        if risk is not None:
            cfg.simgr_weights.risk_score = risk

        return cfg

    def reload(self) -> None:
        """Reload configuration from defaults.

        Resets component map and re-initializes defaults.
        Use for hot reload on startup or manual trigger.
        """
        self.component_map = {}
        self._init_default_components()


# =====================================================
# Default Configuration
# =====================================================

DEFAULT_CONFIG = ScoringConfig()