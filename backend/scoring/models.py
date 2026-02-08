# backend/scoring/models.py
"""
Data models for scoring engine (Pydantic v2 compatible)
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from .taxonomy_adapter import (
    normalize_skill_list,
    normalize_interest_list,
    normalize_education
)

# =========================
# Base Config
# =========================

class BaseSchema(BaseModel):
    """Base schema with strict validation"""

    model_config = ConfigDict(
        extra="forbid",          # Reject unknown fields
        validate_assignment=True
    )


# =========================
# Utils
# =========================

def normalize_str_list(value) -> List[str]:
    """Normalize input to clean lowercase string list"""

    if value is None:
        return []

    if isinstance(value, (set, tuple)):
        value = list(value)

    if isinstance(value, list):
        return [
            str(item).lower().strip()
            for item in value
            if str(item).strip()
        ]

    return []


def normalize_str(value: str) -> str:
    """Normalize single string"""

    if value is None:
        return ""

    return str(value).strip().lower()


# =========================
# User Profile
# =========================

class UserProfile(BaseSchema):
    """User profile for scoring"""

    skills: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)

    education_level: str = Field(default="bachelor")

    ability_score: float = Field(0.5, ge=0.0, le=1.0)
    confidence_score: float = Field(0.5, ge=0.0, le=1.0)

    # -------- Validators --------

    @field_validator("skills", "interests", mode="before")
    @classmethod
    def normalize_lists(cls, v, info):
        # Use taxonomy to normalize strings deterministically
        if info.field_name == "skills":
            return normalize_skill_list(v)
        return normalize_interest_list(v)

    @field_validator("education_level", mode="before")
    @classmethod
    def normalize_education(cls, v):
        return normalize_education(v)


# =========================
# Career Data
# =========================

class CareerData(BaseSchema):
    """Career data for scoring"""

    name: str

    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)

    domain: str = Field(default="general")
    domain_interests: List[str] = Field(default_factory=list)

    ai_relevance: float = Field(0.5, ge=0.0, le=1.0)

    market_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    competition: float = Field(0.5, ge=0.0, le=1.0)
    growth_rate: float = Field(0.5, ge=0.0, le=1.0)

    # -------- Validators --------

    @field_validator("required_skills", "preferred_skills", mode="before")
    @classmethod
    def normalize_skill_lists(cls, v):
        return normalize_skill_list(v)

    @field_validator("domain_interests", mode="before")
    @classmethod
    def normalize_interest_lists(cls, v):
        return normalize_interest_list(v)

    @field_validator("name", "domain", mode="before")
    @classmethod
    def normalize_strings(cls, v):
        return normalize_str(v)

    @field_validator("market_score", mode="before")
    @classmethod
    def default_market_score(cls, v):
        """Fallback when market_score missing"""

        if v is None:
            return 0.5

        return v


# =========================
# Score Weights
# =========================

class ScoreWeights(BaseSchema):
    """Scoring formula weights"""

    skill_match: float = Field(0.4, ge=0.0, le=1.0)
    interest_match: float = Field(0.3, ge=0.0, le=1.0)
    market_score: float = Field(0.2, ge=0.0, le=1.0)
    ability_score: float = Field(0.1, ge=0.0, le=1.0)

    @field_validator("*", mode="after")
    @classmethod
    def check_total_weight(cls, v, info):
        return v

    def validate_sum(self):

        total = (
            self.skill_match
            + self.interest_match
            + self.market_score
            + self.ability_score
        )

        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Score weights must sum to 1.0, got {total}"
            )


# =========================
# Score Breakdown
# =========================

class ScoreBreakdown(BaseSchema):
    """Detailed scoring components"""

    skill_match: float = Field(ge=0.0, le=1.0)
    interest_match: float = Field(ge=0.0, le=1.0)
    market_score: float = Field(ge=0.0, le=1.0)
    ability_score: float = Field(ge=0.0, le=1.0)

    skill_details: Optional[Dict[str, float]] = None
    market_details: Optional[Dict[str, float]] = None


# =========================
# Result Models
# =========================

class ScoredCareer(BaseSchema):
    """Career with final score"""

    career_name: str

    total_score: float = Field(ge=0.0, le=1.0)

    breakdown: ScoreBreakdown

    rank: Optional[int] = Field(None, ge=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "career_name": "ai engineer",
                "total_score": 0.85,
                "breakdown": {
                    "skill_match": 0.90,
                    "interest_match": 0.85,
                    "market_score": 0.80,
                    "ability_score": 0.75
                },
                "rank": 1
            }
        }
    )


# =========================
# Ranking I/O
# =========================

class RankingInput(BaseSchema):
    """Input for ranking engine"""

    user_profile: UserProfile

    eligible_careers: List[CareerData]

    weights: Optional[ScoreWeights] = None


class RankingOutput(BaseSchema):
    """Output from ranking engine"""

    ranked_careers: List[ScoredCareer]

    total_evaluated: int = Field(ge=0)

    weights_used: ScoreWeights
