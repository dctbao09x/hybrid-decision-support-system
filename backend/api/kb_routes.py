"""
FastAPI routes for Knowledge Base
(API Layer - Thin Controller)
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from kb import schemas, service
from kb.database import get_db


router = APIRouter(
    prefix="/kb",
    tags=["Knowledge Base"]
)


# =====================================================
# DEPENDENCY
# =====================================================

def get_kb_service(
    db: Session = Depends(get_db),
) -> service.KnowledgeBaseService:

    return service.KnowledgeBaseService(db)


# =====================================================
# ERROR HANDLER
# =====================================================

def handle_service_error(exc: ValueError):

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc)
    )


def handle_unexpected_error(exc: Exception):
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error"
    )


# =====================================================
# DOMAIN
# =====================================================

@router.post(
    "/domains",
    response_model=schemas.Domain,
    status_code=status.HTTP_201_CREATED
)
def create_domain(
    domain: schemas.DomainCreate,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    try:
        return kb.create_domain(domain)

    except ValueError as e:
        handle_service_error(e)


@router.get(
    "/domains",
    response_model=List[schemas.Domain]
)
def list_domains(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    return kb.list_domains(skip, limit)


@router.get(
    "/domains/{domain_id}",
    response_model=schemas.Domain
)
def get_domain(
    domain_id: int,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    domain = kb.get_domain(domain_id)

    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    return domain


@router.put(
    "/domains/{domain_id}",
    response_model=schemas.Domain
)
def update_domain(
    domain_id: int,
    update: schemas.DomainUpdate,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    try:
        return kb.update_domain(domain_id, update)

    except ValueError as e:
        handle_service_error(e)
    except Exception as e:
        handle_unexpected_error(e)


@router.delete(
    "/domains/{domain_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_domain(
    domain_id: int,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    try:
        kb.delete_domain(domain_id)

    except ValueError as e:
        handle_service_error(e)
    except Exception as e:
        handle_unexpected_error(e)


# =====================================================
# SKILL
# =====================================================

@router.post(
    "/skills",
    response_model=schemas.Skill,
    status_code=status.HTTP_201_CREATED
)
def create_skill(
    skill: schemas.SkillCreate,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    try:
        return kb.create_skill(skill)

    except ValueError as e:
        handle_service_error(e)
    except Exception as e:
        handle_unexpected_error(e)


@router.get(
    "/skills",
    response_model=List[schemas.Skill]
)
def list_skills(
    category: Optional[str] = None,
    is_active: Optional[bool] = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    return kb.list_skills(
        category,
        is_active,
        skip,
        limit
    )


@router.get(
    "/skills/{skill_id}",
    response_model=schemas.Skill
)
def get_skill(
    skill_id: int,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    skill = kb.get_skill(skill_id)

    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    return skill


@router.put(
    "/skills/{skill_id}",
    response_model=schemas.Skill
)
def update_skill(
    skill_id: int,
    update: schemas.SkillUpdate,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    try:
        return kb.update_skill(skill_id, update)

    except ValueError as e:
        handle_service_error(e)
    except Exception as e:
        handle_unexpected_error(e)


@router.delete(
    "/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_skill(
    skill_id: int,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    try:
        kb.delete_skill(skill_id)

    except ValueError as e:
        handle_service_error(e)
    except Exception as e:
        handle_unexpected_error(e)


# =====================================================
# CAREER
# =====================================================

@router.post(
    "/careers",
    response_model=schemas.CareerDetail,
    status_code=status.HTTP_201_CREATED
)
def create_career(
    career: schemas.CareerCreate,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    try:
        return kb.create_career(career)

    except ValueError as e:
        handle_service_error(e)
    except Exception as e:
        handle_unexpected_error(e)


@router.get(
    "/careers",
    response_model=List[schemas.Career]
)
def list_careers(
    domain_id: Optional[int] = None,
    education_min: Optional[str] = None,
    is_active: Optional[bool] = True,
    min_ai_relevance: Optional[float] = Query(None, ge=0, le=1),
    max_competition: Optional[float] = Query(None, ge=0, le=1),
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    filters = schemas.CareerFilter(
        domain_id=domain_id,
        education_min=education_min,
        is_active=is_active,
        min_ai_relevance=min_ai_relevance,
        max_competition=max_competition,
        search=search
    )

    return kb.list_careers(filters, skip, limit)


@router.get(
    "/careers/{career_id}",
    response_model=schemas.CareerDetail
)
def get_career(
    career_id: int,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    career = kb.get_career(career_id)

    if not career:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Career not found")

    return career


@router.get(
    "/careers/slug/{slug}",
    response_model=schemas.CareerDetail
)
def get_career_by_slug(
    slug: str,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    career = kb.get_career_by_slug(slug)

    if not career:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Career not found")

    return career


@router.put(
    "/careers/{career_id}",
    response_model=schemas.Career
)
def update_career(
    career_id: int,
    update: schemas.CareerUpdate,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    try:
        return kb.update_career(career_id, update)

    except ValueError as e:
        handle_service_error(e)
    except Exception as e:
        handle_unexpected_error(e)


@router.delete(
    "/careers/{career_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_career(
    career_id: int,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    try:
        kb.delete_career(career_id)

    except ValueError as e:
        handle_service_error(e)
    except Exception as e:
        handle_unexpected_error(e)


@router.post(
    "/careers/{career_id}/skills/{skill_id}",
    status_code=status.HTTP_201_CREATED
)
def add_career_skill(
    career_id: int,
    skill_id: int,
    requirement_type: str = Query("required", regex="^(required|preferred)$"),
    proficiency_level: str = Query(
        "intermediate",
        regex="^(beginner|intermediate|advanced|expert)$"
    ),
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    try:
        kb.add_career_skill(
            career_id,
            skill_id,
            requirement_type,
            proficiency_level
        )

        return {"message": "Skill added"}

    except ValueError as e:
        handle_service_error(e)
    except Exception as e:
        handle_unexpected_error(e)


@router.delete(
    "/careers/{career_id}/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def remove_career_skill(
    career_id: int,
    skill_id: int,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    try:
        kb.remove_career_skill(career_id, skill_id)

    except ValueError as e:
        handle_service_error(e)
    except Exception as e:
        handle_unexpected_error(e)


# =====================================================
# EDUCATION
# =====================================================

@router.get(
    "/education-levels",
    response_model=List[schemas.EducationLevel]
)
def list_education_levels(
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    return kb.list_education_levels()


# =====================================================
# LEGACY
# =====================================================

@router.get("/legacy/job-requirements/{job_name}")
def get_job_requirements(
    job_name: str,
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    data = kb.get_job_requirements(job_name)

    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return data


@router.get("/legacy/all-jobs")
def get_all_jobs(
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    return kb.get_all_jobs()


@router.get("/legacy/domain-interest-map")
def get_domain_interest_map(
    kb: service.KnowledgeBaseService = Depends(get_kb_service)
):

    return kb.get_domain_interest_map()
