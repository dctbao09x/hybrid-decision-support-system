"""
Job / Career Dataset (Prototype Layer)
Used by Rule Engine and Embedding Engine

NOTE:
This is NOT the official Knowledge Base (Layer 3.6).
This file is only for bootstrapping and experimentation.
"""
from typing import Dict, List, TypedDict
# =====================================================
# SCHEMA DEFINITIONS
# =====================================================

class JobSchema(TypedDict):
    domain: str
    required_skills: List[str]
    education_min: str
    ai_relevance: float
    competition: float
    growth_rate: float

EDUCATION_HIERARCHY: Dict[str, int] = {
    "HighSchool": 1,
    "Associate": 2,
    "Bachelor": 3,
    "Master": 4,
    "PhD": 5,
}

DOMAIN_INTEREST_MAP: Dict[str, List[str]] = {
    "AI": ["IT", "Artificial Intelligence", "Technology", "Science"],
    "Data": ["IT", "Data Science", "Analytics", "Mathematics", "Statistics"],
    "Software": ["IT", "Technology", "Programming", "Engineering"],
    "Cloud": ["IT", "Technology", "Infrastructure"],
    "Security": ["IT", "Technology", "Cybersecurity"],
    "Business": ["Business", "Management", "Economics"],
    "Design": ["Design", "Art", "Creativity"],
    "Marketing": ["Marketing", "Business", "Media"],
    "Media": ["Media", "Content", "Communication", "Art"],
    "Engineering": ["Engineering", "Technology", "Robotics", "Hardware"],
    "Finance": ["Finance", "Economics", "Mathematics"],
    "Education": ["Education", "Teaching"],
    "IT": ["IT", "Technology"],
    "Entrepreneurship": ["Business", "Entrepreneurship", "Innovation"]
}

# ==================== JOB DATABASE ====================

