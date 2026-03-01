# DongSon Nexus
### Hybrid Deterministic Career Decision Support System

DongSon Nexus is a career guidance decision support system built on a **Hybrid Semi-API Architecture**, combining a deterministic Scoring Engine with an AI Explanation Layer — transforming career orientation from intuition-based to data-driven decision-making.

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Solution Overview](#solution-overview)
3. [Dependency Installation](#-dependency-installation)
4. [How to Use](#-how-to-use)
5. [Documentation](#-documentation)
6. [System Architecture](#system-architecture)
7. [Core Pipeline](#core-pipeline)
8. [SIMGR Deterministic Scoring Engine](#simgr-deterministic-scoring-engine)
9. [Explanation Layer (6-Stage XAI)](#explanation-layer-6-stage-xai)
10. [Logging, Audit & Integrity](#logging-audit--integrity)
11. [Evaluation & Drift Detection](#evaluation--drift-detection)
12. [Admin & Operations Panels](#admin--operations-panels)
13. [Technology Stack](#technology-stack)
14. [Security & Governance](#security--governance)
15. [Usage Guide](#usage-guide)
16. [Impact & Value](#impact--value)
17. [Comparison with Traditional Systems](#comparison-with-traditional-systems)
18. [Deployment Note](#deployment-note)
19. [Resources](#resources)

---

## Problem Statement

Vietnam is in a **"golden demographic structure"** phase. However:

- The rate of graduates working outside their field of study hovers at and exceeds **60%** across many sectors.
- Training supply and labor market demand remain structurally misaligned.
- Traditional career guidance tools (Holland, MBTI) are static and do not integrate real market data.

The core problem is not a lack of information — it is the absence of a **structured, reproducible information-processing mechanism**.

---

## Solution Overview

DongSon Nexus is designed as a **Hybrid Deterministic Decision Architecture**:

- **Local Decision Engine** → Makes the decision
- **API + LLM Layer** → Understands & interprets
- **Market Data Integration** → Supply–demand context
- **Audit Layer** → Reproducibility & verification

Goals:
- Personalization based on dynamic competency profiles
- Multi-variable quantitative scoring
- AI separated from decision authority
- Full auditability

---

## 📦 Dependency Installation

The system is modular. Install according to your use case.

---

### 1️⃣ Full System (Recommended)

Install all frozen dependencies:

```bash
pip install -r requirements.lock
```

> ⚠️ This file is a production snapshot. **Do not edit manually.**

---

### 2️⃣ API Backend Only

```bash
pip install -r backend/requirements_api.txt
```

Includes:
- FastAPI
- Authentication (JWT, bcrypt)
- Database ORM
- Validation
- API server runtime

---

### 3️⃣ Data Pipeline

```bash
pip install -r requirements_data_pipeline.txt
```

Includes:
- Web scraping
- ETL
- Market data processing
- NLP & ML utilities
- Monitoring

---

### 4️⃣ Crawlers Only

```bash
pip install -r requirements_crawler.txt
```

Or:

```bash
pip install -r backend/crawlers/requirements_crawler.txt
```

Includes:
- Selenium
- Playwright
- BeautifulSoup
- lxml

---

## 🚀 How to Use

### 1️⃣ Clone Repository

```bash
git clone https://github.com/dctbao09x/hybrid-decision-support-system.git
cd hybrid-decision-support-system
```

---

### 2️⃣ Create Virtual Environment

```bash
python -m venv venv
```

**Windows**

```bash
venv\Scripts\activate
```

**macOS / Linux**

```bash
source venv/bin/activate
```

---

### 3️⃣ Install Dependencies

Full system:

```bash
pip install -r requirements.lock
```

Backend only:

```bash
pip install -r backend/requirements_api.txt
```

---

### 4️⃣ Run API Server

```bash
uvicorn backend.main:app --reload
```

| Endpoint | URL |
|----------|-----|
| Default server | `http://127.0.0.1:8000` |
| Swagger UI | `http://127.0.0.1:8000/docs` |

---

### 5️⃣ Run Data Pipeline *(If Applicable)*

Run ETL module:

```bash
python data_pipeline/run_pipeline.py
```

Or crawler:

```bash
python backend/crawlers/run_crawler.py
```

---

### 6️⃣ Run Tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=.
```

---

## 📚 Documentation

This README describes the system architecture and how to run the system.

Detailed documentation includes:
- System Architecture
- Scoring Engine (SIMGR)
- XAI Explanation Layer
- Market Data Pipeline
- Governance & Audit Design

If the project has a `docs/` directory, you can build documentation using **Sphinx**:

```bash
cd docs
make html
```

Or if Sphinx is already installed:

```bash
sphinx-build -b html docs/ docs/_build
```

Output will be generated at:

```
docs/_build/index.html
```

---

## System Architecture

### Architectural Principles

1. **Decision Isolation** — AI cannot override the scoring engine
2. **Deterministic-First** — Same input always produces same output
3. **Pure-Function Scoring** — No side effects in core scoring logic
4. **Separation of Concerns** — Each layer has a single responsibility
5. **Auditability by Design** — Every decision is traceable and reproducible

### Hybrid Model

```
User → API Layer → Normalization → LLM Feature Extraction
     → Knowledge Base Mapping → SIMGR Core → Ranking
     → XAI Explanation → API Response
```

---

## Core Pipeline

### Step 1 — Structured Input Layer

- Schema validation
- Type casting
- Missing value handling
- Canonical formatting

**Output:** `normalized_profile`

> Quality requirement: Mapping accuracy ≥ 98%

---

### Step 2 — LLM Feature & Semantic Normalization

Implemented via **Ollama**.

Constraints:
- Does **not** generate scores
- Does **not** modify weights
- Does **not** perform ranking

**Output:** `enriched_feature_vector`

---

### Step 3 — Knowledge Base Mapping

Internal ontology:
- Career
- Skill
- Market
- Risk

**Output:** `kb_aligned_feature_set`

---

## SIMGR Deterministic Scoring Engine

### Formula

```
Score = wS·S + wI·I + wM·M + wG·G − wR·R
Clamped to [0, 1]
```

### Components

#### 1. Study Component (S)
- 40% Academic performance
- 30% Standardized test scores
- 30% Skill assessments

#### 2. Interest Component (I)
Matches user interests against a career taxonomy.

#### 3. Market Component (M)
```
M = f(N, G, L)
```
- **N**: Number of job postings
- **G**: Industry growth rate
- **L**: Median salary

#### 4. Growth Component (G)
Long-term industry trend analysis.

#### 5. Risk Component (R)
Penalty factors:
- Automation risk
- Market saturation
- Training cost
- Unemployment rate

### Engine Structure

| Component | Role |
|-----------|------|
| `ScoringConfig` | Versioned weight configuration |
| `SIMGRCalculator` | Orchestrator |
| `RankingEngine` | Sorts and ranks careers |
| `ExplainRouter` | Routes output to XAI layer |

---

## Explanation Layer (6-Stage XAI)

Implemented using:
- **SHAP**
- **Python**
- **Ollama**
- **FastAPI**

### Pipeline

| Stage | Component |
|-------|-----------|
| 1 | XAI Core |
| 2 | Rule / Template Binding |
| 3 | Ollama Formatter |
| 4 | Explanation API |
| 5 | Frontend Rendering |
| 6 | User Feedback Capture |

Constraints:
- Does **not** alter scores
- Fully isolated from the Decision Core

**Output:** `explanation_payload`

---

## Logging, Audit & Integrity

### Append-Only Logging

Each log entry records:
- Input snapshot
- Feature vector
- Score breakdown
- Applied rules
- `decision_trace_id`

### Hash-Chain Linking

- SHA-256 chaining between entries
- Tamper detection
- Deterministic reconstruction

---

## Evaluation & Drift Detection

### Model Metrics

| Metric | Value |
|--------|-------|
| Accuracy | 0.9535 |
| F1 Score | 0.9395 |
| Precision | 0.9458 |
| Recall | 0.9501 |
| Validation | 5-Fold Cross Validation |

### Drift Monitoring

Metrics used:
- KL Divergence
- Jensen-Shannon Divergence
- Population Stability Index (PSI)

**Drift condition:** `Divergence > adaptive threshold`

---

## Admin & Operations Panels

### Central Command
- SLA monitoring
- Error rate tracking
- Model drift alerts
- LLM health checks
- Cost control

### Knowledge Base Admin
- Ontology versioning
- Bulk import / export
- Rollback support

### MLOps Panel
- Model training
- Evaluation
- Version management
- Controlled retraining

### Governance Panel
- Approval workflow
- SLA compliance tracking
- Risk tracking

---

## Technology Stack

### Backend
- Python 3.13
- FastAPI
- Uvicorn
- Gunicorn

### AI & ML
- scikit-learn
- PyTorch
- SHAP
- sentence-transformers
- FAISS
- Ollama

### Data
- PostgreSQL
- Apache Airflow

### Infrastructure
- Kubernetes
- Nginx
- Prometheus
- Grafana

### Security
- `cryptography` (Fernet / AES)
- Environment-based secret handling

---

## Security & Governance

- All user data is anonymized before processing
- Sensitive attributes are excluded from decision variables
- Consent-based data usage model
- Continuous drift and bias monitoring

---

## Usage Guide

### User Flow

1. Click **"Get Started"**
2. Enter skills and proficiency levels
3. Provide educational background
4. Set career goals
5. Confirm work experience
6. Receive ranked results

**Estimated time:** 3–5 minutes

---

## Impact & Value

- Reduces trial-and-error in career selection
- Transparent, explainable decision-making
- Long-term progress tracking
- Supports schools and organizations in guidance programs

---

## Comparison with Traditional Systems

| Criterion | Holland | MBTI | DongSon Nexus |
|-----------|---------|------|---------------|
| Basis | Personality | Personality | Actual competency |
| Data source | Psychometric test | Self-assessment | Structured profile |
| Quantitative scoring | Low | Low | SIMGR Score |
| Market integration | No | No | Yes |
| Reproducibility | Limited | Limited | Deterministic |
| Explanation | Qualitative | Qualitative | XAI score decomposition |

---

## Deployment Note

The system runs **locally** due to the following runtime requirements:

- FastAPI backend
- Python runtime
- Ollama (local LLM inference)
- ML pipeline
- API server

> GitHub Pages supports static hosting only and does not support backend runtimes.

---

## Resources

| Resource | Link |
|----------|------|
| 📁 Repository | [Google Drive](https://drive.google.com/file/d/1nQeEfx_YKKUmR8ni6RnXYMGakepwv1Si/view?usp=sharing) |
| 🎬 Demo | [Google Drive](https://drive.google.com/file/d/1IXrOPDASQjcDbNf-IUIehBRGK0HMU2c5/view) |
| 📄 Product Explanation | [Google Drive](https://drive.google.com/file/d/1luWNBk-OznCKBQ4Sl1YRDc77ygSJkPA7/view) |
