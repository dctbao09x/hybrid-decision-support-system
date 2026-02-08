"""
Market-based Rules
Luật đánh giá dựa trên thị trường lao động
"""

from typing import Dict, Any, List
from ..rule_base import Rule
from ..taxonomy_adapter import (
    normalize_skill_list,
    normalize_interest_list
)


# -------------------------
# Helper
# -------------------------

def _safe_list(data) -> List[str]:
    if isinstance(data, list):
        return [str(x) for x in data]
    return []


def _clamp_score(score: float, min_v=-0.3, max_v=0.3) -> float:
    return max(min(score, max_v), min_v)


def _base_result() -> Dict[str, Any]:
    return {
        "passed": True,
        "score_delta": 0.0,
        "flags": [],
        "warnings": []
    }


# =====================================================
# Competition Rule
# =====================================================

class CompetitionRule(Rule):
    """
    Đánh giá mức độ cạnh tranh ngành nghề
    """

    HIGH_COMP = 0.85
    LOW_COMP = 0.65

    def __init__(self):
        super().__init__(
            name="CompetitionRule",
            priority=65
        )

    def evaluate(self, profile: Dict, job: Dict) -> Dict[str, Any]:

        result = _base_result()

        competition = float(job.get("competition", 0.5))
        skill_count = len(
            normalize_skill_list(profile.get("skill_tags", []))
        )
        confidence = float(profile.get("confidence_score", 0.5))

        # Cạnh tranh cao
        if competition >= self.HIGH_COMP:

            if skill_count >= 4 and confidence >= 0.7:

                result["score_delta"] = 0.05
                result["flags"].append("high_competition_ready")

            else:

                result["score_delta"] = -0.1
                result["flags"].append("high_competition_risk")
                result["warnings"].append(
                    "Ngành cạnh tranh cao, hồ sơ hiện tại chưa đủ mạnh"
                )

        # Cạnh tranh thấp
        elif competition <= self.LOW_COMP:

            result["score_delta"] = 0.05
            result["flags"].append("low_competition")

        result["score_delta"] = _clamp_score(result["score_delta"])

        return result


# =====================================================
# Growth Rate Rule
# =====================================================

class GrowthRateRule(Rule):
    """
    Đánh giá tốc độ tăng trưởng ngành
    """

    HIGH_GROWTH = 0.85
    LOW_GROWTH = 0.60

    def __init__(self):
        super().__init__(
            name="GrowthRateRule",
            priority=60
        )

    def evaluate(self, profile: Dict, job: Dict) -> Dict[str, Any]:

        result = _base_result()

        growth = float(job.get("growth_rate", 0.5))
        intent = str(profile.get("intent", "general")).lower()

        # Tăng trưởng cao
        if growth >= self.HIGH_GROWTH:

            bonus = 0.15 if intent == "career_intent" else 0.1

            result["score_delta"] = bonus
            result["flags"].append("high_growth")

        # Tăng trưởng thấp
        elif growth <= self.LOW_GROWTH:

            result["score_delta"] = -0.05
            result["flags"].append("low_growth")

            result["warnings"].append(
                "Ngành có tốc độ tăng trưởng thấp"
            )

        result["score_delta"] = _clamp_score(result["score_delta"])

        return result


# =====================================================
# AI Relevance Rule
# =====================================================

class AIRelevanceRule(Rule):
    """
    Đánh giá mức độ phù hợp với lĩnh vực AI
    """

    HIGH_AI = 0.80
    LOW_AI = 0.50

    AI_INTERESTS = {
        "ai",
        "artificial intelligence",
        "it",
        "technology",
        "machine learning"
    }

    AI_SKILLS = {
        "python",
        "machine learning",
        "deep learning",
        "tensorflow",
        "pytorch",
        "ai"
    }

    def __init__(self):
        super().__init__(
            name="AIRelevanceRule",
            priority=70
        )

    def evaluate(self, profile: Dict, job: Dict) -> Dict[str, Any]:

        result = _base_result()

        relevance = float(job.get("ai_relevance", 0.5))

        interests = set(
            i.lower()
            for i in normalize_interest_list(profile.get("interest_tags", []))
        )
        skills = set(
            s.lower()
            for s in normalize_skill_list(profile.get("skill_tags", []))
        )

        has_interest = bool(interests & self.AI_INTERESTS)
        has_skill = bool(skills & self.AI_SKILLS)

        # Liên quan AI cao
        if relevance >= self.HIGH_AI:

            if has_interest and has_skill:

                result["score_delta"] = 0.15
                result["flags"].append("ai_strong_match")

            elif has_interest:

                result["flags"].append("ai_need_skills")
                result["warnings"].append(
                    "Cần bổ sung kỹ năng AI/ML"
                )

            else:

                result["score_delta"] = -0.1
                result["flags"].append("ai_mismatch")

        # AI thấp nhưng user quan tâm
        elif relevance <= self.LOW_AI and (has_interest or has_skill):

            result["score_delta"] = -0.05
            result["flags"].append("ai_underutilized")

            result["warnings"].append(
                "Năng lực AI chưa được tận dụng"
            )

        result["score_delta"] = _clamp_score(result["score_delta"])

        return result


# =====================================================
# Domain Match Rule
# =====================================================

class DomainMatchRule(Rule):
    """
    Đánh giá độ khớp lĩnh vực
    """

    def __init__(self):
        super().__init__(
            name="DomainMatchRule",
            priority=75
        )

    def evaluate(self, profile: Dict, job: Dict) -> Dict[str, Any]:

        result = _base_result()

        try:
            from ..job_database import DOMAIN_INTEREST_MAP
        except ImportError:
            result["warnings"].append(
                "Không tải được DOMAIN_INTEREST_MAP"
            )
            return result

        domain = str(job.get("domain", "unknown")).lower()

        interests = set(
            i.lower()
            for i in normalize_interest_list(profile.get("interest_tags", []))
        )

        domain_interests = {
            i.lower()
            for i in normalize_interest_list(
                DOMAIN_INTEREST_MAP.get(domain, [])
            )
        }

        if not domain_interests:
            return result

        matched = interests & domain_interests

        ratio = len(matched) / len(domain_interests)

        # Match cao
        if ratio >= 0.5:

            result["score_delta"] = 0.15
            result["flags"].append("domain_match")

        # Match một phần
        elif ratio > 0:

            result["score_delta"] = 0.05
            result["flags"].append("domain_partial")

        # Không match
        else:

            result["score_delta"] = -0.05
            result["flags"].append("domain_mismatch")

            result["warnings"].append(
                f"Lĩnh vực {domain} không khớp sở thích"
            )

        result["score_delta"] = _clamp_score(result["score_delta"])

        return result
