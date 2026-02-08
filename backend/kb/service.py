"""
Service layer for Knowledge Base (Business Logic Layer)
"""

from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from . import models, schemas, repository
from taxonomy.facade import taxonomy


class KnowledgeBaseService:
    """
    Main service for Knowledge Base operations
    (Orchestrates Repositories + Business Rules)
    """

    def __init__(self, db: Session):
        self.db = db

    # =====================================================
    # INTERNAL HELPERS
    # =====================================================

    def _require_domain(self, domain_id: int) -> models.Domain:
        domain = repository.DomainRepository.get_by_id(self.db, domain_id)

        if not domain:
            raise ValueError("Domain not found")

        return domain

    def _require_career(self, career_id: int) -> models.Career:
        career = repository.CareerRepository.get_by_id(self.db, career_id)

        if not career:
            raise ValueError("Career not found")

        return career

    def _require_skill(self, skill_id: int) -> models.Skill:
        skill = repository.SkillRepository.get_by_id(self.db, skill_id)

        if not skill:
            raise ValueError("Skill not found")

        return skill

    # =====================================================
    # DOMAIN
    # =====================================================

    def create_domain(
        self,
        domain: schemas.DomainCreate
    ) -> models.Domain:

        exists = repository.DomainRepository.get_by_name(
            self.db,
            domain.name
        )

        if exists:
            raise ValueError("Domain already exists")

        return repository.DomainRepository.create(self.db, domain)


    def get_domain(self, domain_id: int) -> Optional[models.Domain]:

        return repository.DomainRepository.get_by_id(self.db, domain_id)


    def get_domain_by_name(self, name: str) -> Optional[models.Domain]:

        return repository.DomainRepository.get_by_name(self.db, name)


    def list_domains(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[models.Domain]:

        return repository.DomainRepository.get_all(
            self.db,
            skip,
            limit
        )


    def update_domain(
        self,
        domain_id: int,
        domain_update: schemas.DomainUpdate
    ) -> models.Domain:

        self._require_domain(domain_id)

        domain = repository.DomainRepository.update(
            self.db,
            domain_id,
            domain_update
        )

        return domain


    def delete_domain(self, domain_id: int) -> bool:

        self._require_domain(domain_id)

        return repository.DomainRepository.delete(
            self.db,
            domain_id
        )


    # =====================================================
    # SKILL
    # =====================================================

    def create_skill(
        self,
        skill: schemas.SkillCreate
    ) -> models.Skill:

        exists = repository.SkillRepository.get_by_name(
            self.db,
            skill.name
        )

        if exists:
            raise ValueError("Skill already exists")

        return repository.SkillRepository.create(self.db, skill)


    def get_skill(self, skill_id: int) -> Optional[models.Skill]:

        return repository.SkillRepository.get_by_id(self.db, skill_id)


    def get_skill_by_name(self, name: str) -> Optional[models.Skill]:

        return repository.SkillRepository.get_by_name(self.db, name)


    def list_skills(
        self,
        category: Optional[str] = None,
        is_active: Optional[bool] = True,
        skip: int = 0,
        limit: int = 100
    ) -> List[models.Skill]:

        return repository.SkillRepository.get_all(
            self.db,
            category,
            is_active,
            skip,
            limit
        )


    def update_skill(
        self,
        skill_id: int,
        skill_update: schemas.SkillUpdate
    ) -> models.Skill:

        self._require_skill(skill_id)

        return repository.SkillRepository.update(
            self.db,
            skill_id,
            skill_update
        )


    def delete_skill(self, skill_id: int) -> bool:

        self._require_skill(skill_id)

        return repository.SkillRepository.delete(
            self.db,
            skill_id
        )


    def get_or_create_skill(
        self,
        skill_name: str,
        category: str = "technical"
    ) -> models.Skill:

        skill = repository.SkillRepository.get_by_name(
            self.db,
            skill_name
        )

        if skill:
            return skill

        create = schemas.SkillCreate(
            name=skill_name,
            category=category
        )

        return repository.SkillRepository.create(
            self.db,
            create
        )


    # =====================================================
    # CAREER
    # =====================================================

    def create_career(
        self,
        career: schemas.CareerCreate
    ) -> models.Career:

        exists = repository.CareerRepository.get_by_slug(
            self.db,
            career.slug
        ) if career.slug else None

        if exists:
            raise ValueError("Career slug already exists")

        return repository.CareerRepository.create(self.db, career)


    def get_career(
        self,
        career_id: int
    ) -> Optional[models.Career]:

        return repository.CareerRepository.get_by_id(
            self.db,
            career_id
        )


    def get_career_by_name(
        self,
        name: str
    ) -> Optional[models.Career]:

        return repository.CareerRepository.get_by_name(
            self.db,
            name
        )


    def get_career_by_slug(
        self,
        slug: str
    ) -> Optional[models.Career]:

        return repository.CareerRepository.get_by_slug(
            self.db,
            slug
        )


    def list_careers(
        self,
        filters: Optional[schemas.CareerFilter] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[models.Career]:

        return repository.CareerRepository.get_all(
            self.db,
            filters,
            skip,
            limit
        )


    def update_career(
        self,
        career_id: int,
        career_update: schemas.CareerUpdate
    ) -> models.Career:

        self._require_career(career_id)

        return repository.CareerRepository.update(
            self.db,
            career_id,
            career_update
        )


    def delete_career(self, career_id: int) -> bool:

        self._require_career(career_id)

        return repository.CareerRepository.delete(
            self.db,
            career_id
        )


    def add_career_skill(
        self,
        career_id: int,
        skill_id: int,
        requirement_type: str = "required",
        proficiency_level: str = "intermediate"
    ) -> models.CareerSkill:

        self._require_career(career_id)
        self._require_skill(skill_id)

        rel = repository.CareerRepository.add_skill(
            self.db,
            career_id,
            skill_id,
            requirement_type,
            proficiency_level
        )

        if not rel:
            raise ValueError("Relation already exists")

        return rel


    def remove_career_skill(
        self,
        career_id: int,
        skill_id: int
    ) -> bool:

        self._require_career(career_id)
        self._require_skill(skill_id)

        return repository.CareerRepository.remove_skill(
            self.db,
            career_id,
            skill_id
        )


    # =====================================================
    # EDUCATION
    # =====================================================

    def create_education_level(
        self,
        edu: schemas.EducationLevelCreate
    ) -> models.EducationLevel:

        exists = repository.EducationLevelRepository.get_by_name(
            self.db,
            edu.name
        )

        if exists:
            raise ValueError("Education level exists")

        return repository.EducationLevelRepository.create(
            self.db,
            edu
        )


    def list_education_levels(self) -> List[models.EducationLevel]:

        return repository.EducationLevelRepository.get_all(
            self.db
        )


    def get_education_hierarchy(self) -> Dict[str, int]:

        # Taxonomy is the single source of truth for education levels
        mapping: Dict[str, int] = {}
        for entry in taxonomy.manager.education.entries:
            if entry.deprecated:
                continue
            mapping[entry.canonical_label] = entry.priority
            for values in entry.aliases.values():
                for alias in values:
                    mapping[alias] = entry.priority
        return mapping


    # =====================================================
    # RULE ENGINE COMPATIBILITY
    # =====================================================

    def get_job_requirements(
        self,
        job_name: str
    ) -> Dict[str, Any]:

        career = self.get_career_by_name(job_name)

        if not career:
            return {}

        required = []
        preferred = []

        for cs in career.career_skills:

            if cs.requirement_type == models.RequirementType.REQUIRED:
                required.append(cs.skill.name)

            elif cs.requirement_type == models.RequirementType.PREFERRED:
                preferred.append(cs.skill.name)

        # Normalize skills via taxonomy
        required_norm = taxonomy.resolve_skill_list(required, return_ids=False)
        preferred_norm = taxonomy.resolve_skill_list(preferred, return_ids=False)

        return {
            "name": career.name,
            "domain": career.domain.name if career.domain else "Unknown",
            "required_skills": required_norm,
            "preferred_skills": preferred_norm,
            "min_education": taxonomy.resolve_education(
                career.education_min or "",
                return_id=False
            ),
            "ai_relevance": career.ai_relevance,
            "competition": career.competition,
            "growth_rate": career.growth_rate,
        }


    def get_all_jobs(self) -> List[str]:

        careers = self.list_careers(
            filters=schemas.CareerFilter(is_active=True),
            limit=1000
        )

        return [c.name for c in careers]


    def get_job_domain(self, job_name: str) -> str:

        career = self.get_career_by_name(job_name)

        if not career or not career.domain:
            return "Unknown"

        return career.domain.name


    def get_relevant_interests(
        self,
        job_name: str
    ) -> List[str]:

        career = self.get_career_by_name(job_name)

        if not career or not career.domain:
            return []

        return [
            i.interest_name
            for i in career.domain.interests
        ]


    def get_domain_interest_map(self) -> Dict[str, List[str]]:

        domains = self.list_domains(limit=100)

        return {
            d.name: taxonomy.resolve_interest_list(
                [i.interest_name for i in d.interests],
                return_ids=False
            )
            for d in domains
        }

    def get_education_by_name(
        self,
        name: str
    ) -> Optional[models.EducationLevel]:

        return repository.EducationLevelRepository.get_by_name(
            self.db,
            name
        )

