# backend/rule_engine/rule_engine.py
"""
Core Rule Engine - Áp dụng và quản lý các rule
"""
from typing import Dict, List, Any
from .rule_base import Rule, RuleResult
from .job_database import get_job_requirements, get_all_jobs
from .rules import *


class RuleEngine:
    """Rule Engine chính để xử lý logic cứng"""
    
    def __init__(self):
        """Khởi tạo engine với tất cả rules"""
        self.rules: List[Rule] = []
        self._load_default_rules()
    
    def _load_default_rules(self):
        """Load tất cả rule mặc định"""
        # Eligibility rules
        self.add_rule(AgeEligibilityRule())
        self.add_rule(EducationEligibilityRule())
        
        # Skill matching rules
        self.add_rule(RequiredSkillRule())
        self.add_rule(PreferredSkillRule())
        self.add_rule(SkillCountRule())
        
        # Confidence rules
        self.add_rule(ConfidenceLevelRule())
        self.add_rule(DataCompletenessRule())
        
        # Risk detection rules
        self.add_rule(InterestSkillGapRule())
        self.add_rule(SimilarityMismatchRule())
        self.add_rule(DifficultyMismatchRule())
        
        # Priority rules
        self.add_rule(IntentAlignmentRule())
        self.add_rule(InterestMatchRule())
        self.add_rule(SimilarityBoostRule())
        
        # Market rules
        self.add_rule(CompetitionRule())
        self.add_rule(GrowthRateRule())
        self.add_rule(AIRelevanceRule())
        self.add_rule(DomainMatchRule())
        
        # Sắp xếp theo priority (cao -> thấp)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def add_rule(self, rule: Rule):
        """Thêm rule mới vào engine"""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def remove_rule(self, rule_name: str):
        """Xóa rule theo tên"""
        self.rules = [r for r in self.rules if r.name != rule_name]
    
    def evaluate_job(self, profile: Dict, job_name: str) -> Dict[str, Any]:
        """
        Đánh giá một ngành nghề cụ thể
        
        Args:
            profile: Hồ sơ người dùng đã xử lý
            job_name: Tên ngành nghề
            
        Returns:
            Kết quả đánh giá
        """
        job_requirements = get_job_requirements(job_name)
        if not job_requirements:
            return None
        
        # Thêm tên job vào requirements để rule sử dụng
        job_requirements["name"] = job_name
        
        # Kết quả tổng hợp
        result = RuleResult()
        
        # Áp dụng từng rule
        for rule in self.rules:
            rule_result = rule.evaluate(profile, job_requirements)
            result.merge(rule_result)
        
        return {
            "job": job_name,
            "passed": result.passed,
            "score_delta": round(result.score_delta, 3),
            "flags": result.flags,
            "warnings": result.warnings
        }
    
    def process_profile(self, profile: Dict) -> Dict[str, Any]:
        """
        Xử lý toàn bộ hồ sơ và trả về kết quả
        
        Args:
            profile: Hồ sơ từ Input Processing Layer
            
        Returns:
            {
                "filtered_jobs": [...],
                "ranked_jobs": [...],
                "flags": [...],
                "warnings": [...]
            }
        """
        all_jobs = get_all_jobs()
        job_evaluations = []
        
        # Đánh giá từng ngành
        for job_name in all_jobs:
            eval_result = self.evaluate_job(profile, job_name)
            if eval_result and eval_result["passed"]:
                job_evaluations.append(eval_result)
        
        # Tính điểm cuối cho mỗi ngành
        for job_eval in job_evaluations:
            # Điểm base từ similarity (nếu có)
            similarity_scores = profile.get("similarity_scores", {})
            base_score = similarity_scores.get(job_eval["job"], 0.5)
            
            # Điểm cuối = base + delta
            final_score = max(0.0, min(1.0, base_score + job_eval["score_delta"]))
            job_eval["score"] = round(final_score, 3)
        
        # Sắp xếp theo điểm giảm dần
        ranked_jobs = sorted(job_evaluations, key=lambda x: x["score"], reverse=True)
        
        # Lọc ngành (loại bỏ điểm quá thấp)
        filtered_jobs = [job for job in ranked_jobs if job["score"] >= 0.2]
        
        # Tổng hợp flags và warnings
        all_flags = set()
        all_warnings = set()
        
        for job in filtered_jobs:
            all_flags.update(job.get("flags", []))
            all_warnings.update(job.get("warnings", []))
        
        return {
            "filtered_jobs": [
                {
                    "job": job["job"],
                    "score": job["score"],
                    "tags": job.get("flags", [])
                }
                for job in filtered_jobs
            ],
            "ranked_jobs": [
                {
                    "job": job["job"],
                    "score": job["score"],
                    "tags": job.get("flags", [])
                }
                for job in ranked_jobs
            ],
            "flags": sorted(list(all_flags)),
            "warnings": sorted(list(all_warnings)),
            "total_jobs_evaluated": len(all_jobs),
            "jobs_passed": len(filtered_jobs)
        }