# DongSon Nexus
### Hybrid Deterministic Career Decision Support System

DongSon Nexus là hệ thống hỗ trợ ra quyết định định hướng nghề nghiệp dựa trên kiến trúc **Hybrid Semi-API**, kết hợp Scoring Engine xác định (deterministic) và AI Explanation Layer, nhằm chuyển bài toán hướng nghiệp từ cảm tính sang định lượng.

---

# Table of Contents

1. [Problem Statement](#problem-statement)
2. [Solution Overview](#solution-overview)
3. [System Architecture](#system-architecture)
4. [Core Pipeline](#core-pipeline)
5. [SIMGR Deterministic Scoring Engine](#simgr-deterministic-scoring-engine)
6. [Explanation Layer (6-Stage XAI)](#explanation-layer-6-stage-xai)
7. [Logging, Audit & Integrity](#logging-audit--integrity)
8. [Evaluation & Drift Detection](#evaluation--drift-detection)
9. [Admin & Operations Panels](#admin--operations-panels)
10. [Technology Stack](#technology-stack)
11. [Security & Governance](#security--governance)
12. [Usage Guide](#usage-guide)
13. [Impact & Value](#impact--value)
14. [Comparison with Traditional Systems](#comparison-with-traditional-systems)
15. [Deployment Note](#deployment-note)
16. [Resources](#resources)

---

# Problem Statement

Việt Nam đang trong giai đoạn “cơ cấu dân số vàng”. Tuy nhiên:

- Tỷ lệ làm việc trái ngành ở nhiều nhóm ngành dao động quanh và vượt 60%.
- Cơ cấu đào tạo và nhu cầu tuyển dụng không đồng bộ.
- Công cụ hướng nghiệp truyền thống (Holland, MBTI) mang tính tĩnh, không tích hợp dữ liệu thị trường.

Vấn đề cốt lõi không nằm ở thiếu thông tin, mà ở thiếu một **cơ chế xử lý thông tin có cấu trúc và tái lập được**.

---

# Solution Overview

DongSon Nexus được thiết kế như một **Hybrid Deterministic Decision Architecture**:

- Local Decision Engine → Quyết định
- API + LLM Layer → Hiểu & Diễn giải
- Market Data Integration → Bối cảnh cung – cầu
- Audit Layer → Tái lập & kiểm chứng

Mục tiêu:
- Cá nhân hóa dựa trên hồ sơ năng lực động
- Chấm điểm định lượng đa biến
- Tách biệt AI khỏi quyền quyết định
- Có khả năng kiểm toán

---

# System Architecture

## Architectural Principles

1. Decision Isolation  
2. Deterministic-First  
3. Pure-Function Scoring  
4. Separation of Concerns  
5. Auditability by Design  

## Hybrid Model
User → API Layer → Normalization → LLM Feature Extraction
→ Knowledge Base Mapping → SIMGR Core → Ranking
→ XAI Explanation → API Response


---

# Core Pipeline

## Step 1 — Structured Input Layer

- Schema validation
- Type casting
- Missing handling
- Canonical formatting

Output:

normalized_profile


Quality requirement:
Mapping accuracy ≥ 98%

---

## Step 2 — LLM Feature & Semantic Normalization

Implemented via Ollama.

Constraints:
- Không sinh score
- Không thay đổi weight
- Không thực hiện ranking

Output:

enriched_feature_vector


---

## Step 3 — Knowledge Base Mapping

Ontology nội bộ:
- Career
- Skill
- Market
- Risk

Output:

kb_aligned_feature_set


---

# SIMGR Deterministic Scoring Engine

## Formula


Score = wS·S + wI·I + wM·M + wG·G − wR·R
Clamp to [0,1]


## Components

### 1. Study Component (S)
- 40% Điểm học tập
- 30% Bài test
- 30% Đánh giá kỹ năng

### 2. Interest Component (I)
Match sở thích với taxonomy ngành.

### 3. Market Component (M)
M = f(N, G, L)
- N: số tin tuyển dụng
- G: tăng trưởng
- L: lương trung vị

### 4. Growth Component (G)
Xu hướng ngành dài hạn.

### 5. Risk Component (R)
Penalty:
- Automation risk
- Saturation
- Chi phí đào tạo
- Thất nghiệp

## Engine Structure

- ScoringConfig (versioned)
- SIMGRCalculator (orchestrator)
- RankingEngine
- ExplainRouter

---

# Explanation Layer (6-Stage XAI)

Triển khai bằng:
- SHAP
- Python
- Ollama
- FastAPI

Pipeline:

1. XAI Core
2. Rule / Template Binding
3. Ollama Formatter
4. Explanation API
5. Frontend Rendering
6. User Feedback Capture

Ràng buộc:
- Không thay đổi score
- Tách biệt khỏi Decision Core

Output:

explanation_payload


---

# Logging, Audit & Integrity

## Append-Only Logging

Lưu:
- Input snapshot
- Feature vector
- Score breakdown
- Applied rules
- decision_trace_id

## Hash-Chain Linking

- SHA-256 linking
- Tamper detection
- Deterministic reconstruction

---

# Evaluation & Drift Detection

## Metrics

- Accuracy: 0.953488
- F1 Score: 0.939514
- Precision: 0.945771
- Recall: 0.950124
- 5-Fold Cross Validation

## Drift Monitoring

- KL Divergence
- Jensen-Shannon Divergence
- PSI

Drift condition:
Divergence > adaptive threshold

---

# Admin & Operations Panels

## Central Command
- SLA monitoring
- Error rate
- Model drift
- LLM health
- Cost control

## Knowledge Base Admin
- Ontology versioning
- Bulk import/export
- Rollback support

## MLOps Panel
- Training
- Evaluation
- Versioning
- Controlled retraining

## Governance Panel
- Approval workflow
- SLA compliance
- Risk tracking

---

# Technology Stack

## Backend
- Python 3.13
- FastAPI
- Uvicorn
- Gunicorn

## AI & ML
- scikit-learn
- PyTorch
- SHAP
- sentence-transformers
- FAISS
- Ollama

## Data
- PostgreSQL
- Apache Airflow

## Infrastructure
- Kubernetes
- Nginx
- Prometheus
- Grafana

## Security
- cryptography (Fernet/AES)
- Environment-based secret handling

---

# Security & Governance

- Dữ liệu được ẩn danh hóa
- Không sử dụng thuộc tính nhạy cảm làm biến quyết định
- Consent-based data usage
- Drift & bias monitoring

---

# Usage Guide

## User Flow

1. Nhấn "Bắt đầu"
2. Nhập kỹ năng & mức độ
3. Cung cấp học vấn
4. Thiết lập mục tiêu
5. Xác nhận kinh nghiệm
6. Nhận kết quả

Thời gian: 3–5 phút

---

# Impact & Value

- Giảm thử-sai trong chọn ngành
- Minh bạch hóa quyết định
- Theo dõi tiến trình dài hạn
- Hỗ trợ nhà trường & tổ chức

---

# Comparison with Traditional Systems

| Tiêu chí | Holland | MBTI | DongSon Nexus |
|----------|---------|------|---------------|
| Cơ sở | Tính cách | Tính cách | Năng lực thực tế |
| Dữ liệu | Trắc nghiệm | Tự đánh giá | Hồ sơ cấu trúc |
| Định lượng | Thấp | Thấp | SIMGR Score |
| Tích hợp thị trường | Không | Không | Có |
| Tái lập | Hạn chế | Hạn chế | Deterministic |
| Giải thích | Định tính | Định tính | XAI phân rã điểm |

---

# Deployment Note

Hệ thống chạy local do yêu cầu:

- FastAPI backend
- Python runtime
- Ollama
- ML pipeline
- API server

GitHub Pages chỉ hỗ trợ static hosting, không hỗ trợ backend runtime.

---

# Resources

Repository:
https://github.com/dctbao09x/Hybrid-Decision-Support-System

Demo:
https://drive.google.com/file/d/1IXrOPDASQjcDbNf-IUIehBRGK0HMU2c5/view

Product Explanation:
https://drive.google.com/file/d/1luWNBk-OznCKBQ4Sl1YRDc77ygSJkPA7/view
