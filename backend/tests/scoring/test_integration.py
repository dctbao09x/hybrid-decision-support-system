"""
Integration tests for scoring pipeline.

Tests end-to-end scoring with baseline validation.
"""

import pytest
import json
import os
from backend.scoring import rank_careers, score_jobs
from backend.scoring.models import UserProfile, CareerData
from backend.scoring.baseline_capture import create_baseline_user, create_baseline_careers


class TestBaselineValidation:
    """Test that refactored scoring matches baseline within ±2%."""

    @pytest.fixture
    def baseline_data(self):
        """Load baseline data."""
        baseline_file = "backend/tests/scoring/baseline.json"
        if not os.path.exists(baseline_file):
            pytest.skip("Baseline file not found. Run baseline_capture.py first.")

        with open(baseline_file, "r") as f:
            return json.load(f)

    def test_rank_careers_baseline_compatibility(self, baseline_data):
        """Test rank_careers output matches baseline."""
        user_data = baseline_data["user_profile"]
        career_data_list = baseline_data["careers"]
        expected_results = baseline_data["results"]

        # Reconstruct objects
        user = UserProfile(**user_data)
        careers = [CareerData(**c) for c in career_data_list]

        # Run scoring
        results = rank_careers(user, careers)

        # Validate each result
        for expected, actual in zip(expected_results, results):
            assert expected["career_name"] == actual.career_name
            assert expected["rank"] == actual.rank

            # Check total score within ±2%
            expected_score = expected["total_score"]
            actual_score = actual.total_score
            deviation = abs(actual_score - expected_score)
            assert deviation <= 0.02, f"Score deviation too large for {actual.career_name}: {deviation}"

            # Check breakdown scores within ±2%
            for key in ["study_score", "interest_score", "market_score", "growth_score", "risk_score"]:
                expected_val = expected["breakdown"][key]
                actual_val = getattr(actual.breakdown, key)
                deviation = abs(actual_val - expected_val)
                assert deviation <= 0.02, f"{key} deviation too large for {actual.career_name}: {deviation}"

    def test_score_jobs_new_interface(self):
        """Test new score_jobs interface."""
        user = create_baseline_user()
        careers = create_baseline_careers()

        results = score_jobs(careers, user)

        assert len(results) == len(careers)
        for result in results:
            assert hasattr(result, "contributions")
            assert "study" in result.contributions
            assert "weight" in result.contributions["study"]
            assert "contribution" in result.contributions["study"]

    def test_score_jobs_contributions_calculation(self):
        """Test contributions are calculated correctly."""
        user = UserProfile(skills=["python"])
        careers = [CareerData(name="Engineer", required_skills=["python"])]

        results = score_jobs(careers, user)

        result = results[0]
        for component in ["study", "interest", "market", "growth", "risk"]:
            weight = result.contributions[component]["weight"]
            contribution = result.contributions[component]["contribution"]
            score = getattr(result.breakdown, f"{component}_score")

            # Contribution should be weight * score
            expected_contribution = weight * score
            assert abs(contribution - expected_contribution) < 0.0001


class TestEndToEndPipeline:
    """Test complete scoring pipeline."""

    def test_full_pipeline_execution(self):
        """Test full pipeline from user profile to scored results."""
        user = UserProfile(
            skills=["python", "machine learning", "sql"],
            interests=["AI", "data science"],
            education_level="master",
            ability_score=0.8,
            confidence_score=0.7
        )

        careers = [
            CareerData(
                name="Data Scientist",
                required_skills=["python", "statistics"],
                preferred_skills=["machine learning", "sql"],
                domain="data science",
                domain_interests=["AI"],
                ai_relevance=0.9,
                growth_rate=0.85,
                competition=0.6,
            ),
            CareerData(
                name="Software Engineer",
                required_skills=["python"],
                preferred_skills=["system design"],
                domain="software",
                ai_relevance=0.7,
                growth_rate=0.7,
                competition=0.8,
            ),
        ]

        # Test rank_careers (legacy)
        ranked_results = rank_careers(user, careers)
        assert len(ranked_results) == 2
        assert ranked_results[0].total_score >= ranked_results[1].total_score

        # Test score_jobs (new)
        scored_results = score_jobs(careers, user)
        assert len(scored_results) == 2

        # Results should be in same order
        for legacy, new in zip(ranked_results, scored_results):
            assert legacy.career_name == new.career_name
            assert legacy.total_score == new.total_score

    def test_pipeline_determinism(self):
        """Test pipeline produces identical results."""
        user = create_baseline_user()
        careers = create_baseline_careers()

        # Run multiple times
        results1 = rank_careers(user, careers)
        results2 = rank_careers(user, careers)

        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.total_score == r2.total_score
            assert r1.career_name == r2.career_name
            assert r1.rank == r2.rank

    def test_pipeline_error_handling(self):
        """Test pipeline handles errors gracefully."""
        user = UserProfile()
        careers = []  # Empty list

        results = rank_careers(user, careers)
        assert results == []

        # Invalid user
        results = rank_careers(None, careers)
        assert results == []


class TestNormalizerIntegration:
    """Test normalizer integration with scoring."""

    def test_analyze_output_to_user_profile(self):
        """Test converting analyze output to UserProfile."""
        from backend.scoring.normalizer import Prompt3Normalizer

        analyze_output = {
            "age": 25,
            "education_level": "bachelor",
            "interest_tags": ["AI", "machine learning"],
            "skill_tags": ["python", "sql"],
            "goal_cleaned": "Become AI engineer",
            "intent": "career_change",
            "chat_summary": "Interested in AI",
            "confidence_score": 0.8
        }

        user_profile = Prompt3Normalizer.normalize_user_profile_from_analyze(analyze_output)

        assert isinstance(user_profile, UserProfile)
        assert user_profile.skills == ["python", "sql"]
        assert user_profile.interests == ["AI", "machine learning"]
        assert user_profile.education_level == "bachelor"
        assert user_profile.ability_score == 0.8
        assert user_profile.confidence_score == 0.8

    def test_invalid_analyze_output_raises_error(self):
        """Test invalid analyze output raises ValueError."""
        from backend.scoring.normalizer import Prompt3Normalizer

        invalid_output = {
            "age": "invalid",  # Should be int
            "education_level": "bachelor",
            "interest_tags": ["AI"],
            "skill_tags": ["python"],
            "goal_cleaned": "Goal",
            "intent": "intent",
            "chat_summary": "summary",
            "confidence_score": 0.8
        }

        with pytest.raises(ValueError):
            Prompt3Normalizer.normalize_user_profile_from_analyze(invalid_output)
