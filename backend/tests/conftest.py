# backend/tests/conftest.py
"""
Root conftest.py — shared fixtures for the entire test suite.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


# ─── Temporary directory ───────────────────────────────────────────────
@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


# ─── Sample profile (raw user input) ──────────────────────────────────
@pytest.fixture
def raw_profile():
    return {
        "personalInfo": {
            "age": "22",
            "education_level": "Bachelor",
        },
        "interests": ["AI", "Machine Learning"],
        "skills": "Python, SQL, TensorFlow",
        "careerGoal": "Trở thành AI Engineer",
        "chatHistory": [
            {"role": "user", "text": "Tôi muốn làm AI"},
            {"role": "assistant", "text": "Bạn biết Python chứ?"},
            {"role": "user", "text": "Vâng, tôi biết Python và TensorFlow"},
        ],
    }


# ─── Sample processed profile ─────────────────────────────────────────
@pytest.fixture
def processed_profile():
    return {
        "age": 22,
        "education_level": "Bachelor",
        "interest_tags": ["ai", "machine learning"],
        "skill_tags": ["python", "sql", "tensorflow"],
        "goal_cleaned": "tro thanh AI Engineer",
        "intent": "career_intent",
        "chat_summary": "toi muon lam ai. vang toi biet python va tensorflow",
        "confidence_score": 0.75,
    }


# ─── Sample job record (raw) ──────────────────────────────────────────
@pytest.fixture
def raw_job_record():
    return {
        "job_id": "J001",
        "job_title": "Python Developer",
        "company": "TechCorp",
        "salary": "15 - 25 Triệu",
        "location": "Hồ Chí Minh",
        "url": "https://example.com/job/001",
        "posted_date": "10/01/2026",
        "skills": "Python, Django, SQL",
        "source": "topcv",
        "experience": "2 năm",
        "description": "Tuyển dụng Python Developer có kinh nghiệm",
    }


# ─── Sample crawl records ─────────────────────────────────────────────
@pytest.fixture
def sample_crawl_records():
    return [
        {
            "job_id": f"fix_{i:03d}",
            "job_title": f"Software Engineer {i}",
            "company": f"Company{chr(65 + i % 5)}",
            "url": f"https://topcv.vn/job/fix_{i:03d}",
            "salary": f"{10 + i * 2} - {15 + i * 2} Triệu",
            "location": ["Hồ Chí Minh", "Hà Nội", "Đà Nẵng"][i % 3],
            "skills": ", ".join(["Python", "Java", "SQL"][: (i % 3 + 1)]),
        }
        for i in range(10)
    ]


# ─── Sample scoring components ────────────────────────────────────────
@pytest.fixture
def sample_score_components():
    return {"study": 0.8, "interest": 0.7, "market": 0.6, "growth": 0.5, "risk": 0.3}


# ─── Mock LLM adapter ─────────────────────────────────────────────────
@pytest.fixture
def mock_llm():
    with patch("backend.llm_adapter.analyze_with_llm") as m:
        m.return_value = {
            "recommended_careers": ["AI Engineer", "Data Scientist"],
            "strengths": ["Kỹ năng lập trình tốt"],
            "areas_to_improve": ["Cần thêm kinh nghiệm thực tế"],
            "explanation": "Dựa trên kỹ năng Python và TensorFlow...",
        }
        yield m


# ─── Event loop for async tests (pytest-asyncio auto) ─────────────────
def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "e2e: end-to-end tests (slow)")
    config.addinivalue_line("markers", "integration: integration tests")
    config.addinivalue_line("markers", "regression: regression tests")