JOB_DATABASE: Dict[str, JobSchema] = {

    # ================= AI / DATA =================

    "AI Engineer": {
        "domain": "AI",
        "required_skills": ["Python", "Machine Learning", "Deep Learning", "PyTorch", "TensorFlow"],
        "education_min": "Bachelor",
        "ai_relevance": 0.95,
        "competition": 0.85,
        "growth_rate": 0.90
    },

    "Machine Learning Engineer": {
        "domain": "AI",
        "required_skills": ["Python", "ML", "Scikit-learn", "MLOps", "Deployment"],
        "education_min": "Bachelor",
        "ai_relevance": 0.90,
        "competition": 0.80,
        "growth_rate": 0.88
    },

    "Data Scientist": {
        "domain": "Data",
        "required_skills": ["Python", "Statistics", "SQL", "Machine Learning", "Pandas"],
        "education_min": "Bachelor",
        "ai_relevance": 0.85,
        "competition": 0.75,
        "growth_rate": 0.85
    },

    "Data Analyst": {
        "domain": "Data",
        "required_skills": ["Excel", "SQL", "Power BI", "Tableau", "Python"],
        "education_min": "Associate",
        "ai_relevance": 0.60,
        "competition": 0.65,
        "growth_rate": 0.75
    },

    "AI Researcher": {
        "domain": "AI",
        "required_skills": ["Math", "Deep Learning", "Research", "Paper Writing"],
        "education_min": "Master",
        "ai_relevance": 0.98,
        "competition": 0.90,
        "growth_rate": 0.80
    },

    # ================= SOFTWARE =================

    "Software Engineer": {
        "domain": "Software",
        "required_skills": ["Programming", "OOP", "Git", "Algorithms"],
        "education_min": "Bachelor",
        "ai_relevance": 0.50,
        "competition": 0.75,
        "growth_rate": 0.80
    },

    "Backend Developer": {
        "domain": "Software",
        "required_skills": ["Python", "Java", "API", "Database", "Docker"],
        "education_min": "Associate",
        "ai_relevance": 0.55,
        "competition": 0.70,
        "growth_rate": 0.78
    },

    "Frontend Developer": {
        "domain": "Software",
        "required_skills": ["JavaScript", "React", "HTML", "CSS", "UX"],
        "education_min": "Associate",
        "ai_relevance": 0.40,
        "competition": 0.72,
        "growth_rate": 0.75
    },

    "Mobile Developer": {
        "domain": "Software",
        "required_skills": ["Flutter", "Kotlin", "Swift", "API"],
        "education_min": "Associate",
        "ai_relevance": 0.45,
        "competition": 0.68,
        "growth_rate": 0.72
    },

    "Game Developer": {
        "domain": "Software",
        "required_skills": ["Unity", "C#", "Game Design", "3D"],
        "education_min": "Associate",
        "ai_relevance": 0.35,
        "competition": 0.80,
        "growth_rate": 0.65
    },

    # ================= CLOUD / DEVOPS =================

    "DevOps Engineer": {
        "domain": "Cloud",
        "required_skills": ["Docker", "Kubernetes", "Linux", "CI/CD", "AWS"],
        "education_min": "Bachelor",
        "ai_relevance": 0.50,
        "competition": 0.70,
        "growth_rate": 0.82
    },

    "Cloud Architect": {
        "domain": "Cloud",
        "required_skills": ["AWS", "Azure", "Architecture", "Security"],
        "education_min": "Bachelor",
        "ai_relevance": 0.55,
        "competition": 0.75,
        "growth_rate": 0.85
    },

    "System Administrator": {
        "domain": "IT",
        "required_skills": ["Linux", "Networking", "Monitoring", "Security"],
        "education_min": "Associate",
        "ai_relevance": 0.30,
        "competition": 0.60,
        "growth_rate": 0.60
    },

    # ================= SECURITY =================

    "Cybersecurity Analyst": {
        "domain": "Security",
        "required_skills": ["PenTest", "SIEM", "Network Security", "Linux"],
        "education_min": "Bachelor",
        "ai_relevance": 0.60,
        "competition": 0.78,
        "growth_rate": 0.88
    },

    "Security Engineer": {
        "domain": "Security",
        "required_skills": ["Encryption", "Cloud Security", "SOC", "Python"],
        "education_min": "Bachelor",
        "ai_relevance": 0.65,
        "competition": 0.75,
        "growth_rate": 0.85
    },

    # ================= BUSINESS / PRODUCT =================

    "Product Manager": {
        "domain": "Business",
        "required_skills": ["Roadmap", "PRD", "Agile", "Analytics"],
        "education_min": "Bachelor",
        "ai_relevance": 0.70,
        "competition": 0.85,
        "growth_rate": 0.80
    },

    "Business Analyst": {
        "domain": "Business",
        "required_skills": ["SQL", "Documentation", "Process", "Excel"],
        "education_min": "Bachelor",
        "ai_relevance": 0.55,
        "competition": 0.70,
        "growth_rate": 0.75
    },

    "Project Manager": {
        "domain": "Business",
        "required_skills": ["Planning", "Leadership", "Agile", "JIRA"],
        "education_min": "Bachelor",
        "ai_relevance": 0.40,
        "competition": 0.78,
        "growth_rate": 0.70
    },

    # ================= DESIGN =================

    "UI/UX Designer": {
        "domain": "Design",
        "required_skills": ["Figma", "Wireframe", "Research", "Prototyping"],
        "education_min": "Associate",
        "ai_relevance": 0.45,
        "competition": 0.75,
        "growth_rate": 0.70
    },

    "Graphic Designer": {
        "domain": "Design",
        "required_skills": ["Photoshop", "Illustrator", "Branding"],
        "education_min": "Associate",
        "ai_relevance": 0.30,
        "competition": 0.80,
        "growth_rate": 0.65
    },

    "Motion Designer": {
        "domain": "Design",
        "required_skills": ["After Effects", "Animation", "Video Editing"],
        "education_min": "Associate",
        "ai_relevance": 0.35,
        "competition": 0.78,
        "growth_rate": 0.68
    },

    # ================= MARKETING / MEDIA =================

    "Digital Marketer": {
        "domain": "Marketing",
        "required_skills": ["SEO", "Ads", "Analytics", "Content"],
        "education_min": "Associate",
        "ai_relevance": 0.50,
        "competition": 0.75,
        "growth_rate": 0.78
    },

    "Content Creator": {
        "domain": "Media",
        "required_skills": ["Writing", "Video", "Storytelling"],
        "education_min": "HighSchool",
        "ai_relevance": 0.45,
        "competition": 0.85,
        "growth_rate": 0.80
    },

    "Copywriter": {
        "domain": "Marketing",
        "required_skills": ["Writing", "SEO", "Branding"],
        "education_min": "Associate",
        "ai_relevance": 0.55,
        "competition": 0.78,
        "growth_rate": 0.70
    },

    # ================= ENGINEERING =================

    "Robotics Engineer": {
        "domain": "Engineering",
        "required_skills": ["ROS", "Control", "Embedded", "C++"],
        "education_min": "Bachelor",
        "ai_relevance": 0.80,
        "competition": 0.70,
        "growth_rate": 0.85
    },

    "Embedded Engineer": {
        "domain": "Engineering",
        "required_skills": ["C", "MCU", "RTOS", "Electronics"],
        "education_min": "Bachelor",
        "ai_relevance": 0.60,
        "competition": 0.65,
        "growth_rate": 0.75
    },

    "IoT Engineer": {
        "domain": "Engineering",
        "required_skills": ["Sensors", "MQTT", "Python", "Cloud"],
        "education_min": "Bachelor",
        "ai_relevance": 0.65,
        "competition": 0.70,
        "growth_rate": 0.80
    },

    # ================= FINANCE =================

    "Financial Analyst": {
        "domain": "Finance",
        "required_skills": ["Excel", "Modeling", "Accounting"],
        "education_min": "Bachelor",
        "ai_relevance": 0.55,
        "competition": 0.78,
        "growth_rate": 0.70
    },

    "Quant Analyst": {
        "domain": "Finance",
        "required_skills": ["Math", "Python", "Statistics", "ML"],
        "education_min": "Master",
        "ai_relevance": 0.85,
        "competition": 0.90,
        "growth_rate": 0.75
    },

    # ================= EDUCATION =================

    "AI Lecturer": {
        "domain": "Education",
        "required_skills": ["Teaching", "AI", "Research"],
        "education_min": "Master",
        "ai_relevance": 0.90,
        "competition": 0.65,
        "growth_rate": 0.75
    },

    "STEM Teacher": {
        "domain": "Education",
        "required_skills": ["Teaching", "Math", "Science"],
        "education_min": "Bachelor",
        "ai_relevance": 0.50,
        "competition": 0.60,
        "growth_rate": 0.70
    },

    # ================= SUPPORT =================

    "IT Support": {
        "domain": "IT",
        "required_skills": ["Troubleshooting", "Networking", "Windows"],
        "education_min": "HighSchool",
        "ai_relevance": 0.25,
        "competition": 0.60,
        "growth_rate": 0.55
    },

    "QA Engineer": {
        "domain": "Software",
        "required_skills": ["Testing", "Automation", "Selenium"],
        "education_min": "Associate",
        "ai_relevance": 0.45,
        "competition": 0.70,
        "growth_rate": 0.70
    },

    "Technical Writer": {
        "domain": "Media",
        "required_skills": ["Documentation", "Writing", "Tech"],
        "education_min": "Bachelor",
        "ai_relevance": 0.55,
        "competition": 0.65,
        "growth_rate": 0.68
    },

    # ================= STARTUP / FREELANCE =================

    "Startup Founder": {
        "domain": "Entrepreneurship",
        "required_skills": ["Business", "Pitching", "Tech", "Leadership"],
        "education_min": "Any",
        "ai_relevance": 0.70,
        "competition": 0.90,
        "growth_rate": 0.85
    },

    "Freelance Developer": {
        "domain": "Entrepreneurship",
        "required_skills": ["Programming", "Client Management"],
        "education_min": "Any",
        "ai_relevance": 0.55,
        "competition": 0.80,
        "growth_rate": 0.78
    },

    # ================= DATA ENGINEERING =================

    "Data Engineer": {
        "domain": "Data",
        "required_skills": ["ETL", "Spark", "SQL", "Python", "Big Data"],
        "education_min": "Bachelor",
        "ai_relevance": 0.75,
        "competition": 0.70,
        "growth_rate": 0.88
    },

    "ML Ops Engineer": {
        "domain": "AI",
        "required_skills": ["Deployment", "Docker", "MLflow", "Cloud"],
        "education_min": "Bachelor",
        "ai_relevance": 0.85,
        "competition": 0.75,
        "growth_rate": 0.90
    },

    # ================= ANALYTICS / STRATEGY =================

    "Strategy Analyst": {
        "domain": "Business",
        "required_skills": ["Research", "Analysis", "Presentation"],
        "education_min": "Bachelor",
        "ai_relevance": 0.60,
        "competition": 0.78,
        "growth_rate": 0.72
    },

    "Operations Analyst": {
        "domain": "Business",
        "required_skills": ["Process", "Excel", "Optimization"],
        "education_min": "Bachelor",
        "ai_relevance": 0.55,
        "competition": 0.70,
        "growth_rate": 0.70
    },

}
# =====================================================
# VALIDATION
# =====================================================

