# backend/rule_engine/rules/confidence.py
"""
Confidence Rules - Luật đánh giá độ tin cậy
"""
from typing import Dict, Any
from ..rule_base import Rule


class ConfidenceLevelRule(Rule):
    """Phân loại mức độ tin cậy"""
    
    def __init__(self):
        super().__init__(name="ConfidenceLevelRule", priority=60)
    
    def evaluate(self, profile: Dict, job: Dict) -> Dict[str, Any]:
        confidence = profile.get("confidence_score", 0.0)
        
        if confidence >= 0.8:
            return {
                "passed": True,
                "score_delta": 0.1,
                "flags": ["high_confidence"],
                "warnings": []
            }
        
        if confidence < 0.4:
            return {
                "passed": True,
                "score_delta": -0.1,
                "flags": ["low_confidence"],
                "warnings": ["Hồ sơ chưa đầy đủ, nên bổ sung thêm thông tin"]
            }
        
        return {
            "passed": True,
            "score_delta": 0.0,
            "flags": ["medium_confidence"],
            "warnings": []
        }


class DataCompletenessRule(Rule):
    """Kiểm tra tính đầy đủ của dữ liệu"""
    
    def __init__(self):
        super().__init__(name="DataCompletenessRule", priority=55)
    
    def evaluate(self, profile: Dict, job: Dict) -> Dict[str, Any]:
        completeness_score = 0
        total_fields = 5
        
        if profile.get("age", 0) > 0:
            completeness_score += 1
        if profile.get("education_level") and profile.get("education_level") != "unknown":
            completeness_score += 1
        if profile.get("interest_tags"):
            completeness_score += 1
        if profile.get("skill_tags"):
            completeness_score += 1
        if profile.get("goal_cleaned"):
            completeness_score += 1
        
        completeness_ratio = completeness_score / total_fields
        
        if completeness_ratio < 0.4:
            return {
                "passed": True,
                "score_delta": -0.15,
                "flags": ["incomplete_profile"],
                "warnings": ["Hồ sơ thiếu nhiều thông tin quan trọng"]
            }
        
        if completeness_ratio >= 0.8:
            return {
                "passed": True,
                "score_delta": 0.05,
                "flags": ["complete_profile"],
                "warnings": []
            }
        
        return {
            "passed": True,
            "score_delta": 0.0,
            "flags": [],
            "warnings": []
        }