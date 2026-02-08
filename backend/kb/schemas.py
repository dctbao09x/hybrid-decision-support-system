# backend/kb/schemas.py
"""
Pydantic Schemas for Validation & Serialization (Production-ready)
"""

from datetime import datetime
from typing import List, Optional
from enum import Enum

from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    model_validator,
)


# ======================================================
# ENUMS
# ======================================================

class RequirementTypeEnum(str, Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class ProficiencyLevelEnum(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SkillCategoryEnum(str, Enum):
    TECHNICAL = "technical"
    SOFT = "soft"
    DOMAIN = "domain"
    TOOL = "tool"
    LANGUAGE = "language"


# ======================================================
# BASE CONFIG (Pydantic v2)
# ======================================================

class ORMBase(BaseModel):
    """Base schema for ORM mapping"""

    model_config = ConfigDict(from_attributes=True)


# ======================================================
# SKILL SCHEMAS
# ======================================================

class SkillBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: Optional[str] = Field(None, max_length=100)

    category: SkillCategoryEnum = SkillCategoryEnum.TECHNICAL

    description: Optional[str] = Field(None, max_length=2000)


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)

    category: Optional[SkillCategoryEnum] = None

    description: Optional[str] = Field(None, max_length=2000)

    is_active: Optional[bool] = None


class Skill(SkillBase, ORMBase):
    id: int

    is_active: bool

    created_at: datetime
    updated_at: datetime


# ======================================================
# DOMAIN SCHEMAS
# ======================================================

class DomainBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)

    description: Optional[str] = Field(None, max_length=2000)

    icon: Optional[str] = Field(None, max_length=20)


class DomainCreate(DomainBase):
    interests: List[str] = Field(default_factory=list)


class DomainUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=50)

    description: Optional[str] = Field(None, max_length=2000)

    icon: Optional[str] = Field(None, max_length=20)


class DomainInterest(ORMBase):
    id: int
    interest_name: str


class Domain(DomainBase, ORMBase):
    id: int

    created_at: datetime
    updated_at: datetime

    interests: List[DomainInterest] = Field(default_factory=list)


# ======================================================
# CAREER SKILL SCHEMAS
# ======================================================

class CareerSkillBase(BaseModel):
    skill_id: int = Field(..., gt=0)

    requirement_type: RequirementTypeEnum = RequirementTypeEnum.REQUIRED

    proficiency_level: ProficiencyLevelEnum = ProficiencyLevelEnum.INTERMEDIATE


class CareerSkillCreate(CareerSkillBase):
    pass


class CareerSkillDetail(ORMBase):
    id: int

    skill: Skill

    requirement_type: RequirementTypeEnum
    proficiency_level: ProficiencyLevelEnum


# ======================================================
# ROADMAP SCHEMAS
# ======================================================

class RoadmapBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)

    description: Optional[str] = Field(None, max_length=3000)

    step_order: int = Field(..., ge=1)

    level: Optional[str] = Field(None, max_length=50)

    duration_months: Optional[int] = Field(None, ge=1, le=240)


class RoadmapCreate(RoadmapBase):
    pass


class RoadmapUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)

    description: Optional[str] = Field(None, max_length=3000)

    step_order: Optional[int] = Field(None, ge=1)

    level: Optional[str] = Field(None, max_length=50)

    duration_months: Optional[int] = Field(None, ge=1, le=240)


class Roadmap(RoadmapBase, ORMBase):
    id: int

    career_id: int

    created_at: datetime
    updated_at: datetime


# ======================================================
# CAREER SCHEMAS
# ======================================================

class CareerBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)

    slug: Optional[str] = Field(None, max_length=100)

    domain_id: int = Field(..., gt=0)

    description: Optional[str] = Field(None, max_length=5000)

    icon: Optional[str] = Field(None, max_length=20)

    education_min: Optional[str] = Field(None, max_length=50)

    ai_relevance: float = Field(0.5, ge=0.0, le=1.0)

    competition: float = Field(0.5, ge=0.0, le=1.0)

    growth_rate: float = Field(0.5, ge=0.0, le=1.0)

    salary_range_min: Optional[int] = Field(None, ge=0)

    salary_range_max: Optional[int] = Field(None, ge=0)

    # ---------------- Validation ----------------

    @model_validator(mode="after")
    def validate_salary_range(self):

        if (
            self.salary_range_min is not None
            and self.salary_range_max is not None
            and self.salary_range_min > self.salary_range_max
        ):
            raise ValueError("salary_range_min must be <= salary_range_max")

        return self


class CareerCreate(CareerBase):
    skills: List[CareerSkillCreate] = Field(default_factory=list)

    roadmaps: List[RoadmapCreate] = Field(default_factory=list)


class CareerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)

    domain_id: Optional[int] = Field(None, gt=0)

    description: Optional[str] = Field(None, max_length=5000)

    icon: Optional[str] = Field(None, max_length=20)

    education_min: Optional[str] = Field(None, max_length=50)

    ai_relevance: Optional[float] = Field(None, ge=0.0, le=1.0)

    competition: Optional[float] = Field(None, ge=0.0, le=1.0)

    growth_rate: Optional[float] = Field(None, ge=0.0, le=1.0)

    salary_range_min: Optional[int] = Field(None, ge=0)

    salary_range_max: Optional[int] = Field(None, ge=0)

    is_active: Optional[bool] = None


class Career(CareerBase, ORMBase):
    id: int

    is_active: bool

    created_at: datetime
    updated_at: datetime

    domain: Optional[Domain] = None


class CareerDetail(Career):
    career_skills: List[CareerSkillDetail] = Field(default_factory=list)

    roadmaps: List[Roadmap] = Field(default_factory=list)


# ======================================================
# EDUCATION LEVEL SCHEMAS
# ======================================================

class EducationLevelBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)

    hierarchy_level: int = Field(..., ge=1)

    description: Optional[str] = Field(None, max_length=2000)


class EducationLevelCreate(EducationLevelBase):
    pass


class EducationLevel(EducationLevelBase, ORMBase):
    id: int


# ======================================================
# QUERY / FILTER SCHEMAS
# ======================================================

class CareerFilter(BaseModel):
    domain_id: Optional[int] = None

    education_min: Optional[str] = None

    is_active: Optional[bool] = True

    min_ai_relevance: Optional[float] = Field(None, ge=0.0, le=1.0)

    max_competition: Optional[float] = Field(None, ge=0.0, le=1.0)

    search: Optional[str] = Field(None, max_length=200)
