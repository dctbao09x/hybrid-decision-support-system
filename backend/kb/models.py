# backend/kb/models.py
"""
SQLAlchemy ORM Models for Knowledge Base (Production-ready)
"""

from datetime import datetime
import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint,
    CheckConstraint,
    Index,
    func,
)

from sqlalchemy.orm import (
    declarative_base,
    relationship,
)


# ======================================================
# Base
# ======================================================

Base = declarative_base()


# ======================================================
# Mixins
# ======================================================

class TimestampMixin:
    """Standard timestamp fields"""

    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


# ======================================================
# ENUMS
# ======================================================

class RequirementType(enum.Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class ProficiencyLevel(enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SkillCategory(enum.Enum):
    TECHNICAL = "technical"
    SOFT = "soft"
    DOMAIN = "domain"
    TOOL = "tool"
    LANGUAGE = "language"


# ======================================================
# MODELS
# ======================================================

class Domain(Base, TimestampMixin):
    """Career domain/category"""

    __tablename__ = "domains"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)
    icon = Column(String(20))

    # Relationships
    careers = relationship(
        "Career",
        back_populates="domain",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    interests = relationship(
        "DomainInterest",
        back_populates="domain",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<Domain(id={self.id}, name='{self.name}')>"


# ------------------------------------------------------

class Career(Base, TimestampMixin):
    """Career / Job information"""

    __tablename__ = "careers"

    __table_args__ = (
        CheckConstraint(
            "salary_range_min <= salary_range_max",
            name="ck_salary_range"
        ),
        Index(
            "ix_career_domain_active",
            "domain_id",
            "is_active"
        ),
    )

    id = Column(Integer, primary_key=True)

    domain_id = Column(
        Integer,
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)

    description = Column(Text)
    icon = Column(String(20))

    # Education
    education_min = Column(String(50))

    # Metrics
    ai_relevance = Column(Float, default=0.5, nullable=False)
    competition = Column(Float, default=0.5, nullable=False)
    growth_rate = Column(Float, default=0.5, nullable=False)

    # Salary
    salary_range_min = Column(Integer)
    salary_range_max = Column(Integer)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    domain = relationship(
        "Domain",
        back_populates="careers"
    )

    career_skills = relationship(
        "CareerSkill",
        back_populates="career",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    roadmaps = relationship(
        "Roadmap",
        back_populates="career",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<Career(id={self.id}, name='{self.name}', domain_id={self.domain_id})>"


# ------------------------------------------------------

class Skill(Base, TimestampMixin):
    """Skill entity"""

    __tablename__ = "skills"

    id = Column(Integer, primary_key=True)

    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)

    category = Column(
        Enum(SkillCategory, native_enum=False),
        default=SkillCategory.TECHNICAL,
        nullable=False,
        index=True,
    )

    description = Column(Text)

    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    career_skills = relationship(
        "CareerSkill",
        back_populates="skill",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<Skill(id={self.id}, name='{self.name}', category='{self.category.value}')>"


# ------------------------------------------------------

class CareerSkill(Base):
    """Junction table: Career ↔ Skill"""

    __tablename__ = "career_skills"

    __table_args__ = (
        UniqueConstraint(
            "career_id",
            "skill_id",
            name="uq_career_skill"
        ),
    )

    id = Column(Integer, primary_key=True)

    career_id = Column(
        Integer,
        ForeignKey("careers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    skill_id = Column(
        Integer,
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    requirement_type = Column(
        Enum(RequirementType, native_enum=False),
        default=RequirementType.REQUIRED,
        nullable=False,
    )

    proficiency_level = Column(
        Enum(ProficiencyLevel, native_enum=False),
        default=ProficiencyLevel.INTERMEDIATE,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    career = relationship("Career", back_populates="career_skills")
    skill = relationship("Skill", back_populates="career_skills")

    def __repr__(self):
        return (
            f"<CareerSkill(career_id={self.career_id}, "
            f"skill_id={self.skill_id}, "
            f"type={self.requirement_type.value})>"
        )


# ------------------------------------------------------

class DomainInterest(Base):
    """Domain ↔ Interest mapping"""

    __tablename__ = "domain_interests"

    __table_args__ = (
        UniqueConstraint(
            "domain_id",
            "interest_name",
            name="uq_domain_interest"
        ),
    )

    id = Column(Integer, primary_key=True)

    domain_id = Column(
        Integer,
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    interest_name = Column(String(100), nullable=False)

    # Relationships
    domain = relationship("Domain", back_populates="interests")

    def __repr__(self):
        return (
            f"<DomainInterest(domain_id={self.domain_id}, "
            f"interest='{self.interest_name}')>"
        )


# ------------------------------------------------------

class Roadmap(Base, TimestampMixin):
    """Career progression roadmap"""

    __tablename__ = "roadmaps"

    id = Column(Integer, primary_key=True)

    career_id = Column(
        Integer,
        ForeignKey("careers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(String(200), nullable=False)

    description = Column(Text)

    step_order = Column(Integer, nullable=False)

    level = Column(String(50))  # junior, mid, senior, lead

    duration_months = Column(Integer)

    # Relationships
    career = relationship("Career", back_populates="roadmaps")

    def __repr__(self):
        return (
            f"<Roadmap(id={self.id}, "
            f"career_id={self.career_id}, "
            f"level='{self.level}', "
            f"order={self.step_order})>"
        )


# ------------------------------------------------------

class EducationLevel(Base):
    """Education level hierarchy"""

    __tablename__ = "education_levels"

    id = Column(Integer, primary_key=True)

    name = Column(String(50), unique=True, nullable=False, index=True)

    hierarchy_level = Column(Integer, unique=True, nullable=False)

    description = Column(Text)

    def __repr__(self):
        return (
            f"<EducationLevel(id={self.id}, "
            f"name='{self.name}', "
            f"level={self.hierarchy_level})>"
        )
