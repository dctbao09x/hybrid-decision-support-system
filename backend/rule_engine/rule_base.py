# backend/rule_engine/rule_base.py
"""
Base classes cho Rule Engine
"""
from typing import Dict, List, Any
from abc import ABC, abstractmethod


class Rule(ABC):
    """Base class cho tất cả các rule"""
    
    def __init__(self, name: str, priority: int = 0):
        """
        Args:
            name: Tên rule
            priority: Độ ưu tiên (số càng cao càng ưu tiên)
        """
        self.name = name
        self.priority = priority
    
    @abstractmethod
    def evaluate(self, profile: Dict, job: Dict) -> Dict[str, Any]:
        """
        Đánh giá rule
        
        Args:
            profile: Hồ sơ người dùng đã xử lý
            job: Thông tin ngành nghề
            
        Returns:
            {
                "passed": bool,
                "score_delta": float,  # Thay đổi điểm (-1.0 đến +1.0)
                "flags": List[str],
                "warnings": List[str]
            }
        """
        pass
    
    def __repr__(self):
        return f"<Rule: {self.name} (priority={self.priority})>"


class RuleResult:
    """Kết quả sau khi áp dụng các rule"""
    
    def __init__(self):
        self.passed = True
        self.score_delta = 0.0
        self.flags = []
        self.warnings = []
    
    def merge(self, result: Dict[str, Any]):
        """Merge kết quả từ một rule"""
        if not result.get("passed", True):
            self.passed = False
        
        self.score_delta += result.get("score_delta", 0.0)
        self.flags.extend(result.get("flags", []))
        self.warnings.extend(result.get("warnings", []))
    
    def to_dict(self) -> Dict:
        return {
            "passed": self.passed,
            "score_delta": self.score_delta,
            "flags": list(set(self.flags)),
            "warnings": list(set(self.warnings))
        }