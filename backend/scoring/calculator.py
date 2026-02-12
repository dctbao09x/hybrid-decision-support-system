# backend/scoring/calculator.py
"""
Scoring calculator: Orchestrates SIMGR component computation.

Architecture:
- Loads components dynamically from config.component_map
- Computes all SIMGR scores  
- Applies weights and produces breakdown
- No hardcoded component imports
"""

from __future__ import annotations

from typing import Tuple, Dict, Callable
import logging

from backend.scoring.models import UserProfile, CareerData, ScoreBreakdown
from backend.scoring.config import ScoringConfig
from backend.scoring.normalizer import DataNormalizer

logger = logging.getLogger(__name__)


# =====================================================
# Main Calculator
# =====================================================

class SIMGRCalculator:
    """Orchestrates SIMGR scoring pipeline.
    
    Responsibilities:
    - Load components from config
    - Compute all SIMGR scores
    - Apply weights
    - Produce ScoreBreakdown
    """
    
    def __init__(self, config: ScoringConfig):
        """Initialize calculator.
        
        Args:
            config: Scoring configuration (must have component_map)
        """
        if not isinstance(config, ScoringConfig):
            raise TypeError("config must be ScoringConfig")
        
        self.config = config
        self.normalizer = DataNormalizer()
        self._validate_components()
    
    def _validate_components(self) -> None:
        """Validate component map is initialized."""
        if self.config.deterministic and not self.config.component_map:
            # Lazy initialize if not present
            self.config._init_default_components()
        
        required = {"study", "interest", "market", "growth", "risk"}
        available = set(self.config.component_map.keys())
        
        missing = required - available
        if missing:
            logger.warning(f"Missing components: {missing}")
    
    def calculate(
        self,
        user: UserProfile,
        career: CareerData
    ) -> Tuple[float, Dict]:
        """Calculate total score and breakdown.

        Args:
            user: User profile
            career: Career profile

        Returns:
            Tuple of (total_score, breakdown_dict)
        """
        # Initialize score dict
        simgr_scores: Dict[str, float] = {}
        details: Dict[str, Dict] = {}

        # Compute each SIMGR component
        for component_name in ["study", "interest", "market", "growth", "risk"]:
            try:
                result = self._compute_component(
                    component_name,
                    user,
                    career
                )
                simgr_scores[component_name] = result.value
                details[f"{component_name}_details"] = result.meta

            except Exception as e:
                logger.exception(
                    f"Component {component_name} failed for {career.name}: {e}"
                )

                if self.config.debug_mode:
                    raise

                # Fallback to neutral score
                simgr_scores[component_name] = 0.5
                details[f"{component_name}_details"] = {
                    "error": str(e),
                    "fallback": True
                }

        # Apply weights and compute total
        weights = self.config.simgr_weights

        total_score = (
            simgr_scores.get("study", 0.5) * weights.study_score +
            simgr_scores.get("interest", 0.5) * weights.interest_score +
            simgr_scores.get("market", 0.5) * weights.market_score +
            simgr_scores.get("growth", 0.5) * weights.growth_score +
            simgr_scores.get("risk", 0.5) * weights.risk_score
        )

        total_score = self.normalizer.clamp(total_score)

        # Build breakdown
        breakdown = {
            "study_score": round(simgr_scores.get("study", 0.5), 4),
            "interest_score": round(simgr_scores.get("interest", 0.5), 4),
            "market_score": round(simgr_scores.get("market", 0.5), 4),
            "growth_score": round(simgr_scores.get("growth", 0.5), 4),
            "risk_score": round(simgr_scores.get("risk", 0.5), 4),
        }

        if self.config.debug_mode:
            breakdown.update({
                "study_details": details.get("study_details", {}),
                "interest_details": details.get("interest_details", {}),
                "market_details": details.get("market_details", {}),
                "growth_details": details.get("growth_details", {}),
                "risk_details": details.get("risk_details", {}),
            })

        return total_score, breakdown
    
    def _compute_component(
        self,
        component_name: str,
        user: UserProfile,
        career: CareerData
    ) -> ScoreResult:
        """Compute single component score.

        Args:
            component_name: Name of component (from SIMGR)
            user: User profile
            career: Career profile

        Returns:
            ScoreResult with value [0,1] and meta dict
        """
        from backend.scoring.models import ScoreResult

        component_fn: Callable = self.config.component_map.get(
            component_name
        )

        if not component_fn:
            logger.warning(f"Component {component_name} not found")
            return ScoreResult(value=0.5, meta={})

        # Call component function
        result = component_fn(career, user, self.config)

        # Validate output
        if not isinstance(result, ScoreResult):
            raise TypeError(
                f"Component {component_name} returned {type(result)}, "
                f"expected ScoreResult"
            )

        # Clamp score to [0, 1]
        result.value = self.normalizer.clamp(float(result.value))

        if not isinstance(result.meta, dict):
            raise TypeError(
                f"Component {component_name} returned non-dict meta: "
                f"{type(result.meta)}"
            )

        return result

