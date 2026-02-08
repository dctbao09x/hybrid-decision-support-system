# backend/scoring/normalizer.py
"""
Numerical normalization & similarity utilities
"""

from typing import Iterable, Sequence, Set, Union
import math


Number = Union[int, float]


class DataNormalizer:
    """Utilities for normalizing scoring data"""

    EPS = 1e-9


    # =========================
    # Core Utils
    # =========================

    @staticmethod
    def _is_valid_number(x: Number) -> bool:
        """Check finite numeric value"""

        if x is None:
            return False

        if not isinstance(x, (int, float)):
            return False

        return math.isfinite(x)


    @staticmethod
    def clamp(
        value: Number,
        min_val: Number = 0.0,
        max_val: Number = 1.0
    ) -> float:
        """Clamp value between bounds safely"""

        if not DataNormalizer._is_valid_number(value):
            return float(min_val)

        return float(max(min_val, min(max_val, value)))


    # =========================
    # Range Normalization
    # =========================

    @staticmethod
    def normalize_to_range(
        value: Number,
        min_val: Number,
        max_val: Number,
        target_min: Number = 0.0,
        target_max: Number = 1.0
    ) -> float:
        """
        Normalize value from [min_val, max_val] → [target_min, target_max]
        """

        if not all(
            DataNormalizer._is_valid_number(v)
            for v in (value, min_val, max_val, target_min, target_max)
        ):
            return float(target_min)

        if abs(max_val - min_val) < DataNormalizer.EPS:
            return float((target_min + target_max) / 2)

        ratio = (value - min_val) / (max_val - min_val)

        scaled = ratio * (target_max - target_min) + target_min

        return DataNormalizer.clamp(scaled, target_min, target_max)


    @staticmethod
    def normalize_list(values: Iterable[Number]) -> list[float]:
        """Normalize iterable of numbers to [0,1]"""

        if values is None:
            return []

        clean = [
            float(v)
            for v in values
            if DataNormalizer._is_valid_number(v)
        ]

        if not clean:
            return []

        min_val = min(clean)
        max_val = max(clean)

        if abs(max_val - min_val) < DataNormalizer.EPS:
            return [0.5] * len(clean)

        return [
            DataNormalizer.normalize_to_range(v, min_val, max_val)
            for v in clean
        ]


    # =========================
    # Similarities
    # =========================

    @staticmethod
    def jaccard_similarity(
        set1: Set[str],
        set2: Set[str]
    ) -> float:
        """Jaccard similarity in [0,1]"""

        if not set1 or not set2:
            return 0.0

        union = set1 | set2

        if not union:
            return 0.0

        return len(set1 & set2) / len(union)


    @staticmethod
    def cosine_similarity(
        vec1: Sequence[Number],
        vec2: Sequence[Number]
    ) -> float:
        """Cosine similarity with numerical safety"""

        if vec1 is None or vec2 is None:
            return 0.0

        if len(vec1) != len(vec2):
            raise ValueError("Vector length mismatch")

        if not vec1:
            return 0.0

        dot = 0.0
        norm1 = 0.0
        norm2 = 0.0

        for a, b in zip(vec1, vec2):

            if not (
                DataNormalizer._is_valid_number(a)
                and DataNormalizer._is_valid_number(b)
            ):
                continue

            a = float(a)
            b = float(b)

            dot += a * b
            norm1 += a * a
            norm2 += b * b

        if norm1 < DataNormalizer.EPS or norm2 < DataNormalizer.EPS:
            return 0.0

        sim = dot / (math.sqrt(norm1) * math.sqrt(norm2))

        return DataNormalizer.clamp(sim, -1.0, 1.0)


    # =========================
    # Aggregation
    # =========================

    @staticmethod
    def weighted_average(
        values: Iterable[Number],
        weights: Iterable[Number]
    ) -> float:
        """Safe weighted mean"""

        if values is None or weights is None:
            return 0.0

        pairs = [
            (float(v), float(w))
            for v, w in zip(values, weights)
            if (
                DataNormalizer._is_valid_number(v)
                and DataNormalizer._is_valid_number(w)
            )
        ]

        if not pairs:
            return 0.0

        total_weight = sum(w for _, w in pairs)

        if abs(total_weight) < DataNormalizer.EPS:
            return 0.0

        weighted_sum = sum(v * w for v, w in pairs)

        return weighted_sum / total_weight
