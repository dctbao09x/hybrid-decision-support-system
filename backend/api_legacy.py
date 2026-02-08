# backend/api.py
from rule_engine.job_database import JOB_DATABASE
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# Add backend to path for imports
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from processor import process_user_profile

# ==================== PYDANTIC SCHEMAS ====================

class PersonalInfo(BaseModel):
    fullName: str
    age: str
    education: str


class ChatMessage(BaseModel):
    role: str
    text: str


class UserProfileRequest(BaseModel):
    personalInfo: PersonalInfo
    interests: List[str]
    skills: str
    careerGoal: str
    chatHistory: Optional[List[ChatMessage]] = []


class UserProfileResponse(BaseModel):
    age: int
    education_level: str
    interest_tags: List[str]
    skill_tags: List[str]
    goal_cleaned: str
    intent: str
    chat_summary: str
    confidence_score: float


class RecommendationsRequest(BaseModel):
    processedProfile: Optional[Dict[str, Any]] = None
    userProfile: Optional[Dict[str, Any]] = None
    assessmentAnswers: Optional[Dict[str, Any]] = None
    chatHistory: Optional[List[ChatMessage]] = None


class ChatRequest(BaseModel):
    message: str
    chatHistory: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    reply: str


# ==================== FASTAPI APP ====================

app = FastAPI(
    title="Career Guidance AI API",
    description="Hybrid Decision Support System for Career Guidance",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ 
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== ENDPOINTS ====================

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Career Guidance AI API is running",
        "version": "1.0.0"
    }


@app.post("/analyze", response_model=UserProfileResponse)
def analyze_profile(request: UserProfileRequest):
    """
    Analyze user profile and return processed data
    
    Args:
        request: User profile data from frontend
        
    Returns:
        Processed profile with extracted features
    """
    try:
        # Convert Pydantic model to dict
        profile_dict = {
            "personalInfo": {
                "fullName": request.personalInfo.fullName,
                "age": request.personalInfo.age,
                "education": request.personalInfo.education
            },
            "interests": request.interests,
            "skills": request.skills,
            "careerGoal": request.careerGoal,
            "chatHistory": [
                {"role": msg.role, "text": msg.text}
                for msg in request.chatHistory
            ]
        }
        
        # Process profile
        result = process_user_profile(profile_dict)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing profile: {str(e)}"
        )


def _build_profile_dict(
    user_profile: Dict[str, Any],
    chat_history: Optional[List[ChatMessage]] = None
) -> Dict[str, Any]:
    return {
        "personalInfo": {
            "fullName": user_profile.get("fullName", ""),
            "age": user_profile.get("age", ""),
            "education": user_profile.get("education", "")
        },
        "interests": user_profile.get("interests", []),
        "skills": user_profile.get("skills", ""),
        "careerGoal": user_profile.get("careerGoal", ""),
        "chatHistory": [
            {"role": msg.role, "text": msg.text}
            for msg in (chat_history or [])
        ]
    }


