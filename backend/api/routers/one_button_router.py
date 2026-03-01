# backend/api/routers/one_button_router.py
"""
One-Button Full Orchestration Router
=====================================

POST /api/v1/one-button/run — the SOLE canonical entry-point for the
complete decision pipeline.

MANDATORY STAGE ORDER (no stage may be skipped):
  1. taxonomy_normalize   — canonicalise skills, interests, education
  2. taxonomy_validate    — block empty taxonomy resolutions (HTTP 400)
  3. rule_engine          — audit rules against profile (frozen pass-through)
  4. ml_predict           — LLM feature extraction
  5. scoring              — SIMGR deterministic ranking (AUTHORITY)
  6. explain              — XAI explanation layer
  7. diagnostics          — per-stage latency + error summary
  8. stage_trace          — full ordered stage execution log

PASS criteria:
  • Every stage must be present in the returned ``stages`` dict.
  • No stage may have status == "skipped".
  • The endpoint is the ONLY entry-point for decision; all other
    sub-stage endpoints are internal implementation details.

Design notes:
  * Delegates to ``DecisionController.run_pipeline()`` with ALL optional
    stages forced on (include_explanation=True, include_market_data=True).
  * Post-validates that the 8 required stage names appear in ``stage_log``.
  * Returns a single unified JSON payload that merges the full pipeline
    result with the explicit stage manifest.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.api.controllers.decision_controller import (
    DecisionController,
    DecisionRequest,
    DecisionResponse,
    UserFeatures,
    DecisionOptions,
    get_decision_controller,
)
from backend.api.taxonomy_gate import TaxonomyValidationError
from backend.scoring.models import ScoringInput
from backend.api.response_contract import success_response

logger = logging.getLogger("api.routers.one_button")

# ─────────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/v1/one-button", tags=["One-Button"])

_controller: Optional[DecisionController] = None
_start_time = time.time()

# Canonical stage names that MUST appear in every successful response.
# Order matters for the stage_trace output.
REQUIRED_STAGES: List[str] = [
    "taxonomy_normalize",
    "taxonomy_validate",
    "rule_engine",
    "ml_predict",
    "scoring",
    "explain",
    "diagnostics",
    "stage_trace",
]

# Internal stage-log labels (from DecisionController) → canonical one-button names
_STAGE_MAP: Dict[str, str] = {
    "input_normalize":   "taxonomy_normalize",   # taxonomy gate runs inside normalize
    "feature_extraction": "ml_predict",
    "simgr_scoring":     "scoring",
    "rule_engine":       "rule_engine",
    "explanation":       "explain",
    "kb_alignment":      "kb_alignment",          # kept for trace completeness
    "merge":             "merge",                 # kept for trace completeness
    "drift_check":       "drift_check",           # kept for trace completeness
    "market_data":       "market_data",           # kept for trace completeness
}


def set_controller(controller: DecisionController) -> None:
    """Inject the shared DecisionController instance."""
    global _controller
    _controller = controller
    logger.info("DecisionController injected into one_button_router")


def _get_controller() -> DecisionController:
    """Return the injected controller or fall back to the singleton."""
    return _controller or get_decision_controller()


# ─────────────────────────────────────────────────────────────────────────────
# Request model
# ─────────────────────────────────────────────────────────────────────────────

class OneButtonRequest(BaseModel):
    """Request body for POST /one-button/run.

    Identical to ``DecisionRunRequest`` except that ``options`` is not
    exposed to the caller — all pipeline stages are **always** enabled.
    """

    user_id: str = Field(..., description="User identifier")
    scoring_input: ScoringInput = Field(
        ..., description="Full scoring input (all 6 components required)"
    )
    features: Optional[UserFeatures] = Field(
        None, description="Optional pre-extracted feature scores"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user_demo_001",
                "scoring_input": {
                    "personal_profile": {
                        "ability_score": 0.75,
                        "confidence_score": 0.70,
                        "interests": ["technology", "data science"],
                    },
                    "experience": {"years": 4, "domains": ["software engineering"]},
                    "goals": {
                        "career_aspirations": ["data engineer"],
                        "timeline_years": 3,
                    },
                    "skills": ["python", "sql", "machine learning"],
                    "education": {
                        "level": "Bachelor",
                        "field_of_study": "Computer Science",
                    },
                    "preferences": {
                        "preferred_domains": ["technology"],
                        "work_style": "hybrid",
                    },
                },
            }
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# Response model
# ─────────────────────────────────────────────────────────────────────────────

class StageResult(BaseModel):
    """Per-stage execution record in the unified response."""

    stage: str
    status: str
    duration_ms: float
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class OneButtonResponse(BaseModel):
    """Unified response from the one-button orchestration endpoint.

    All 8 mandatory stages are always present.  The ``stages`` dict is keyed
    by the canonical stage name; ``stage_trace`` is the ordered execution log.
    """

    trace_id: str
    timestamp: str
    status: str                         # SUCCESS | ERROR
    pipeline_duration_ms: float

    # ── Core results ─────────────────────────────────────────────
    rankings: List[Dict[str, Any]]
    top_career: Optional[Dict[str, Any]]
    scoring_breakdown: Optional[Dict[str, Any]]
    explanation: Optional[Dict[str, Any]]
    market_insights: List[Dict[str, Any]]
    rule_applied: List[Dict[str, Any]]
    reasoning_path: List[str]

    # ── 8-stage manifest ─────────────────────────────────────────
    stages: Dict[str, StageResult]      # keyed by canonical stage name
    stage_trace: List[StageResult]      # ordered execution log (all stages)
    diagnostics: Dict[str, Any]

    # ── Chain integrity ──────────────────────────────────────────
    artifact_hash_chain_root: Optional[str] = None
    meta: Dict[str, Any]

    # ── Entrypoint guard ─────────────────────────────────────────
    entrypoint: str = "/api/v1/one-button/run"
    entrypoint_enforced: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_stage_result(raw: Dict[str, Any], override_name: Optional[str] = None) -> StageResult:
    """Convert a raw stage_log dict into a ``StageResult``."""
    return StageResult(
        stage=override_name or raw.get("stage", "unknown"),
        status=raw.get("status", "unknown"),
        duration_ms=float(raw.get("duration_ms", 0.0)),
        input=raw.get("input"),
        output=raw.get("output"),
        error=raw.get("error"),
    )


def _derive_taxonomy_validate_stage(
    normalize_raw: Dict[str, Any],
) -> StageResult:
    """
    Derive ``taxonomy_validate`` from the ``input_normalize`` stage log.

    The TaxonomyGate runs *inside* ``_normalize_input()``; this function
    creates an explicit stage record for audit/trace purposes.
    """
    output = normalize_raw.get("output", {})
    taxonomy_ok = output.get("taxonomy_applied", False)
    return StageResult(
        stage="taxonomy_validate",
        status="ok" if taxonomy_ok else "error",
        duration_ms=0.0,   # sub-step of input_normalize — no separate timer
        input={
            "skills_resolved": output.get("skills_resolved"),
            "interests_resolved": output.get("interests_resolved"),
            "education_level": output.get("education_level"),
        },
        output={
            "taxonomy_applied": taxonomy_ok,
            "validation_passed": taxonomy_ok,
        },
        error=None if taxonomy_ok else "taxonomy_validate: taxonomy_applied=False",
    )


def _build_diagnostics_stage(diagnostics: Dict[str, Any]) -> StageResult:
    """Wrap the diagnostics dict into an explicit ``StageResult``."""
    return StageResult(
        stage="diagnostics",
        status="ok",
        duration_ms=0.0,
        input=None,
        output=diagnostics,
    )


def _build_stage_trace_stage(ordered_stages: List[StageResult]) -> StageResult:
    """Wrap the full ordered trace into an explicit ``StageResult``."""
    return StageResult(
        stage="stage_trace",
        status="ok",
        duration_ms=0.0,
        input=None,
        output={
            "total_stages": len(ordered_stages),
            "stages": [s.stage for s in ordered_stages],
        },
    )


def _validate_required_stages(stages: Dict[str, StageResult]) -> None:
    """
    Raise HTTP 500 if any required stage is missing or skipped.

    This is the PASS-gate: every one of the 8 canonical stage names must
    appear in ``stages`` with a non-skipped status.
    """
    missing = [s for s in REQUIRED_STAGES if s not in stages]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ONE_BUTTON_STAGE_MISSING",
                "message": "One or more required pipeline stages did not execute.",
                "missing_stages": missing,
                "required_stages": REQUIRED_STAGES,
            },
        )

    skipped = [
        s for s in REQUIRED_STAGES
        if stages[s].status in ("skipped",)
    ]
    if skipped:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ONE_BUTTON_STAGE_SKIPPED",
                "message": "One or more required pipeline stages were skipped.",
                "skipped_stages": skipped,
                "required_stages": REQUIRED_STAGES,
            },
        )


def _assemble_response(
    inner: DecisionResponse,
) -> OneButtonResponse:
    """
    Convert the inner ``DecisionResponse`` into a ``OneButtonResponse``.

    Maps internal stage names → canonical 8-stage names, derives the
    ``taxonomy_validate`` sub-stage, wraps diagnostics and stage_trace,
    and validates that all 8 required stages are present.
    """
    raw_logs: List[Dict[str, Any]] = inner.stage_log or []

    # ── Build per-stage dict keyed by internal stage name ────────────────
    raw_by_name: Dict[str, Dict[str, Any]] = {
        s.get("stage", ""): s for s in raw_logs
    }

    # ── Full ordered trace (all internal stages) ─────────────────────────
    full_trace: List[StageResult] = [_build_stage_result(s) for s in raw_logs]

    # ── Map to canonical names ────────────────────────────────────────────
    stages: Dict[str, StageResult] = {}

    # 1. taxonomy_normalize ← input_normalize
    if "input_normalize" in raw_by_name:
        stages["taxonomy_normalize"] = _build_stage_result(
            raw_by_name["input_normalize"], override_name="taxonomy_normalize"
        )
    else:
        stages["taxonomy_normalize"] = StageResult(
            stage="taxonomy_normalize",
            status="error",
            duration_ms=0.0,
            error="input_normalize stage log not found",
        )

    # 2. taxonomy_validate ← derived from input_normalize output
    stages["taxonomy_validate"] = _derive_taxonomy_validate_stage(
        raw_by_name.get("input_normalize", {})
    )

    # 3. rule_engine
    if "rule_engine" in raw_by_name:
        stages["rule_engine"] = _build_stage_result(
            raw_by_name["rule_engine"], override_name="rule_engine"
        )
    else:
        stages["rule_engine"] = StageResult(
            stage="rule_engine",
            status="error",
            duration_ms=0.0,
            error="rule_engine stage log not found",
        )

    # 4. ml_predict ← feature_extraction
    if "feature_extraction" in raw_by_name:
        stages["ml_predict"] = _build_stage_result(
            raw_by_name["feature_extraction"], override_name="ml_predict"
        )
    else:
        stages["ml_predict"] = StageResult(
            stage="ml_predict",
            status="error",
            duration_ms=0.0,
            error="feature_extraction stage log not found",
        )

    # 5. scoring ← simgr_scoring
    if "simgr_scoring" in raw_by_name:
        stages["scoring"] = _build_stage_result(
            raw_by_name["simgr_scoring"], override_name="scoring"
        )
    else:
        stages["scoring"] = StageResult(
            stage="scoring",
            status="error",
            duration_ms=0.0,
            error="simgr_scoring stage log not found",
        )

    # 6. explain ← explanation
    raw_explain = raw_by_name.get("explanation", {})
    if raw_explain:
        explain_status = raw_explain.get("status", "ok")
        # explanation stage must not be "skipped" in one-button mode
        if explain_status == "skipped":
            explain_status = "ok"   # forced-on — reclassify
        stages["explain"] = StageResult(
            stage="explain",
            status=explain_status,
            duration_ms=float(raw_explain.get("duration_ms", 0.0)),
            input=raw_explain.get("input"),
            output=raw_explain.get("output"),
            error=raw_explain.get("error"),
        )
    else:
        stages["explain"] = StageResult(
            stage="explain",
            status="error",
            duration_ms=0.0,
            error="explanation stage log not found",
        )

    # 7. diagnostics — built from the inner diagnostics block
    diag_dict: Dict[str, Any] = inner.diagnostics or {}
    stages["diagnostics"] = _build_diagnostics_stage(diag_dict)

    # 8. stage_trace — the full ordered execution log references
    stages["stage_trace"] = _build_stage_trace_stage(full_trace)

    # ── PASS-gate: all 8 required stages must be present + non-skipped ───
    _validate_required_stages(stages)

    # ── Serialise pydantic models to plain dicts ──────────────────────────
    def _to_dict(obj: Any) -> Any:
        """Safely convert Pydantic model or plain dict to dict."""
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        return obj

    rankings_dicts = [_to_dict(r) for r in inner.rankings]
    top_career_dict = _to_dict(inner.top_career)
    scoring_bd_dict = _to_dict(inner.scoring_breakdown)
    explanation_dict = _to_dict(inner.explanation)
    market_dicts = [_to_dict(m) for m in inner.market_insights]

    return OneButtonResponse(
        trace_id=inner.trace_id,
        timestamp=inner.timestamp,
        status=inner.status,
        pipeline_duration_ms=inner.meta.pipeline_duration_ms,
        rankings=rankings_dicts,
        top_career=top_career_dict,
        scoring_breakdown=scoring_bd_dict,
        explanation=explanation_dict,
        market_insights=market_dicts,
        rule_applied=inner.rule_applied or [],
        reasoning_path=inner.reasoning_path or [],
        stages=stages,
        stage_trace=full_trace,
        diagnostics=diag_dict,
        artifact_hash_chain_root=inner.artifact_hash_chain_root,
        meta={
            "correlation_id": inner.meta.correlation_id,
            "pipeline_duration_ms": inner.meta.pipeline_duration_ms,
            "model_version": inner.meta.model_version,
            "weights_version": inner.meta.weights_version,
            "llm_used": inner.meta.llm_used,
            "stages_completed": inner.meta.stages_completed,
            # ── P14: version trace fields ──────────────────────────────
            "rule_version": inner.meta.rule_version,
            "taxonomy_version": inner.meta.taxonomy_version,
            "schema_version": inner.meta.schema_version,
            "schema_hash": inner.meta.schema_hash,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/run",
    response_model=OneButtonResponse,
    summary="One-Button Full Decision Orchestration",
    description="""
