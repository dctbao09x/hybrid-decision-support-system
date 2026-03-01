# backend/inference/api_server.py
"""
Unified API Gateway
===================

**SINGLE ENTRYPOINT** for all backend APIs.

All endpoints are consolidated under /api/v1/*:
  
  /api/v1/
   ├─ health/*     — Health checks (live, full, ready, scoring, llm, warmup)
   ├─ ops/*        — Operations (sla, alerts, status, recovery/*, metrics/*)
   ├─ ml/*         — ML operations (evaluation, models, retrain, deploy)
   ├─ infer/*      — Inference (predict, feedback, analyze, recommendations)
   ├─ explain/*    — Explanations (Stage 5)
   ├─ pipeline/*   — Data pipeline (run, recommendations)
   ├─ crawlers/*   — Crawler management
   ├─ kb/*         — Knowledge base CRUD
   └─ chat/*       — Chat endpoints

Usage:
    # Create and run
    api = create_inference_api()
    uvicorn.run(api.app, host="0.0.0.0", port=8000)
    
    # Or with run_api.py
    python -m uvicorn backend.run_api:app --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
import uuid
import contextvars
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import numpy as np
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

# Ensure backend is in path
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.inference.model_loader import ModelLoader
from backend.inference.ab_router import ABRouter, RouteTarget
from backend.inference.feedback_collector import FeedbackCollector
from backend.inference.metric_tracker import MetricTracker

# Type-only imports
if TYPE_CHECKING:
    from backend.scoring.explain.xai import XAIService
    from backend.explain.stage3 import Stage3Engine
    from backend.api.controllers.explain_controller import ExplainController
    from backend.storage.explain_history import ExplainHistoryStorage
    from backend.ops.integration import OpsHub
    from backend.crawler_manager import CrawlerManager
    from backend.main_controller import MainController

# XAI Integration (runtime)
try:
    from backend.scoring.explain.xai import XAIService as _XAIService, get_xai_service
    XAI_AVAILABLE = True
except ImportError:
    XAI_AVAILABLE = False
    _XAIService = None
    get_xai_service = None

# Stage 3 Integration (runtime)
try:
    from backend.explain.stage3 import run_stage3, Stage3Engine as _Stage3Engine
    STAGE3_AVAILABLE = True
except ImportError:
    STAGE3_AVAILABLE = False
    run_stage3 = None
    _Stage3Engine = None

# Stage 5 Explain API Integration (runtime)
try:
    from backend.api.routers.explain_router import router as explain_router
    from backend.api.routers.explain_router import router_v2 as explain_router_v2
    from backend.api.routers.explain_router import set_controller
    from backend.api.controllers.explain_controller import ExplainController as _ExplainController
    from backend.storage.explain_history import ExplainHistoryStorage as _ExplainHistoryStorage
    STAGE5_AVAILABLE = True
except ImportError as e:
    STAGE5_AVAILABLE = False
    explain_router = None
    explain_router_v2 = None
    set_controller = None
    _ExplainController = None
    _ExplainHistoryStorage = None

logger = logging.getLogger("api.gateway")


# ═══════════════════════════════════════════════════════════════════════════
# Correlation ID Context
# ═══════════════════════════════════════════════════════════════════════════

correlation_id_var = contextvars.ContextVar("correlation_id", default=None)


class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = correlation_id_var.get() or "-"
        return True


# ═══════════════════════════════════════════════════════════════════════════
#  Request/Response Models (for legacy compatibility)
# ═══════════════════════════════════════════════════════════════════════════

class PredictRequest(BaseModel):
    """Career prediction request."""
    user_id: str = Field(..., description="Unique user identifier")
    math_score: float = Field(..., ge=0, le=100, description="Math aptitude score")
    physics_score: float = Field(..., ge=0, le=100, description="Physics aptitude score")
    interest_it: float = Field(..., ge=0, le=100, description="IT interest level")
    logic_score: float = Field(..., ge=0, le=100, description="Logical reasoning score")


class PredictResponse(BaseModel):
    """Career prediction response with XAI explanation."""
    prediction_id: str
    user_id: str
    career: str = Field(..., description="Predicted career")
    confidence: float
    reason: List[str] = Field(default_factory=list, description="Explanation reasons")
    explain_text: str = Field(default="", description="Full explanation text from Stage 3")
    xai_meta: Dict[str, Any] = Field(default_factory=dict, description="XAI metadata")
    top_careers: List[Dict[str, Any]] = Field(default_factory=list)
    model_version: str
    latency_ms: float
    timestamp: str
    
    @property
    def predicted_career(self) -> str:
        return self.career


class FeedbackRequest(BaseModel):
    """Feedback submission request."""
    prediction_id: str = Field(..., description="ID from predict response")
    actual_career: str = Field(..., description="Actual career outcome")


class FeedbackResponse(BaseModel):
    """Feedback submission response."""
    prediction_id: str
    matched: bool
    message: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    active_model: Optional[str] = None
    canary_model: Optional[str] = None
    uptime_seconds: float
    timestamp: str


class MetricsResponse(BaseModel):
    """Metrics response."""
    latency: Dict[str, float]
    requests: Dict[str, int]
    error_rate: float
    qps: float
    model_counts: Dict[str, int]
    feedback: Dict[str, Any]
    timestamp: str


class KillSwitchRequest(BaseModel):
    """Kill switch request."""
    enabled: bool


class KillSwitchResponse(BaseModel):
    """Kill switch response."""
    kill_switch: bool = Field(..., description="Current kill switch state")
    message: str = Field(..., description="Status message")
    timestamp: str = Field(..., description="Response timestamp")


class ModelInfo(BaseModel):
    """Model version information."""
    version: str = Field(..., description="Model version identifier")
    type: str = Field(default="unknown", description="Model type")
    path: str = Field(default="", description="Model file path")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    is_active: bool = Field(default=False, description="Whether this is the active model")


class RouterStats(BaseModel):
    """A/B router statistics."""
    active_version: str = Field(default="unknown", description="Active model version")
    canary_version: Optional[str] = Field(default=None, description="Canary model version")
    canary_ratio: float = Field(default=0.0, description="Canary traffic ratio")
    total_requests: int = Field(default=0, description="Total routed requests")
    active_requests: int = Field(default=0, description="Requests to active model")
    canary_requests: int = Field(default=0, description="Requests to canary model")
    kill_switch_enabled: bool = Field(default=False, description="Kill switch state")


class WarmupResponse(BaseModel):
    """LLM warmup response."""
    status: str = Field(..., description="Warmup status")
    llm_ready: bool = Field(default=False, description="Whether LLM is ready")
    model: str = Field(default="", description="LLM model name")
    warmup_time_ms: float = Field(default=0.0, description="Warmup duration")
    message: str = Field(default="", description="Status message")


# ═══════════════════════════════════════════════════════════════════════════
#  Inference API Gateway
# ═══════════════════════════════════════════════════════════════════════════

class InferenceAPI:
    """
    Unified API Gateway with model loading, A/B routing, and all routers.
    
    This is the **SINGLE ENTRYPOINT** for production.
    
    Usage::
    
        api = InferenceAPI()
        api.setup()
        
        # Get FastAPI app
        app = api.get_app()
        
        # Run with uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    """
    
    def __init__(self):
        self.app = FastAPI(
            title="Hybrid Decision Support System API",
            description="Unified API Gateway - Career Guidance with ML and Explanation",
            version="2.0.0",
        )
        
        # CORS middleware - allow frontend access
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:5174",
                "http://127.0.0.1:5174",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ],
            allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Core Components
        self._model_loader: Optional[ModelLoader] = None
        self._router: Optional[ABRouter] = None
        self._feedback: Optional[FeedbackCollector] = None
        self._metrics: Optional[MetricTracker] = None
        self._xai_service: Optional["XAIService"] = None
        self._stage3_engine: Optional["Stage3Engine"] = None
        
        # Stage 5 components
        self._explain_controller: Optional["ExplainController"] = None
        self._history_storage: Optional["ExplainHistoryStorage"] = None
        
        # LiveOps components
        self._command_engine: Optional[object] = None
        
        # External components (set during setup)
        self._main_control: Optional["MainController"] = None
        self._ops_hub: Optional["OpsHub"] = None
        self._crawler_manager: Optional["CrawlerManager"] = None
        
        # State
        self._start_time = time.time()
        self._classes: List[str] = []
        self._feature_names: List[str] = [
            "math_score", "physics_score", "interest_it", "logic_score"
        ]
        self._metrics_task: Optional[asyncio.Task] = None
        
        # Register middleware
        self._register_middleware()
        
        # Register lifecycle events
        self._register_lifecycle()
    
    def setup(
        self,
        model_loader: Optional[ModelLoader] = None,
        router: Optional[ABRouter] = None,
        feedback: Optional[FeedbackCollector] = None,
        metrics: Optional[MetricTracker] = None,
        xai_service: Optional["XAIService"] = None,
        xai_config: Optional[Dict[str, Any]] = None,
        stage3_engine: Optional["Stage3Engine"] = None,
        explain_config: Optional[Dict[str, Any]] = None,
        main_control: Optional["MainController"] = None,
        ops_hub: Optional["OpsHub"] = None,
        crawler_manager: Optional["CrawlerManager"] = None,
    ) -> None:
        """Initialize all components and register routers."""
        
        # Store external components
        self._main_control = main_control
        self._ops_hub = ops_hub
        self._crawler_manager = crawler_manager
        
        # Initialize inference components
        self._model_loader = model_loader or ModelLoader()
        self._router = router or ABRouter()
        self._feedback = feedback or FeedbackCollector()
        
        # Initialize XAI Service (Stage 2)
        if XAI_AVAILABLE:
            self._xai_service = xai_service or get_xai_service()
            if xai_config:
                self._xai_service.load_config(xai_config)
        
        # Initialize Stage 3 Engine
        if STAGE3_AVAILABLE and _Stage3Engine:
            self._stage3_engine = stage3_engine or _Stage3Engine()
            if explain_config:
                self._stage3_engine.load_config(explain_config)
        
        self._metrics = metrics or MetricTracker()
        
        # Load active model
        model_version = "unknown"
        try:
            model = self._model_loader.load_active()
            self._classes = self._model_loader.get_classes()
            self._router.configure(active_version=model.version)
            model_version = model.version
            
            # Initialize XAI with model
            if self._xai_service:
                self._xai_service.load_model(
                    model=model.model,
                    feature_names=self._feature_names,
                    classes=self._classes,
                    model_version=model.version,
                )
            
            logger.info("API Gateway initialized with model %s", model.version)
        except FileNotFoundError:
            logger.warning("No active model found - API will return errors until model is deployed")
        
        # Register all routers
        self._register_all_routers()
        
        # Initialize Stage 5 Explain API
        self._setup_stage5(main_control=main_control, model_version=model_version)
    
    def _register_middleware(self) -> None:
        """Register middleware for correlation ID and metrics."""
        
        @self.app.middleware("http")
        async def correlation_middleware(request: Request, call_next):
            correlation_id = str(uuid.uuid4())
            token = correlation_id_var.set(correlation_id)
            
            logger.debug(
                "Request started %s %s",
                request.method,
                request.url.path,
            )
            
            start_time = time.monotonic()
            
            try:
                response = await call_next(request)
            finally:
                correlation_id_var.reset(token)
            
            duration = time.monotonic() - start_time
            
            # Record metrics (skip /metrics to avoid recursion)
            if self._ops_hub and not request.url.path.startswith("/api/v1/ops/metrics"):
                if hasattr(self._ops_hub, 'metrics'):
                    self._ops_hub.metrics.record_request(
                        method=request.method,
                        path=request.url.path,
                        status_code=response.status_code,
                        duration=duration,
                    )
            
            response.headers["X-Correlation-ID"] = correlation_id
            return response
    
    def _register_lifecycle(self) -> None:
        """Register startup and shutdown events."""
        
        @self.app.on_event("startup")
        async def startup_event():
            logger.info("API Gateway starting...")
            
            # Initialize ops if available
            if self._ops_hub:
                await self._ops_hub.startup()
            
            # Start LiveOps command engine if available
            if hasattr(self, '_command_engine') and self._command_engine:
                await self._command_engine.start()
                logger.info("LiveOps CommandEngine started")
            
            # Warmup scoring engine and LLM
            logger.info("Starting system warmup...")
            try:
                from backend.ops.warmup import get_warmup_manager
                warmup = get_warmup_manager()
                warmup_status = await warmup.initialize_all()
                
                scoring_status = warmup_status.get("components", {}).get("scoring", {}).get("status", "unknown")
                llm_status = warmup_status.get("components", {}).get("llm", {}).get("status", "unknown")
                startup_time = warmup_status.get("startup_time_ms", 0)
                
                logger.info(
                    "Warmup complete: scoring=%s, llm=%s, time=%.1fms",
                    scoring_status, llm_status, startup_time,
                )
            except ImportError:
                logger.warning("Warmup manager not available")
            
            # Start metrics background task
            if self._ops_hub:
                self._metrics_task = asyncio.create_task(self._metrics_background_loop())
                logger.info("Metrics background collector started")
            
            logger.info("API Gateway ready to accept traffic")
        
        @self.app.on_event("shutdown")
        async def shutdown_event():
            logger.info("API Gateway shutting down...")
            
            # Stop LiveOps command engine
            if hasattr(self, '_command_engine') and self._command_engine:
                await self._command_engine.stop()
                logger.info("LiveOps CommandEngine stopped")
            
            if self._metrics_task:
                self._metrics_task.cancel()
                try:
                    await self._metrics_task
                except asyncio.CancelledError:
                    pass
            
            if self._ops_hub:
                await self._ops_hub.shutdown()
            
            if self._crawler_manager:
                await self._crawler_manager.shutdown()
    
    async def _metrics_background_loop(self):
        """Periodic infra metrics collection."""
        while True:
            try:
                if self._ops_hub and hasattr(self._ops_hub, 'metrics'):
                    self._ops_hub.metrics.refresh_infra_gauges()
                    
                    # Auto-alert evaluation
                    error_rt = self._ops_hub.metrics.error_rate()
                    if error_rt > 0.05:
                        from backend.ops.monitoring.alerts import AlertSeverity
                        await self._ops_hub.alerts.fire(
                            title="High error rate",
                            message=f"HTTP error rate: {error_rt:.1%}",
                            severity=AlertSeverity.CRITICAL,
                            source="metrics",
                            context={"error_rate": error_rt},
                        )
            except Exception as exc:
                logger.debug("metrics loop error: %s", exc)
            
            await asyncio.sleep(15)
    
    def _register_all_routers(self) -> None:
        """
        Register all routers using deterministic registry.
        
        NO TRY/EXCEPT - if any router fails to import, the server FAILS FAST.
        This ensures all workers have identical routing tables.
        """
        from backend.api.router_registry import (
            get_all_routers,
            setup_dependencies,
            setup_explain_controller,
            setup_liveops_command_engine,
            get_liveops_ws_handler,
            get_auth_admin_dependency,
            validate_route_count,
            CORE_ROUTERS,
            EXPLAIN_ROUTERS,
            ADMIN_ROUTERS,
            LIVEOPS_ROUTERS,
        )
        from fastapi import Depends
        
        # Inject dependencies into routers
        setup_dependencies(
            main_control=self._main_control,
            ops_hub=self._ops_hub,
            crawler_manager=self._crawler_manager,
            inference_api=self,
        )
        
        # Register core routers
        for router_info in CORE_ROUTERS:
            self.app.include_router(
                router_info.router,
                prefix=router_info.prefix,
                tags=router_info.tags,
            )
        logger.info(f"Registered {len(CORE_ROUTERS)} core routers")
        
        # Register explain routers
        for router_info in EXPLAIN_ROUTERS:
            self.app.include_router(
                router_info.router,
                prefix=router_info.prefix,
                tags=router_info.tags,
            )
        logger.info(f"Registered {len(EXPLAIN_ROUTERS)} explain routers")
        
        # Register admin routers
        for router_info in ADMIN_ROUTERS:
            self.app.include_router(
                router_info.router,
                prefix=router_info.prefix,
                tags=router_info.tags,
            )
        logger.info(f"Registered {len(ADMIN_ROUTERS)} admin routers")
        
        # Register LiveOps with auth dependency
        auth_admin = get_auth_admin_dependency()
        for router_info in LIVEOPS_ROUTERS:
            self.app.include_router(
                router_info.router,
                prefix=router_info.prefix,
                tags=router_info.tags,
                dependencies=[Depends(auth_admin)],
            )
        
        # Add LiveOps WebSocket route
        self.app.add_websocket_route("/ws/live", get_liveops_ws_handler())
        logger.info(f"Registered {len(LIVEOPS_ROUTERS)} LiveOps routers + WebSocket")
        
        # Store command engine for lifecycle management
        self._command_engine = setup_liveops_command_engine()
        
        # Register legacy compatibility routes (backward compat)
        self._register_legacy_routes()
        
        # CRITICAL: Validate route count to ensure no silent failures
        validate_route_count(self.app)
        
        logger.info("All routers registered successfully (deterministic)")
    
    def _register_legacy_routes(self) -> None:
        """Register legacy routes for backward compatibility."""
        
        @self.app.get("/")
        async def root():
            return {"message": "HDSS Backend Running", "api": "v2"}
        
        # Legacy /health endpoint (redirect to /api/v1/health/full)
        @self.app.get("/health", tags=["Legacy"])
        async def legacy_health():
            """Legacy health check - redirects to /api/v1/health/full."""
            active_model = "none"
            canary_model = None
            
            if self._model_loader:
                try:
                    active = self._model_loader.get_model()
                    active_model = active.version
                except Exception:
                    pass
                
                if self._model_loader._canary_model:
                    canary_model = self._model_loader._canary_model.version
            
            return HealthResponse(
                status="healthy" if active_model != "none" else "degraded",
                active_model=active_model,
                canary_model=canary_model,
                uptime_seconds=time.time() - self._start_time,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        
        # Legacy /metrics endpoint
        @self.app.get("/metrics", tags=["Legacy"])
        async def legacy_metrics():
            """Legacy metrics - Prometheus format."""
            if self._ops_hub and hasattr(self._ops_hub, 'metrics'):
                return PlainTextResponse(
                    content=self._ops_hub.metrics.export_prometheus(),
                    media_type="text/plain; version=0.0.4; charset=utf-8",
                )
            return PlainTextResponse(content="# No metrics available\n")
        
        # Legacy /predict endpoint (backward compat)
        @self.app.post("/predict", response_model=PredictResponse, tags=["Legacy"])
        async def legacy_predict(request: PredictRequest):
            """Legacy predict - use /api/v1/infer/predict instead."""
            return await self._handle_predict(request)
        
        # Legacy /feedback endpoint
        @self.app.post("/feedback", response_model=FeedbackResponse, tags=["Legacy"])
        async def legacy_feedback(request: FeedbackRequest):
            """Legacy feedback - use /api/v1/infer/feedback instead."""
            if not self._feedback:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Feedback collector not initialized",
                )
            
            matched = self._feedback.log_feedback(
                prediction_id=request.prediction_id,
                actual_career=request.actual_career,
            )
            
            return FeedbackResponse(
                prediction_id=request.prediction_id,
                matched=matched,
                message="Feedback recorded" if matched else "Prediction not found",
            )

        @self.app.post("/api/v1/model/retrain", tags=["Legacy"])
        async def legacy_model_retrain():
            """Legacy retrain route - use /api/v1/mlops/train instead."""
            from backend.mlops.lifecycle import get_mlops_manager

            manager = get_mlops_manager()
            result = await manager.train(trigger="legacy_model_retrain", source="feedback")
            result["deprecated"] = True
            result["replacement"] = "/api/v1/mlops/train"
            return result

        @self.app.post("/api/v1/validation/run", tags=["Legacy"])
        async def legacy_validation_run():
            """Legacy validation route - use /api/v1/mlops/validate instead."""
            from backend.mlops.lifecycle import get_mlops_manager

            manager = get_mlops_manager()
            result = manager.validate()
            result["deprecated"] = True
            result["replacement"] = "/api/v1/mlops/validate"
            return result

        @self.app.post("/api/v1/pipeline/train", tags=["Legacy"])
        async def legacy_pipeline_train():
            from backend.mlops.lifecycle import get_mlops_manager

            manager = get_mlops_manager()
            result = await manager.train(trigger="legacy_pipeline_train", source="feedback")
            result["deprecated"] = True
            result["replacement"] = "/api/v1/mlops/train"
            return result

        @self.app.post("/api/v1/pipeline/validate", tags=["Legacy"])
        async def legacy_pipeline_validate():
            from backend.mlops.lifecycle import get_mlops_manager

            manager = get_mlops_manager()
            result = manager.validate()
            result["deprecated"] = True
            result["replacement"] = "/api/v1/mlops/validate"
            return result

        @self.app.post("/api/v1/pipeline/deploy", tags=["Legacy"])
        async def legacy_pipeline_deploy(model_id: str):
            from backend.mlops.lifecycle import get_mlops_manager

            manager = get_mlops_manager()
            result = manager.deploy(model_id=model_id)
            result["deprecated"] = True
            result["replacement"] = "/api/v1/mlops/deploy"
            return result

        @self.app.post("/api/v1/pipeline/rollback", tags=["Legacy"])
        async def legacy_pipeline_rollback():
            from backend.mlops.lifecycle import get_mlops_manager

            manager = get_mlops_manager()
            result = manager.rollback(reason="legacy_pipeline_rollback")
            result["deprecated"] = True
            result["replacement"] = "/api/v1/mlops/rollback"
            return result
    
    async def _handle_predict(self, request: PredictRequest) -> PredictResponse:
        """Handle prediction request (shared by legacy and new routes)."""
        start_time = time.time()
        
        if not self._model_loader:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Model not loaded",
            )
        
        try:
            # Route to appropriate model
            routing = self._router.route(request.user_id)
            use_canary = routing.target == RouteTarget.CANARY
            
            # Get model
            model = self._model_loader.get_model(use_canary=use_canary)
            
            # Prepare features
            features = np.array([[
                request.math_score,
                request.physics_score,
                request.interest_it,
                request.logic_score,
            ]])
            
            # Predict
            prediction = model.predict(features)[0]
            probabilities = model.predict_proba(features)[0]
            
            # Decode prediction
            predicted_career = self._model_loader.decode_prediction(prediction)
            confidence = float(probabilities[prediction])
            
            # Get top careers
            top_indices = np.argsort(probabilities)[::-1][:3]
            top_careers = [
                {
                    "career": self._model_loader.decode_prediction(idx),
                    "probability": float(probabilities[idx]),
                }
                for idx in top_indices
            ]
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Log prediction
            prediction_id = self._feedback.log_prediction(
                user_id=request.user_id,
                features={
                    "math_score": request.math_score,
                    "physics_score": request.physics_score,
                    "interest_it": request.interest_it,
                    "logic_score": request.logic_score,
                },
                predicted_career=predicted_career,
                predicted_proba=confidence,
                model_version=model.version,
                latency_ms=latency_ms,
                routing_target=routing.target.value,
            )
            
            # Record metrics
            self._metrics.record_success(
                latency_ms=latency_ms,
                model_version=model.version,
            )
            
            # Generate XAI explanation
            reasons = []
            xai_meta = {}
            explain_text = ""
            
            if self._xai_service and self._xai_service.is_ready():
                try:
                    pred_idx = None
                    if hasattr(model.model, "classes_"):
                        try:
                            pred_idx = list(model.model.classes_).index(prediction)
                        except (ValueError, TypeError):
                            pred_idx = int(prediction) if isinstance(prediction, (int, np.integer)) else None
                    
                    xai_result = self._xai_service.explain(
                        sample=features[0],
                        predicted_career=predicted_career,
                        confidence=confidence,
                        prediction_idx=pred_idx,
                        user_id=request.user_id,
                    )
                    
                    reasons = xai_result.reasons
                    xai_meta = xai_result.xai_meta
                    
                except Exception as xai_err:
                    logger.warning(f"XAI explanation failed: {xai_err}")
                    reasons = []
                    xai_meta = {"error": str(xai_err)}
            
            # Run Stage 3
            if self._stage3_engine and self._stage3_engine.is_enabled():
                try:
                    stage2_output = {
                        "trace_id": prediction_id,
                        "career": predicted_career,
                        "reason_codes": self._extract_reason_codes(xai_meta),
                        "sources": self._extract_sources(xai_meta),
                        "confidence": confidence,
                    }
                    
                    stage3_result = self._stage3_engine.run(stage2_output)
                    
                    if stage3_result.reasons:
                        reasons = stage3_result.reasons
                    explain_text = stage3_result.explain_text
                    
                    xai_meta["stage3"] = {
                        "used_codes": stage3_result.used_codes,
                        "skipped_codes": stage3_result.skipped_codes,
                    }
                    
                except Exception as stage3_err:
                    logger.error(f"Stage 3 processing failed: {stage3_err}")
                    xai_meta["stage3_error"] = str(stage3_err)
            
            return PredictResponse(
                prediction_id=prediction_id,
                user_id=request.user_id,
                career=predicted_career,
                confidence=confidence,
                reason=reasons,
                explain_text=explain_text,
                xai_meta=xai_meta,
                top_careers=top_careers,
                model_version=model.version,
                latency_ms=latency_ms,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._metrics.record_error(
                latency_ms=latency_ms,
                model_version="unknown",
                error_type=type(e).__name__,
            )
            logger.error("Prediction error: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )
    
    def _setup_stage5(
        self,
        main_control: Optional[Any] = None,
        model_version: str = "unknown",
    ) -> None:
        """
        Initialize Stage 5 Explain API components.
        
        Uses the deterministic router_registry for setup.
        """
        from backend.api.router_registry import setup_explain_controller
        
        try:
            self._explain_controller = setup_explain_controller(
                main_control=main_control,
                model_version=model_version,
            )
            logger.info("Stage 5 Explain API initialized via router_registry")
        except Exception as e:
            logger.error(f"Stage 5 initialization failed: {e}")
            self._explain_controller = None
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application."""
        return self.app
    
    def _extract_reason_codes(self, xai_meta: Dict[str, Any]) -> List[str]:
        """Extract reason codes from XAI metadata for Stage 3."""
        codes = []
        top_features = xai_meta.get("top_features", [])
        for feature in top_features:
            if isinstance(feature, dict):
                name = feature.get("name", "")
                importance = feature.get("importance", 0)
                if importance >= 0.15:
                    codes.append(f"{name}_high")
                elif importance >= 0.10:
                    codes.append(f"{name}_good")
        return codes
    
    def _extract_sources(self, xai_meta: Dict[str, Any]) -> List[str]:
        """Extract evidence sources from XAI metadata."""
        method = xai_meta.get("method", "")
        sources = []
        if "shap" in method.lower():
            sources.append("shap")
        if "fi" in method.lower() or "importance" in method.lower():
            sources.append("importance")
        if "coef" in method.lower():
            sources.append("coef")
        if "perm" in method.lower():
            sources.append("perm")
        if not sources:
            sources = ["importance"]
        return sources


# ═══════════════════════════════════════════════════════════════════════════
#  Factory Function
# ═══════════════════════════════════════════════════════════════════════════

def create_inference_api(
    model_loader: Optional[ModelLoader] = None,
    router: Optional[ABRouter] = None,
    feedback: Optional[FeedbackCollector] = None,
    metrics: Optional[MetricTracker] = None,
    main_control: Optional[Any] = None,
    ops_hub: Optional[Any] = None,
    crawler_manager: Optional[Any] = None,
) -> InferenceAPI:
    """
    Create and configure the unified API Gateway.
    
    Args:
        model_loader: ModelLoader instance (optional)
        router: ABRouter instance (optional)
        feedback: FeedbackCollector instance (optional)
        metrics: MetricTracker instance (optional)
        main_control: MainController instance for full pipeline (optional)
        ops_hub: OpsHub instance for monitoring (optional)
        crawler_manager: CrawlerManager instance for crawlers (optional)
    
    Returns:
        Configured InferenceAPI instance
    """
    api = InferenceAPI()
    api.setup(
        model_loader=model_loader,
        router=router,
        feedback=feedback,
        metrics=metrics,
        main_control=main_control,
        ops_hub=ops_hub,
        crawler_manager=crawler_manager,
    )
    return api
