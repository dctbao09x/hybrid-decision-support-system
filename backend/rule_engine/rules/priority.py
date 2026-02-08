# backend/rule_engine/rules/priority.py
"""
Priority Rules - Luật ưu tiên nghề nghiệp
"""
from typing import Dict, Any, Iterable, Mapping
from ..rule_base import Rule
from ..taxonomy_adapter import normalize_interest_list


def _to_lower_set(values: Iterable[Any]) -> set:
    result = set()
    for value in values or []:
        if isinstance(value, str):
            item = value.strip()
            if item:
                result.add(item.lower())
    return result


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_0_1(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


class IntentAlignmentRule(Rule):
    """Ưu tiên dựa trên ý định của người dùng"""
    
    def __init__(self):
        super().__init__(name="IntentAlignmentRule", priority=75)
    
    def evaluate(self, profile: Dict, job: Dict) -> Dict[str, Any]:
        intent = profile.get("intent", "general")
        competition = _clamp_0_1(_to_float(job.get("competition", 0.5), 0.5))
        growth_rate = _clamp_0_1(_to_float(job.get("growth_rate", 0.5), 0.5))
        
        # Ý định học tập -> ưu tiên ngành có lộ trình rõ ràng
        if intent == "learning_intent":
            return {
                "passed": True,
                "score_delta": 0.05,
                "flags": ["learning_path_available"],
                "warnings": []
            }
        
        # Ý định làm việc ngay -> ưu tiên ngành dễ vào nghề và tăng trưởng tốt
        if intent == "career_intent":
            if competition <= 0.70 and growth_rate >= 0.75:
                return {
                    "passed": True,
                    "score_delta": 0.15,
                    "flags": ["quick_entry_high_growth"],
                    "warnings": []
                }
            elif competition <= 0.70:
                return {
                    "passed": True,
                    "score_delta": 0.1,
                    "flags": ["quick_entry"],
                    "warnings": []
                }
        
        # Ý định chuyển ngành -> cần cân nhắc
        if intent == "switching_intent":
            return {
                "passed": True,
                "score_delta": 0.0,
                "flags": ["career_switch"],
                "warnings": ["Chuyển ngành cần lộ trình học tập phù hợp"]
            }
        
        return {
            "passed": True,
            "score_delta": 0.0,
            "flags": [],
            "warnings": []
        }


class InterestMatchRule(Rule):
    """Ưu tiên ngành khớp với sở thích"""
    
    def __init__(self):
        super().__init__(name="InterestMatchRule", priority=80)
    
    def evaluate(self, profile: Dict, job: Dict) -> Dict[str, Any]:
        from ..job_database import DOMAIN_INTEREST_MAP
        
        user_interests = set(
            i.lower()
            for i in normalize_interest_list(profile.get("interest_tags", []))
        )
        job_domain = job.get("domain", "Unknown")
        if not isinstance(job_domain, str):
            job_domain = str(job_domain)
        
        # Lấy sở thích liên quan đến domain
        relevant_interests = set(
            i.lower()
            for i in normalize_interest_list(
                DOMAIN_INTEREST_MAP.get(job_domain, [])
            )
        )
        
        if not user_interests or not relevant_interests:
            return {
                "passed": True,
                "score_delta": 0.0,
                "flags": [],
                "warnings": []
            }
        
        matched = user_interests & relevant_interests
        match_ratio = len(matched) / len(relevant_interests) if relevant_interests else 0
        
        if match_ratio >= 0.5:
            return {
                "passed": True,
                "score_delta": 0.2,
                "flags": ["strong_interest_match"],
                "warnings": []
            }
        
        if match_ratio > 0:
            return {
                "passed": True,
                "score_delta": 0.1,
                "flags": ["partial_interest_match"],
                "warnings": []
            }
        
        return {
            "passed": True,
            "score_delta": -0.05,
            "flags": ["no_interest_match"],
            "warnings": ["Ngành này không khớp với sở thích đã khai báo"]
        }


class SimilarityBoostRule(Rule):
    """Tăng điểm dựa trên similarity score"""
    
    def __init__(self):
        super().__init__(name="SimilarityBoostRule", priority=85)
    
    def evaluate(self, profile: Dict, job: Dict) -> Dict[str, Any]:
        similarity_scores = profile.get("similarity_scores", {})
        if not isinstance(similarity_scores, Mapping):
            similarity_scores = {}
        job_name = job.get("name", "")
        if not isinstance(job_name, str):
            job_name = str(job_name)
        
        if not job_name or job_name not in similarity_scores:
            return {
                "passed": True,
                "score_delta": 0.0,
                "flags": [],
                "warnings": []
            }
        
        similarity = similarity_scores.get(job_name, 0.0)
        
        if similarity >= 0.8:
            return {
                "passed": True,
                "score_delta": 0.25,
                "flags": ["very_high_similarity"],
                "warnings": []
            }
        
        if similarity >= 0.6:
            return {
                "passed": True,
                "score_delta": 0.15,
                "flags": ["high_similarity"],
                "warnings": []
            }
        
        if similarity < 0.3:
            return {
                "passed": True,
                "score_delta": -0.1,
                "flags": ["low_similarity"],
                "warnings": ["Mục tiêu chưa rõ ràng với ngành này"]
            }
        
        return {
            "passed": True,
            "score_delta": 0.0,
            "flags": [],
            "warnings": []
        }
