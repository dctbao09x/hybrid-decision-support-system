# backend/rule_engine/adapters/kb_adapter.py
"""
Knowledge Base Adapter
Backward compatibility layer for old job_database.py
Improved: caching, TTL, centralized DB access, error handling
"""

from typing import Dict, List, Optional, Callable, TypeVar
from datetime import datetime, timedelta
import logging

from kb.database import get_db_context
from kb.service import KnowledgeBaseService


# ============================
# LOGGING
# ============================

logger = logging.getLogger("kb-adapter")


# ============================
# TYPES
# ============================

T = TypeVar("T")


# ============================
# ADAPTER
# ============================

class KnowledgeBaseAdapter:
    """
    Adapter providing old job_database.py interface
    over new Knowledge Base service
    """

    # Cache TTL (seconds)
    CACHE_TTL = 300


    def __init__(self):

        # Cached objects
        self._education_cache: Optional[Dict[str, int]] = None
        self._domain_interest_cache: Optional[Dict[str, List[str]]] = None

        # Cache timestamps
        self._education_ts: Optional[datetime] = None
        self._domain_ts: Optional[datetime] = None


    # ========================
    # INTERNAL
    # ========================

    def _cache_valid(self, ts: Optional[datetime]) -> bool:

        if ts is None:
            return False

        return (datetime.utcnow() - ts) < timedelta(seconds=self.CACHE_TTL)


    def _with_service(self, fn: Callable[[KnowledgeBaseService], T]) -> T:
        """
        Run function inside DB context with KB service
        """

        try:
            with get_db_context() as db:

                service = KnowledgeBaseService(db)

                return fn(service)

        except Exception as e:

            logger.exception("KB Adapter error: %s", e)

            raise


    # ========================
    # JOBS
    # ========================

    def get_job_requirements(self, job_name: str) -> Dict:

        return self._with_service(
            lambda s: s.get_job_requirements(job_name)
        )


    def get_all_jobs(self) -> List[str]:

        return self._with_service(
            lambda s: s.get_all_jobs()
        )


    def get_jobs_by_domain(self, domain: str) -> List[str]:

        return self._with_service(
            lambda s: s.get_jobs_by_domain(domain)
        )


    def get_job_domain(self, job_name: str) -> str:

        return self._with_service(
            lambda s: s.get_job_domain(job_name)
        )


    def get_relevant_interests(self, job_name: str) -> List[str]:

        return self._with_service(
            lambda s: s.get_relevant_interests(job_name)
        )


    # ========================
    # CACHED
    # ========================

    def get_education_hierarchy(self) -> Dict[str, int]:

        if (
            self._education_cache
            and self._cache_valid(self._education_ts)
        ):
            return self._education_cache

        def load(service: KnowledgeBaseService):

            data = service.get_education_hierarchy()

            self._education_cache = data
            self._education_ts = datetime.utcnow()

            return data

        return self._with_service(load)


    def get_domain_interest_map(self) -> Dict[str, List[str]]:

        if (
            self._domain_interest_cache
            and self._cache_valid(self._domain_ts)
        ):
            return self._domain_interest_cache

        def load(service: KnowledgeBaseService):

            data = service.get_domain_interest_map()

            self._domain_interest_cache = data
            self._domain_ts = datetime.utcnow()

            return data

        return self._with_service(load)


    # ========================
    # CACHE CONTROL
    # ========================

    def clear_cache(self):

        self._education_cache = None
        self._domain_interest_cache = None

        self._education_ts = None
        self._domain_ts = None

        logger.info("KB adapter cache cleared")


    def refresh_cache(self):

        """Force reload all cached data"""

        self.clear_cache()

        self.get_education_hierarchy()
        self.get_domain_interest_map()

        logger.info("KB adapter cache refreshed")


# ============================
# SINGLETON
# ============================

kb_adapter = KnowledgeBaseAdapter()


# ============================
# LEGACY API
# ============================

get_job_requirements = kb_adapter.get_job_requirements
get_all_jobs = kb_adapter.get_all_jobs
get_jobs_by_domain = kb_adapter.get_jobs_by_domain
get_job_domain = kb_adapter.get_job_domain
get_relevant_interests = kb_adapter.get_relevant_interests


# ============================
# LEGACY CONSTANTS
# ============================

class _EducationHierarchy:

    def __getitem__(self, key: str) -> int:

        data = kb_adapter.get_education_hierarchy()

        return data.get(key, 0)


class _DomainInterestMap:

    def __getitem__(self, key: str) -> List[str]:

        data = kb_adapter.get_domain_interest_map()

        return data.get(key, [])


    def get(self, key: str, default=None):

        data = kb_adapter.get_domain_interest_map()

        return data.get(key, default)


EDUCATION_HIERARCHY = _EducationHierarchy()
DOMAIN_INTEREST_MAP = _DomainInterestMap()
