# DongSon Nexus
### Hybrid Deterministic Career Decision Support System

DongSon Nexus is a career guidance decision support system built on a **Hybrid Semi-API Architecture**, combining a deterministic Scoring Engine with an AI Explanation Layer — transforming career orientation from intuition-based to data-driven decision-making.

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Solution Overview](#solution-overview)
3. [Dependency Installation](#-dependency-installation)
4. [How to Use](#-how-to-use)
5. [System Architecture](#system-architecture)
6. [Core Pipeline](#core-pipeline)
7. [SIMGR Deterministic Scoring Engine](#step-4--simgr-deterministic-scoring-engine)
8. [Explanation Layer (6-Stage XAI)](#step-5--explanation-layer-6-stage-xai)
9. [Logging, Audit & Integrity](#step-6--logging-audit--integrity)
10. [Evaluation & Drift Detection](#evaluation--drift-detection)
11. [Technology Stack](#technology-stack)
12. [Security & Governance](#security--governance)
13. [Impact & Value](#impact--value)
14. [Comparison with Traditional Systems](#comparison-with-traditional-systems)
15. [Resources](#resources)

---

## Problem Statement

Vietnam is in a **"golden demographic structure"** phase. However:

- Over **60%** of graduates work outside their field of study across many sectors.
- Training supply and labor market demand remain structurally misaligned.
- Traditional career guidance tools (Holland, MBTI) are static and do not integrate real market data.

The core problem is not a lack of information — it is the absence of a **structured, reproducible information-processing mechanism**.

---

## Solution Overview

DongSon Nexus is designed as a **Hybrid Deterministic Decision Architecture**:

| Layer | Role |
|-------|------|
| **Local Decision Engine** | Makes the decision |
| **API + LLM Layer** | Understands & interprets |
| **Market Data Integration** | Supply–demand context |
| **Audit Layer** | Reproducibility & verification |

**Goals:**
- Personalization based on dynamic competency profiles
- Multi-variable quantitative scoring
- AI separated from decision authority
- Full auditability

---

## 📦 Dependency Installation

### Full System *(Recommended)*

```bash
pip install -r requirements.lock
```

> ⚠️ This file is a production snapshot. Do not edit manually.

### Backend Only

```bash
pip install -r backend/requirements_api.txt
```

### Data Pipeline

```bash
pip install -r requirements_data_pipeline.txt
```

### Crawlers Only

```bash
pip install -r requirements_crawler.txt
```

---

## 🚀 How to Use

### 1. Clone Repository

```bash
git clone https://github.com/dctbao09x/hybrid-decision-support-system.git
cd hybrid-decision-support-system
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

**Windows:** `venv\Scripts\activate`  
**macOS / Linux:** `source venv/bin/activate`

### 3. Install Dependencies

```bash
pip install -r requirements.lock
```

### 4. Run API Server

```bash
uvicorn backend.main:app --reload
```

| Endpoint | URL |
|----------|-----|
| Default server | `http://127.0.0.1:8000` |
| Swagger UI | `http://127.0.0.1:8000/docs` |

### 5. Run Tests

```bash
pytest --cov=.
```

---

## System Architecture

### Architectural Principles

| Principle | Description |
|-----------|-------------|
| **Decision Isolation** | AI cannot override the scoring engine |
| **Deterministic-First** | Same input always produces same output |
| **Pure-Function Scoring** | No side effects in core scoring logic |
| **Separation of Concerns** | Each layer has a single responsibility |
| **Auditability by Design** | Every decision is traceable and reproducible |

### Pipeline Overview

```
User → API Layer → Normalization → LLM Feature Extraction
     → Knowledge Base Mapping → SIMGR Core → Ranking
     → XAI Explanation → API Response
```

![System Architecture](https://raw.githubusercontent.com/dctbao09x/hybrid-decision-support-system/685dfa40ffad23d3205b194622354881d54c8ec3/System%20Architecture.png)

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

## Step 4 — SIMGR Deterministic Scoring Engine

![SIMGR Structure](https://raw.githubusercontent.com/dctbao09x/hybrid-decision-support-system/685dfa40ffad23d3205b194622354881d54c8ec3/SIMGR%20Structure.png)

### Formula

```
Score = wS·S + wI·I + wM·M + wG·G − wR·R
Clamped to [0, 1]
```

### Components

| Component | Weight Breakdown |
|-----------|-----------------|
| **S — Study** | 40% Academic · 30% Standardized Tests · 30% Skill Assessments |
| **I — Interest** | User interests matched against career taxonomy |
| **M — Market** | `f(N, G, L)` → Job postings · Growth rate · Median salary |
| **G — Growth** | Long-term industry trend analysis |
| **R — Risk** | Automation risk · Market saturation · Training cost · Unemployment |

### Engine Structure

| Component | Role |
|-----------|------|
| `ScoringConfig` | Versioned weight configuration |
| `SIMGRCalculator` | Orchestrator |
| `RankingEngine` | Sorts and ranks careers |
| `ExplainRouter` | Routes output to XAI layer |

---

## Step 5 — Explanation Layer (6-Stage XAI)

Implemented using **SHAP**, **Python**, **Ollama**, and **FastAPI**.

| Stage | Component |
|-------|-----------|
| 1 | XAI Core |
| 2 | Rule / Template Binding |
| 3 | Ollama Formatter |
| 4 | Explanation API |
| 5 | Frontend Rendering |
| 6 | User Feedback Capture |

> ⚠️ Does **not** alter scores. Fully isolated from the Decision Core.

**Output:** `explanation_payload`

---

## Step 6 — Logging, Audit & Integrity

**Append-Only Logging** — Each entry records: input snapshot, feature vector, score breakdown, applied rules, and `decision_trace_id`.

**Hash-Chain Linking** — SHA-256 chaining between entries for tamper detection and deterministic reconstruction.

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

Metrics: **KL Divergence**, **Jensen-Shannon Divergence**, **Population Stability Index (PSI)**  
Drift condition: `Divergence > adaptive threshold`

---

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.13 · FastAPI · Uvicorn · Gunicorn |
| **AI & ML** | scikit-learn · PyTorch · SHAP · sentence-transformers · FAISS · Ollama |
| **Data** | PostgreSQL · Apache Airflow |
| **Infrastructure** | Kubernetes · Nginx · Prometheus · Grafana |
| **Security** | `cryptography` (Fernet / AES) · Environment-based secret handling |

---

## Security & Governance

- All user data is anonymized before processing
- Sensitive attributes are excluded from decision variables
- Consent-based data usage model
- Continuous drift and bias monitoring

---

## Impact & Value

- Reduces trial-and-error in career selection
- Transparent, explainable decision-making
- Long-term progress tracking
- Supports schools and organizations in guidance programs

---

## Comparison with Traditional Systems

| Criterion | Holland | MBTI | DongSon Nexus |
|-----------|:-------:|:----:|:-------------:|
| Basis | Personality | Personality | Actual competency |
| Data source | Psychometric test | Self-assessment | Structured profile |
| Quantitative scoring | Low | Low | SIMGR Score |
| Market integration | ✗ | ✗ | ✓ |
| Reproducibility | Limited | Limited | Deterministic |
| Explanation | Qualitative | Qualitative | XAI score decomposition |

---

## Resources

| Resource | Link |
|----------|------|
| 📁 Repository | [Google Drive](https://drive.google.com/file/d/1nQeEfx_YKKUmR8ni6RnXYMGakepwv1Si/view?usp=sharing) |
| 🎬 Demo | [Google Drive](https://drive.google.com/file/d/1IXrOPDASQjcDbNf-IUIehBRGK0HMU2c5/view) |
| 📄 Product Explanation | [Google Drive](https://drive.google.com/file/d/1luWNBk-OznCKBQ4Sl1YRDc77ygSJkPA7/view) |

---

> **Deployment Note:** The system runs locally due to FastAPI backend, Python runtime, Ollama (local LLM inference), and ML pipeline requirements. GitHub Pages supports static hosting only.