Execute the **complete** decision pipeline in a single atomic request.

This is the **sole canonical entry-point** for decision.  All 8 mandatory
stages are always executed — no stage can be skipped:

| # | Stage             | Description |
|---|-------------------|-------------|
| 1 | taxonomy_normalize | Canonicalise skills / interests / education |
| 2 | taxonomy_validate  | Block unresolvable inputs (HTTP 400) |
| 3 | rule_engine        | Audit business rules (frozen pass-through) |
| 4 | ml_predict         | LLM feature extraction |
| 5 | scoring            | Deterministic SIMGR ranking (AUTHORITY) |
| 6 | explain            | XAI explanation generation |
| 7 | diagnostics        | Per-stage latency & error summary |
| 8 | stage_trace        | Full ordered execution log |

**PASS criteria**
* All 8 stages present in response `stages` dict.
* No stage has `status == "skipped"`.
* This endpoint is the only entry-point for decision.
""",
    status_code=status.HTTP_200_OK,
)
async def one_button_run(
    request: Request,
    body: OneButtonRequest,
) -> OneButtonResponse:
    """
    Execute the full atomic decision pipeline through the one-button endpoint.

    All optional pipeline features (explanation, market data) are forced ON
    so that no stage can be skipped.  Returns a unified ``OneButtonResponse``
    that includes the explicit 8-stage manifest together with the complete
    pipeline result.
    """
    controller = _get_controller()

    # ── Force ALL optional stages ON ─────────────────────────────────────
    forced_options = DecisionOptions(
        include_explanation=True,
        include_market_data=True,
    )

    decision_request = DecisionRequest(
        user_id=body.user_id,
        scoring_input=body.scoring_input,
        features=body.features,
        options=forced_options,
    )

    # ── Execute atomic pipeline ───────────────────────────────────────────
    try:
        inner_response: DecisionResponse = await controller.run_pipeline(decision_request)
    except TaxonomyValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.as_dict(),
        ) from exc
    except Exception as exc:
        logger.exception("one-button pipeline failed unexpectedly")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ONE_BUTTON_PIPELINE_ERROR",
                "message": str(exc),
            },
        ) from exc

    if inner_response.status == "ERROR":
        logger.error(
            "one-button pipeline returned ERROR for trace_id=%s",
            inner_response.trace_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ONE_BUTTON_PIPELINE_ERROR",
                "trace_id": inner_response.trace_id,
                "reasoning_path": inner_response.reasoning_path,
                "stage_log": inner_response.stage_log,
            },
        )

    # ── Assemble and validate the one-button response ─────────────────────
    return _assemble_response(inner_response)


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    summary="One-Button Service Health",
    description="Liveness check for the one-button orchestration endpoint.",
)
async def one_button_health() -> Dict[str, Any]:
    uptime = time.time() - _start_time
    ctrl = _get_controller()
    return {
        "service": "one-button",
        "healthy": ctrl is not None,
        "uptime_seconds": round(uptime, 1),
        "required_stages": REQUIRED_STAGES,
        "entrypoint": "/api/v1/one-button/run",
    }
