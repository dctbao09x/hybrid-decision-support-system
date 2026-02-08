# backend/rule_engine/rules/__init__.py
"""
Import tất cả các rule
"""
from .eligibility import AgeEligibilityRule, EducationEligibilityRule
from .skill_matching import RequiredSkillRule, PreferredSkillRule, SkillCountRule
from .confidence import ConfidenceLevelRule, DataCompletenessRule
from .risk_detection import InterestSkillGapRule, SimilarityMismatchRule, DifficultyMismatchRule
from .priority import IntentAlignmentRule, InterestMatchRule, SimilarityBoostRule
from .market_rules import CompetitionRule, GrowthRateRule, AIRelevanceRule, DomainMatchRule

__all__ = [
    # Eligibility
    "AgeEligibilityRule",
    "EducationEligibilityRule",
    
    # Skill Matching
    "RequiredSkillRule",
    "PreferredSkillRule",
    "SkillCountRule",
    
    # Confidence
    "ConfidenceLevelRule",
    "DataCompletenessRule",
    
    # Risk Detection
    "InterestSkillGapRule",
    "SimilarityMismatchRule",
    "DifficultyMismatchRule",
    
    # Priority
    "IntentAlignmentRule",
    "InterestMatchRule",
    "SimilarityBoostRule",
    
    # Market Rules
    "CompetitionRule",
    "GrowthRateRule",
    "AIRelevanceRule",
    "DomainMatchRule"
]