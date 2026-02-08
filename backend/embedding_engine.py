# backend/embedding_engine.py
"""
Embedding & Similarity Layer for Career Guidance System
Uses sentence-transformers for semantic matching between user profiles and careers
"""

import re
import numpy as np
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
import faiss


# ==================== CAREER CORPUS ====================
CAREER_CORPUS = {
    "AI Engineer": """
        Artificial Intelligence Engineer Machine Learning Deep Learning 
        Neural Networks TensorFlow PyTorch Python Data Science 
        Computer Vision NLP Algorithm Research Development
        Trí tuệ nhân tạo Kỹ sư AI Học máy Mạng nơ-ron
    """,
    
    "Data Scientist": """
        Data Science Analytics Statistics Machine Learning Python R
        SQL Database Big Data Visualization Pandas NumPy
        Business Intelligence Predictive Modeling Data Mining
        Khoa học dữ liệu Phân tích dữ liệu Thống kê
    """,
    
    "Software Developer": """
        Software Development Programming Coding Backend Frontend
        Java Python JavaScript C++ Web Development Mobile App
        API Database Git Agile DevOps Cloud
        Phát triển phần mềm Lập trình viên Developer
    """,
    
    "Data Analyst": """
        Data Analysis Business Analytics SQL Excel Tableau
        Dashboard Reporting Visualization Metrics KPI
        Business Intelligence Statistics Python R
        Phân tích dữ liệu Báo cáo Trực quan hóa
    """,
    
    "Machine Learning Engineer": """
        Machine Learning MLOps Model Deployment Production
        Python TensorFlow PyTorch Scikit-learn Feature Engineering
        Model Optimization Cloud AWS Azure Algorithm
        Kỹ sư máy học Triển khai mô hình
    """,
    
    "UX/UI Designer": """
        User Experience User Interface Design Figma Adobe XD
        Prototyping Wireframe Visual Design Interaction Design
        Usability Research User Research Design Thinking
        Thiết kế giao diện Trải nghiệm người dùng
    """,
    
    "Product Manager": """
        Product Management Roadmap Strategy Agile Scrum
        User Stories Requirements PRD Stakeholder Management
        Market Research Analytics Product Launch Business
        Quản lý sản phẩm Chiến lược Phát triển sản phẩm
    """,
    
    "Marketing Manager": """
        Marketing Digital Marketing SEO SEM Social Media
        Content Marketing Brand Management Campaign Strategy
        Analytics Google Analytics Marketing Automation CRM
        Quản lý marketing Tiếp thị Truyền thông
    """,
    
    "Business Analyst": """
        Business Analysis Requirements Gathering Process Improvement
        SQL Data Analysis Documentation Stakeholder Management
        Agile JIRA Workflow Project Management
        Phân tích kinh doanh Phân tích quy trình
    """,
    
    "DevOps Engineer": """
        DevOps CI/CD Jenkins Docker Kubernetes Infrastructure
        Cloud AWS Azure GCP Automation Scripting Linux
        Monitoring Terraform Ansible System Administration
        Kỹ sư DevOps Tự động hóa Triển khai
    """,
    
    "Frontend Developer": """
        Frontend Development React Vue Angular JavaScript TypeScript
        HTML CSS Responsive Design Web Development UI
        Redux State Management REST API GraphQL
        Phát triển giao diện Lập trình web
    """,
    
    "Backend Developer": """
        Backend Development API REST GraphQL Database SQL NoSQL
        Node.js Python Java Spring Boot Django Flask
        Microservices Cloud Server Architecture
        Phát triển backend Lập trình server
    """,
    
    "Cybersecurity Analyst": """
        Cybersecurity Information Security Network Security Penetration Testing
        Ethical Hacking Security Audit Risk Assessment SIEM
        Firewall Encryption Incident Response Compliance
        An ninh mạng Bảo mật Phân tích bảo mật
    """,
    
    "Cloud Architect": """
        Cloud Architecture AWS Azure GCP Infrastructure as Code
        Serverless Microservices Container Orchestration Scalability
        High Availability Disaster Recovery Security Compliance
        Kiến trúc đám mây Cloud Solution
    """,
    
    "QA Engineer": """
        Quality Assurance Testing Automation Selenium Test Cases
        Manual Testing Bug Tracking JIRA Regression Testing
        Performance Testing API Testing CI/CD Quality Control
        Kiểm thử phần mềm Đảm bảo chất lượng
    """,
    
    "Content Writer": """
        Content Writing Copywriting SEO Content Marketing
        Blog Articles Technical Writing Creative Writing
        Storytelling Editing Research Content Strategy
        Viết nội dung Biên tập Sáng tạo nội dung
    """,
    
    "Graphic Designer": """
        Graphic Design Adobe Photoshop Illustrator InDesign
        Visual Design Branding Logo Design Typography
        Print Design Digital Design Creative Design Layout
        Thiết kế đồ họa Thiết kế hình ảnh
    """,
    
    "HR Manager": """
        Human Resources Recruitment Talent Acquisition Employee Relations
        Performance Management Compensation Benefits Training Development
        HR Policies Labor Law Organizational Development
        Quản lý nhân sự Tuyển dụng Đào tạo
    """,
    
    "Financial Analyst": """
        Financial Analysis Investment Analysis Financial Modeling
        Excel Forecasting Budgeting Financial Reporting
        Valuation Risk Management Corporate Finance Accounting
        Phân tích tài chính Đầu tư Mô hình tài chính
    """,
    
    "Sales Manager": """
        Sales Management B2B B2C CRM Pipeline Management
        Lead Generation Sales Strategy Negotiation Revenue Growth
        Customer Relationship Account Management Team Leadership
        Quản lý bán hàng Phát triển doanh số
    """
}