def _validate_database() -> None:

    if len(JOB_DATABASE) < 40:
        raise ValueError(
            f"JOB_DATABASE must contain >= 50 jobs, current={len(JOB_DATABASE)}"
        )

    for name, job in JOB_DATABASE.items():

        required_keys = JobSchema.__annotations__.keys()

        for key in required_keys:
            if key not in job:
                raise ValueError(f"Missing key '{key}' in job '{name}'")

        if not (0.0 <= job["ai_relevance"] <= 1.0):
            raise ValueError(f"Invalid ai_relevance in {name}")

        if not (0.0 <= job["competition"] <= 1.0):
            raise ValueError(f"Invalid competition in {name}")

        if not (0.0 <= job["growth_rate"] <= 1.0):
            raise ValueError(f"Invalid growth_rate in {name}")


_validate_database()


# =====================================================
# QUERY FUNCTIONS
# =====================================================

def get_job(job_name: str) -> JobSchema | None:
    return JOB_DATABASE.get(job_name)


def get_all_jobs() -> List[str]:
    return sorted(JOB_DATABASE.keys())


def get_jobs_by_domain(domain: str) -> List[str]:

    return [
        name for name, data in JOB_DATABASE.items()
        if data["domain"] == domain
    ]


def get_required_skills(job_name: str) -> List[str]:

    job = JOB_DATABASE.get(job_name)

    if not job:
        return []

    return job["required_skills"]


def get_relevant_interests(job_name: str) -> List[str]:

    job = JOB_DATABASE.get(job_name)

    if not job:
        return []

    domain = job["domain"]

    return DOMAIN_INTEREST_MAP.get(domain, [])

