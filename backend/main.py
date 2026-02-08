# backend/main.py
"""
FastAPI Application Entry Point
Career Guidance Hybrid System

Role:
- API Gateway
- Knowledge Base bootstrap
- Service lifecycle management
"""

import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# =====================================================
# PATH CONFIG
# =====================================================

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))


# =====================================================
# LOGGING CONFIG
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("career-api")


# =====================================================
# IMPORTS (AFTER PATH SETUP)
# =====================================================

from api import kb_routes
from api import analyze
from api import recommendations
from api import chat
from api import career_library

from kb.database import init_db
from taxonomy.validate import startup_check, coverage_report


# =====================================================
# LIFECYCLE MANAGEMENT
# =====================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup / shutdown lifecycle
    """

    logger.info("Initializing Knowledge Base...")
    init_db()
    logger.info("Knowledge Base ready")

    try:
        taxonomy_status = startup_check()
        logger.info("Taxonomy loaded: %s", taxonomy_status)
        logger.info("Taxonomy coverage: %s", coverage_report())
    except Exception as exc:
        logger.exception("Taxonomy startup check failed: %s", exc)
        raise

    yield

    logger.info("Application shutdown")


# =====================================================
# APP FACTORY
# =====================================================

def create_app() -> FastAPI:

    app = FastAPI(
        title="Career Guidance AI API",
        description="Hybrid Decision Support System",
        version="2.0.0",
        lifespan=lifespan,
    )
    # ---------------- CORS ----------------

    app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    )

    # ---------------- ROUTES ----------------

    app.include_router(kb_routes.router, prefix="/kb", tags=["KnowledgeBase"])
    app.include_router(analyze.router, prefix="/analyze", tags=["Analysis"])
    app.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
    app.include_router(chat.router, prefix="/chat", tags=["Chat"])
    app.include_router(career_library.router, prefix="/career-library", tags=["CareerLibrary"])

    # ---------------- HEALTH ----------------

    @app.get("/", tags=["System"])
    def health_check():
        return {
            "status": "ok",
            "service": "Career Guidance API",
            "version": "2.0.0",
            "kb": "enabled",
        }

    return app


# =====================================================
# APP INSTANCE
# =====================================================

app = create_app()


# =====================================================
# LOCAL RUNNER
# =====================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