def _slugify(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")


def _icon_for_domain(domain: str) -> str:
    mapping = {
        "AI": "🤖",
        "Data": "📊",
        "Software": "💻",
        "Cloud": "☁️",
        "Security": "🛡️",
        "Business": "📈",
        "Design": "🎨",
        "Marketing": "📣",
        "Media": "📝",
        "Engineering": "⚙️",
        "Finance": "💰",
        "Education": "🎓",
        "IT": "🖧",
        "Entrepreneurship": "🚀"
    }
    return mapping.get(domain, "💼")


@app.post("/recommendations")
def get_recommendations(request: RecommendationsRequest):
    # Lazy imports to avoid startup failures if optional deps are missing
    from embedding_engine import match_careers
    from rule_engine.rule_engine import RuleEngine
    from rule_engine.job_database import get_job_requirements

    processed = request.processedProfile

    if not processed:
        if not request.userProfile:
            raise HTTPException(
                status_code=400,
                detail="userProfile or processedProfile is required"
            )
        profile_dict = _build_profile_dict(
            request.userProfile,
            request.chatHistory
        )
        processed = process_user_profile(profile_dict)

    similarity_list = match_careers(processed, top_k=50)
    similarity_scores = {
        item["career"]: item["similarity"]
        for item in similarity_list
    }

    processed_with_similarity = {
        **processed,
        "similarity_scores": similarity_scores
    }

    engine = RuleEngine()
    rule_result = engine.process_profile(processed_with_similarity)
    ranked_jobs = rule_result.get("filtered_jobs") or rule_result.get("ranked_jobs", [])

@app.post("/recommendations")
def get_recommendations(request: RecommendationsRequest):

    # Lazy imports
    from embedding_engine import match_careers
    from rule_engine.rule_engine import RuleEngine
    from rule_engine.job_database import (
        get_job_requirements,
        get_all_jobs
    )

    # ==================== BUILD PROFILE ====================

    processed = request.processedProfile

    if not processed:

        if not request.userProfile:
            raise HTTPException(
                status_code=400,
                detail="userProfile or processedProfile is required"
            )

        profile_dict = _build_profile_dict(
            request.userProfile,
            request.chatHistory
        )

        processed = process_user_profile(profile_dict)

    # ==================== LOAD ALL JOBS ====================

    all_jobs = get_all_jobs()
    total_jobs = len(all_jobs)

    if total_jobs == 0:
        raise HTTPException(
            status_code=500,
            detail="Job database is empty"
        )

    # ==================== EMBEDDING MATCH ====================

    similarity_list = match_careers(
        processed,
        candidates=all_jobs,
        top_k=total_jobs
    )

    similarity_scores = {
        item["career"]: item["similarity"]
        for item in similarity_list
    }

    processed["similarity_scores"] = similarity_scores

    # ==================== RULE ENGINE ====================

    engine = RuleEngine()
    rule_result = engine.process_profile(processed)

    ranked_jobs = (
        rule_result.get("filtered_jobs")
        or rule_result.get("ranked_jobs")
        or rule_result.get("all_jobs")
        or []
    )

    # ==================== DEBUG ====================

    print("TOTAL JOBS IN DB:", total_jobs)
    print("TOTAL AFTER RULE:", len(ranked_jobs))

    # ==================== BUILD RESPONSE ====================

    recommendations = []

    for job_eval in ranked_jobs:

        job_name = job_eval.get("job")

        if not job_name:
            continue

        reqs = get_job_requirements(job_name) or {}

        domain = reqs.get("domain", "Unknown")

        recommendations.append({

            "id": _slugify(job_name),

            "name": job_name,

            "icon": _icon_for_domain(domain),

            "domain": domain,

            "description": reqs.get(
                "description",
                f"{job_name} thuộc lĩnh vực {domain}."
            ),

            "matchScore": round(
                float(job_eval.get("score", 0.0)), 3
            ),

            "growthRate": float(
                reqs.get("growth_rate", 0.5)
            ),

            "competition": float(
                reqs.get("competition", 0.5)
            ),

            "aiRelevance": float(
                reqs.get("ai_relevance", 0.5)
            ),

            "requiredSkills": reqs.get(
                "required_skills", []
            ),

            "tags": job_eval.get("tags", [])
        })

    # ==================== FINAL RESPONSE ====================

    return {
        "total": len(recommendations),

        "processedProfile": processed,

        "recommendations": recommendations,

        "meta": {
            "flags": rule_result.get("flags", []),
            "warnings": rule_result.get("warnings", []),

            "total_jobs_in_db": total_jobs,

            "jobs_after_rule": len(ranked_jobs)
        }
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    text = request.message.strip().lower()

    if not text:
        return ChatResponse(reply="Bạn có thể chia sẻ thêm không?")

    if "ai" in text or "trí tuệ nhân tạo" in text or "machine learning" in text:
        reply = "AI/ML là mảng rất tiềm năng. Bạn đã có nền tảng lập trình nào chưa?"
    elif "thiết kế" in text or "design" in text or "ui" in text:
        reply = "Thiết kế là mảng sáng tạo. Bạn quan tâm UI/UX hay graphic?"
    elif "data" in text or "dữ liệu" in text:
        reply = "Data là mảng có nhiều cơ hội. Bạn thích phân tích hay xây hệ thống dữ liệu?"
    elif "backend" in text or "server" in text:
        reply = "Backend cần nền tảng về API và database. Bạn đã dùng ngôn ngữ nào?"
    else:
        reply = "Cảm ơn bạn đã chia sẻ. Bạn có thể nói rõ hơn về mục tiêu nghề nghiệp không?"

    return ChatResponse(reply=reply)


@app.get("/health")
def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "services": {
            "processor": "ok",
            "api": "ok"
        }
    }


# ==================== RUN ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0",reload=False,log_level="info",port=8000)