VI_MAP = {
    "à": "a", "á": "a", "ả": "a", "ã": "a", "ạ": "a",
    "ă": "a", "ằ": "a", "ắ": "a", "ẳ": "a", "ẵ": "a", "ặ": "a",
    "â": "a", "ầ": "a", "ấ": "a", "ẩ": "a", "ẫ": "a", "ậ": "a",
    "è": "e", "é": "e", "ẻ": "e", "ẽ": "e", "ẹ": "e",
    "ê": "e", "ề": "e", "ế": "e", "ể": "e", "ễ": "e", "ệ": "e",
    "ì": "i", "í": "i", "ỉ": "i", "ĩ": "i", "ị": "i",
    "ò": "o", "ó": "o", "ỏ": "o", "õ": "o", "ọ": "o",
    "ô": "o", "ồ": "o", "ố": "o", "ổ": "o", "ỗ": "o", "ộ": "o",
    "ơ": "o", "ờ": "o", "ớ": "o", "ở": "o", "ỡ": "o", "ợ": "o",
    "ù": "u", "ú": "u", "ủ": "u", "ũ": "u", "ụ": "u",
    "ư": "u", "ừ": "u", "ứ": "u", "ử": "u", "ữ": "u", "ự": "u",
    "ỳ": "y", "ý": "y", "ỷ": "y", "ỹ": "y", "ỵ": "y",
    "đ": "d"
}

def normalize_text(text: str) -> str:
    """Lowercase, remove accents, special chars"""

    if not text:
        return ""

    text = text.lower().strip()

    normalized = ""
    for c in text:
        normalized += VI_MAP.get(c, c)

    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


# ======================================================
# EMBEDDING ENGINE
# ======================================================

class EmbeddingEngine:
    """
    Singleton embedding engine
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):

        if hasattr(self, "_initialized"):
            return

        print("[Embedding] Loading model...")

        self.model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

        self.dimension = self.model.get_sentence_embedding_dimension()

        self.career_names = list(CAREER_CORPUS.keys())
        self.career_texts = [
            normalize_text(v) for v in CAREER_CORPUS.values()
        ]

        self.index = None
        self.embeddings = None

        self._build_index()

        self._initialized = True

        print("[Embedding] Ready.")


    # --------------------------------------------------

    def _embed(self, text: str) -> np.ndarray:

        text = normalize_text(text)

        if not text:
            return np.zeros(self.dimension, dtype=np.float32)

        vec = self.model.encode(text)

        vec = vec.astype(np.float32)

        faiss.normalize_L2(vec.reshape(1, -1))

        return vec


    # --------------------------------------------------

    def _build_index(self):

        print("[Embedding] Building FAISS index...")

        vectors = []

        for txt in self.career_texts:
            vectors.append(self._embed(txt))

        self.embeddings = np.vstack(vectors)

        self.index = faiss.IndexFlatIP(self.dimension)

        self.index.add(self.embeddings)

        print(f"[Embedding] Indexed {len(vectors)} careers.")


    # --------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict]:

        if not query:
            return []

        q_vec = self._embed(query).reshape(1, -1)

        scores, ids = self.index.search(
            q_vec,
            min(top_k, len(self.career_names))
        )

        results = []

        for i, s in zip(ids[0], scores[0]):

            results.append({
                "career": self.career_names[i],
                "similarity": round(float(s), 4)
            })

        return results


    # --------------------------------------------------

    def match_profile(
        self,
        processed_profile: Dict,
        top_k: int = 5
    ) -> List[Dict]:

        parts = []

        parts.append(processed_profile.get("goal_cleaned", ""))
        parts.append(processed_profile.get("chat_summary", ""))

        parts.extend(processed_profile.get("skill_tags", []))
        parts.extend(processed_profile.get("interest_tags", []))

        combined = " ".join(parts)

        return self.search(combined, top_k)


# ======================================================
# PUBLIC API
# ======================================================

_engine = None


def get_engine() -> EmbeddingEngine:
    global _engine

    if _engine is None:
        _engine = EmbeddingEngine()

    return _engine


def match_careers(
    processed_profile: Dict,
    top_k: int = 5
) -> List[Dict]:

    engine = get_engine()

    return engine.match_profile(processed_profile, top_k)


# ======================================================
# TEST
# ======================================================

if __name__ == "__main__":

    print("\n" + "=" * 70)
    print("EMBEDDING ENGINE TEST")
    print("=" * 70)

    engine = get_engine()

    samples = [

        {
            "goal_cleaned": "muon lam ky su ai",
            "chat_summary": "thich hoc may va du lieu",
            "skill_tags": ["Python", "Machine Learning"],
            "interest_tags": ["IT"]
        },

        {
            "goal_cleaned": "thiet ke giao dien web",
            "chat_summary": "thich sang tao",
            "skill_tags": ["UI Design", "Figma"],
            "interest_tags": ["Design"]
        },

        {
            "goal_cleaned": "lam marketing online",
            "chat_summary": "seo va quang cao",
            "skill_tags": ["SEO", "Content"],
            "interest_tags": ["Business"]
        },

    ]


    for i, p in enumerate(samples, 1):

        print(f"\n--- TEST {i} ---")

        results = engine.match_profile(p)

        for r in results:
            print(r)

    print("\nDONE.")
