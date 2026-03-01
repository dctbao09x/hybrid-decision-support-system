# backend/api/controllers/decision_controller.py
"""
Decision Controller (Atomic Execution)
======================================

Single entry point for the 1-button decision pipeline.

Pipeline stages (SEQUENTIAL, NON-PARALLELIZABLE):
  1. Input Normalize
  2. LLM Feature Extraction
  3. KB Alignment
  4. Merge
  5. SIMGR Scoring (DETERMINISTIC - AUTHORITY)
  6. Drift Check (metadata-only, does NOT modify rankings)
  7. Rule Engine
  8. Market Data Integration
  9. Explanation Layer

INVARIANTS:
  - Atomic transaction (no partial state)
  - Trace ID throughout
  - Deterministic scoring is AUTHORITY
  - LLM ONLY for extraction + explanation
  - Full snapshot logging (input + weights + output)

PROHIBITIONS:
  - LLM deciding instead of core
  - Split scoring across endpoints
  - Client calling pipeline steps
  - Uncontrolled async execution
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from backend.scoring.security.context import (
    ExecutionContextRegistry,
    ScoringExecutionContext,
    ExecutionEnvironment,
    create_scoring_context,
)
from backend.scoring.weight_manifest import (
    get_manifest,
    assert_no_env_override,
)
from backend.scoring.models import ScoringInput
from backend.scoring.errors import MissingComponentError
from backend.scoring.validation import validate_scoring_components
from backend.scoring.sub_scorer import assemble_breakdown, ScoringBreakdown
from backend.scoring.scoring_service import ScoringService as _ScoringService
from backend.api.artifacts import (
    PipelineArtifact,
    ArtifactChain,
    compute_stage_hash,
    STAGE_INPUT_NORMALIZE,
    STAGE_FEATURE_EXTRACTION,
    STAGE_KB_ALIGNMENT,
    STAGE_MERGE,
    STAGE_SIMGR_SCORING,
    STAGE_DRIFT_CHECK,
    STAGE_RULE_ENGINE,
    STAGE_MARKET_DATA,
    STAGE_EXPLANATION,
    STAGE_RESPONSE,
)
from backend.api.hash_chain_logger import append_record
from backend.api.decision_audit_logger import (
    append_decision_record as _append_decision_audit_record,
    NO_EXPLANATION_SENTINEL as _NO_EXPLANATION_SENTINEL,
)
from backend.training.retraining_monitor import RetrainingMonitor, RetrainingConfig
from backend.scoring.drift import (
    DistributionDriftDetector,
    get_drift_detector,
    DRIFT_TYPE_FEATURE,
    DRIFT_TYPE_PREDICTION,
    DRIFT_TYPE_LABEL,
)
from backend.governance.drift_event_log import log_drift_event, METRIC_JSD, METRIC_PSI
from backend.governance.rule_event_log import log_rule_batch as _log_rule_batch
from backend.governance.kb_mapping_log import log_kb_mapping as _log_kb_mapping
from backend.governance.version_resolver import resolve_versions, VersionBundle
from backend.governance.artifact_chain_log import log_artifact_chain
from backend.evaluation.rolling_evaluator import get_rolling_evaluator
from backend.evaluation.eval_metrics_log import log_eval_snapshot as _log_eval_snapshot
from backend.explain.unified_schema import UnifiedExplanation
from backend.explain.storage import get_explanation_storage
from backend.explain.consistency_validator import (
    ExplanationInconsistencyError,
    validate_explanation_consistency,
)
from backend.scoring.consistency_validator import validate_scoring_consistency
from backend.scoring.errors import InconsistentScoringError

logger = logging.getLogger("api.controllers.decision")


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class ScoringUnavailableError(Exception):
    """
    Raised when scoring service is unavailable and fallback is blocked.
    
    REMEDIATION: Circuit breaker pattern replaces hardcoded fallback.
    """
    pass


class InputValidationError(Exception):
    """Raised when required input fields are missing or invalid."""
    pass


# P8: Import TaxonomyValidationError from the dedicated gate module
from backend.api.taxonomy_gate import TaxonomyValidationError, TaxonomyGate  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
# EXPLANATION STATE CONTAINER
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class _ExplanationState:
    """
    Internal container returned by ``_generate_explanation()``.

    Carries the ``ExplanationResult`` (for the API response) together with the
    hash-chain metadata needed to populate the Stage-9 pipeline artifact.

    Fields
    ------
    result:            The Pydantic ExplanationResult for the API response.
    record_hash:       SHA-256 chain link written by ExplanationStorage.
                       Embeds this explanation into the tamper-evident log.
    explanation_id:    Storage-assigned row identifier (``exp-XXXXXXXXXX``).
    stage3_input_hash: SHA-256 of the Stage-3 input (XAI output before render).
    stage3_output_hash:SHA-256 of the Stage-3 output (rendered text/reasons).
    explanation_hash:  SHA-256 of the canonical UnifiedExplanation payload
                       (``UnifiedExplanation.explanation_hash``).  Forwarded
                       to ``decision_audit_logger`` for Stage-6 chain record.
    contributions:     Per-component weighted contributions forwarded to
                       ``ScoringConsistencyValidator`` for Rule-4 cross-check.
    """

    result: "ExplanationResult"
    record_hash: str = ""
    explanation_id: str = ""
    stage3_input_hash: str = ""
    stage3_output_hash: str = ""
    explanation_hash: str = ""
    contributions: Dict[str, float] = field(default_factory=dict)
    """Per-component weighted contributions from the UnifiedExplanation.
    Populated from ``UnifiedExplanation.per_component_contributions`` and
    forwarded to ``ScoringConsistencyValidator`` for Rule-4 cross-check."""

    def __bool__(self) -> bool:  # truthiness mirrors the inner result
        return self.result is not None


# ─── Rule engine result container ─────────────────────────────────────────────

@dataclass
class _RuleEngineResult:
    """
    Return value of ``_apply_rules()``.

    ``rankings`` is always IDENTICAL to the input (rule engine is frozen).
    ``rules_trace`` is the P7 audit list: one entry per evaluated rule.
    """
    rankings: List["CareerResult"]
    rules_trace: List[Dict[str, Any]]


# ═══════════════════════════════════════════════════════════════════════════════

class UserProfile(BaseModel):
    """
    User profile input for decision.
    
    REMEDIATED: Removed silent defaults for ability_score and confidence_score.
    Now requires explicit input OR uses derivation logic.
    """
    skills: List[str] = Field(
        default_factory=list,
        description="User's skills - at least 1 required"
    )
    interests: List[str] = Field(
        default_factory=list,
        description="User's interests - at least 1 required"
    )
    education_level: str = Field(
        default="Bachelor",
        description="Education level - has safe default (most common)"
    )
    # REMEDIATED: These are now Optional with explicit None default
    # Pipeline MUST handle None by deriving from features or rejecting
    ability_score: Optional[float] = Field(
        None, 
        ge=0.0, 
        le=1.0,
        description="Self-assessed ability [0,1]. If None, derived from features."
    )
    confidence_score: Optional[float] = Field(
        None, 
        ge=0.0, 
        le=1.0,
        description="Self-assessed confidence [0,1]. If None, derived from features."
    )
    
    @field_validator("skills", "interests")
    @classmethod
    def validate_non_empty_profile(cls, v: List[str], info) -> List[str]:
        """Validate at least one skill OR interest is provided."""
        # Cleaned list (remove empty strings)
        cleaned = [s.strip() for s in v if s and s.strip()]
        return cleaned


class UserFeatures(BaseModel):
    """
    Feature scores for explanation.
    
    All fields are Optional - when provided, they improve explanation quality.
    When ability_score/confidence_score are None, we derive from these.
    """
    math_score: Optional[float] = Field(None, ge=0, le=10)
    logic_score: Optional[float] = Field(None, ge=0, le=10)
    physics_score: Optional[float] = Field(None, ge=0, le=10)
    literature_score: Optional[float] = Field(None, ge=0, le=10)
    history_score: Optional[float] = Field(None, ge=0, le=10)
    geography_score: Optional[float] = Field(None, ge=0, le=10)
    biology_score: Optional[float] = Field(None, ge=0, le=10)
    chemistry_score: Optional[float] = Field(None, ge=0, le=10)
    economics_score: Optional[float] = Field(None, ge=0, le=10)
    creativity_score: Optional[float] = Field(None, ge=0, le=10)
    interest_tech: Optional[float] = Field(None, ge=0, le=10)
    interest_science: Optional[float] = Field(None, ge=0, le=10)
    interest_arts: Optional[float] = Field(None, ge=0, le=10)
    interest_social: Optional[float] = Field(None, ge=0, le=10)
    
    def derive_ability_score(self) -> float:
        """Derive ability score from academic features."""
        academic_scores = [
            self.math_score, self.logic_score, self.physics_score,
            self.literature_score, self.history_score, self.geography_score,
            self.biology_score, self.chemistry_score, self.economics_score,
        ]
        valid_scores = [s for s in academic_scores if s is not None]
        if valid_scores:
            # Normalize from 0-10 to 0-1
            return sum(valid_scores) / (len(valid_scores) * 10)
        # No features available - raise validation error
        raise InputValidationError(
            "Cannot derive ability_score: No academic features provided. "
            "Provide either ability_score or at least one academic feature."
        )
    
    def derive_confidence_score(self) -> float:
        """Derive confidence score from feature variance."""
        all_scores = [
            self.math_score, self.logic_score, self.physics_score,
            self.creativity_score, self.interest_tech, self.interest_science,
        ]
        valid_scores = [s/10 for s in all_scores if s is not None]
        if valid_scores:
            # Higher consistency = higher confidence
            variance = sum((s - sum(valid_scores)/len(valid_scores))**2 for s in valid_scores) / len(valid_scores)
            return max(0.3, min(0.9, 0.7 - variance))
        raise InputValidationError(
            "Cannot derive confidence_score: Insufficient features provided."
        )


class DecisionOptions(BaseModel):
    """Options for decision pipeline."""
    include_explanation: bool = True
    include_market_data: bool = True


class DecisionRequest(BaseModel):
    """Full decision pipeline request.

    ENFORCEMENT:
    - ``scoring_input`` is the single, strict source of truth for all
      mandatory scoring components.  Pydantic validates presence/type at
      construction time; ``validate_scoring_components()`` enforces it again
      at runtime inside ``_normalize_input()`` before any scoring logic runs.
    - The old ``profile: UserProfile`` field has been REMOVED.  Any caller
      supplying only a ``UserProfile`` dict will receive a 422 validation error.
    - ``features`` remains Optional: it feeds the LLM extraction stage only
      and is NOT a scoring authority.
    """
    user_id: str = Field(...)
    scoring_input: ScoringInput
    features: Optional[UserFeatures] = None
    options: Optional[DecisionOptions] = None


class CareerResult(BaseModel):
    """Single career result."""
    name: str
    domain: str
    total_score: float
    skill_score: float
    interest_score: float
    market_score: float
    growth_potential: float
    ai_relevance: float


class ExplanationFactor(BaseModel):
    """Explanation contributing factor."""
    name: str
    contribution: float
    description: str


class ExplanationResult(BaseModel):
    """Explanation from XAI layer."""
    summary: str
    factors: List[ExplanationFactor]
    confidence: float
    reasoning_chain: List[str]


class MarketInsight(BaseModel):
    """Market data for career."""
    career_name: str
    demand_level: str  # HIGH, MEDIUM, LOW
    salary_range: Dict[str, Any]
    growth_rate: float
    competition_level: str


class DecisionMeta(BaseModel):
    """Pipeline metadata."""
    correlation_id: str
    pipeline_duration_ms: float
    model_version: str
    weights_version: str
    llm_used: bool
    stages_completed: List[str]
    artifact_chain: Optional[List[Dict[str, Any]]] = None  # Full artifact trace
    # ── P14: Version trace (required for response lineage) ──────────────────
    rule_version: str = "unknown"
    taxonomy_version: str = "unknown"
    schema_version: str = "unknown"
    schema_hash: str = "unknown"


class DecisionResponse(BaseModel):
    """Full decision pipeline response.

    ``scoring_breakdown`` is always populated when the pipeline succeeds.
    It carries the five mandatory sub-scores (each in [0, 100]) together
    with the deterministic weighted-sum ``final_score``.  Consumers can
    verify ``final_score == sum(w_i * s_i)`` using the embedded `weights`
    and `contributions` fields.

    P7 TRACE FIELDS (always present on SUCCESS):
    - ``rule_applied``   : list of rules evaluated by the rule engine stage.
    - ``reasoning_path`` : ordered human-readable reasoning steps.
    - ``stage_log``      : timing + metadata for every pipeline stage.
    """
    trace_id: str
    timestamp: str
    status: str  # SUCCESS, PARTIAL, ERROR
    rankings: List[CareerResult]
    top_career: Optional[CareerResult]
    explanation: Optional[ExplanationResult]
    market_insights: List[MarketInsight]
    meta: DecisionMeta
    # ARTIFACT CHAIN INTEGRITY - cryptographic root of all stage hashes
    artifact_hash_chain_root: Optional[str] = None  # sha256(concatenated_stage_hashes)
    # SUB-SCORE DECOMPOSITION — always populated on SUCCESS
    scoring_breakdown: Optional[Dict[str, Any]] = None
    # P7: FULL TRACE CHAIN ─────────────────────────────────────────────────────
    # Rules evaluated during Stage 7 (engine is frozen — pass-through audit).
    rule_applied: List[Dict[str, Any]] = []
    # Step-by-step reasoning trace from input → scoring → rules → explanation.
    reasoning_path: List[str] = []
    # Per-stage timing + metadata log.  P10: each entry carries input/output.
    stage_log: List[Dict[str, Any]] = []
    # P10: DIAGNOSTICS BLOCK ──────────────────────────────────────────────────
    # Aggregate pipeline diagnostics: total latency, stage counts, errors.
    diagnostics: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# P10: RULE EXECUTION LOG REGISTRY  (persistent-backed)
# ═══════════════════════════════════════════════════════════════════════════════
# The in-memory dict is kept for same-session fast lookups and backward
# compatibility with existing tests.  Every write also fans out to the
# persistent RuleEventLogger so records survive restarts.
# ═══════════════════════════════════════════════════════════════════════════════

import collections as _collections

_RULE_LOG_MAX = 200
_rule_log_registry: Dict[str, List[Dict[str, Any]]] = {}
_rule_log_order: "collections.deque[str]" = _collections.deque(maxlen=_RULE_LOG_MAX)


def record_rule_execution(trace_id: str, rules: List[Dict[str, Any]]) -> None:
    """Store rule trace — writes to in-memory cache AND persistent rule_log.jsonl."""
    # ── In-memory (FIFO eviction, backward compat) ────────────────────────────
    if len(_rule_log_registry) >= _RULE_LOG_MAX:
        oldest = _rule_log_order[0]  # deque auto-evicts but dict needs cleanup
        _rule_log_registry.pop(oldest, None)
    _rule_log_registry[trace_id] = rules
    _rule_log_order.append(trace_id)
    # ── Persistent JSONL (hash-linked, cross-restart) ─────────────────────────
    _log_rule_batch(trace_id=trace_id, rules_trace=rules)


def get_rule_log(trace_id: str) -> Optional[List[Dict[str, Any]]]:
    """Return rule trace for the given trace_id.

    Fast path: in-memory dict (same session).
    Fallback: scan persistent rule_log.jsonl (cross-session reconstruction).
    """
    # Fast path — same Python process session
    cached = _rule_log_registry.get(trace_id)
    if cached is not None:
        return cached
    # Fallback — scan JSONL for cross-restart reconstruction
    try:
        from backend.governance.rule_event_log import get_rule_event_logger
        events = get_rule_event_logger().read_by_trace(trace_id=trace_id)
        if events:
            # Reconstruct the original rules_trace format expected by callers
            return [
                {
                    "rule":     e.get("rule_id", ""),
                    "category": e.get("rule_condition", ""),
                    "priority": e.get("priority", 0),
                    "outcome":  e.get("rule_result", "pass_through"),
                    "frozen":   e.get("frozen", True),
                }
                for e in events
            ]
    except Exception:
        pass
    return None


def get_recent_rule_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """Return the most recent rule logs (one entry per trace)."""
    recent = list(_rule_log_order)[-limit:]
    return [
        {
            "trace_id":    tid,
            "rules":       _rule_log_registry.get(tid, []),
            "rules_count": len(_rule_log_registry.get(tid, [])),
        }
        for tid in reversed(recent)
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION CONTROLLER
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionController:
    """
    Atomic decision pipeline controller.
    
    This is the SINGLE orchestrator for the 1-button system.
    All pipeline stages run through this controller.
    """
    
    def __init__(self):
        self._main_controller = None
        self._ops_hub = None
        self._model_version = "v1.0.0"
        self._weights_version = "default"
        
    def set_main_controller(self, controller) -> None:
        """Inject main controller for service dispatch."""
        self._main_controller = controller
        logger.info("MainController injected into DecisionController")
        
    def set_ops_hub(self, ops) -> None:
        """Inject OpsHub for monitoring."""
        self._ops_hub = ops
        logger.info("OpsHub injected into DecisionController")
        
    async def run_pipeline(self, request: DecisionRequest) -> DecisionResponse:
        """
        Execute full atomic decision pipeline.
        
        Stages:
          1. Input Normalize
          2. LLM Feature Extraction
          3. Merge
          4. SIMGR Scoring (AUTHORITY)
          5. Rule Engine
          6. Market Data Integration
          7. Explanation Layer
          
        Returns complete response or raises error (no partial state exposed).
        
        INVARIANTS (DETERMINISTIC SCORING HARDENING):
        - Weight version is immutable (from manifest, not ENV)
        - Validation mode is STRICT
        - No runtime ENV overrides permitted
        """
        trace_id = f"dec-{uuid.uuid4().hex[:12]}"
        correlation_id = f"corr-{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()
        stages_completed: List[str] = []
        stage_log_entries: List[Dict[str, Any]] = []   # P7: per-stage timing log
        llm_used = False
        rule_applied: List[Dict[str, Any]] = []        # P7: rule audit trace
        normalized_input: Dict[str, Any] = {}          # P7: for reasoning_path
        
        # ═══════════════════════════════════════════════════════════════
        # ARTIFACT TRACE: Initialize artifact chain for this decision
        # ═══════════════════════════════════════════════════════════════
        artifact_chain = ArtifactChain(trace_id=trace_id)
        prev_artifact: Optional[PipelineArtifact] = None

        # ═══════════════════════════════════════════════════════════════
        # P14: VERSION TRACE — resolve all four version axes immediately
        # so that even an early failure carries lineage metadata.
        # ═══════════════════════════════════════════════════════════════
        _version_bundle: VersionBundle = resolve_versions(
            model_version_hint=self._model_version,
        )
        logger.info(
            f"[{trace_id}] P14 VersionBundle: model={_version_bundle.model_version} "
            f"rule={_version_bundle.rule_version} "
            f"taxonomy={_version_bundle.taxonomy_version} "
            f"schema={_version_bundle.schema_version} "
            f"hash={_version_bundle.schema_hash[:16]}…"
        )

        # ═══════════════════════════════════════════════════════════════
        # INVARIANT CHECK: Ensure deterministic scoring (no ENV override)
        # ═══════════════════════════════════════════════════════════════
        manifest = get_manifest()
        logger.info(
            f"[{trace_id}] INVARIANT CHECK: weights_version={manifest.active_version} "
            f"mode={manifest.validation_mode}"
        )
        
        logger.info(f"[{trace_id}] Starting decision pipeline for user {request.user_id}")
        
        # ═══════════════════════════════════════════════════════════════
        # SETUP: Create and register execution context (SECURITY)
        # ═══════════════════════════════════════════════════════════════
        scoring_context = create_scoring_context(
            trace_id=trace_id,
            correlation_id=correlation_id,
            user_id=request.user_id,
            caller_module=__name__,
        )
        ExecutionContextRegistry.push(scoring_context, __name__)
        
        try:
            # ═══════════════════════════════════════════════════════════════
            # STAGE 1: Input Normalize  (+  Sub-score Decomposition)
            # ═══════════════════════════════════════════════════════════════
            _t1 = time.monotonic()
            normalized_input = self._normalize_input(request, trace_id=trace_id)

            # Extract and detach ScoringBreakdown before artifact serialisation
            # (ScoringBreakdown is a frozen dataclass — not JSON-serialisable as-is)
            scoring_breakdown: ScoringBreakdown = normalized_input.pop("_scoring_breakdown")

            # Build the artifact payload with the serialised breakdown included
            normalize_artifact_payload = {
                **normalized_input,
                "scoring_breakdown": scoring_breakdown.to_dict(),
            }
            prev_artifact = PipelineArtifact.create(
                trace_id=trace_id,
                stage_name=STAGE_INPUT_NORMALIZE,
                payload=normalize_artifact_payload,
                previous=prev_artifact,
            )
            artifact_chain.add(prev_artifact)
            append_record(prev_artifact.stage_hash)
            stages_completed.append("input_normalize")
            _dur1 = round((time.monotonic() - _t1) * 1000, 2)
            stage_log_entries.append({
                "stage": "input_normalize",
                "status": "ok",
                "duration_ms": _dur1,
                "input": {
                    "user_id": request.user_id,
                    "skills_raw_count": len(request.scoring_input.skills),
                    "interests_raw_count": len(request.scoring_input.personal_profile.interests),
                    "education": request.scoring_input.education.level,
                },
                "output": {
                    "skills_resolved": normalized_input.get("skills", [])[:5],
                    "interests_resolved": normalized_input.get("interests", [])[:5],
                    "education_level": normalized_input.get("education_level"),
                    "ability_score": normalized_input.get("ability_score"),
                    "taxonomy_applied": normalized_input.get("taxonomy_applied", False),
                },
            })
            logger.debug(f"[{trace_id}] Stage 1 complete: input_normalize")
            
            # ═══════════════════════════════════════════════════════════════
            # STAGE 2: LLM Feature Extraction (optional)
            # ═══════════════════════════════════════════════════════════════
            _t2 = time.monotonic()
            features = await self._extract_features(request, trace_id)
            if features.get("llm_extracted"):
                llm_used = True
            prev_artifact = PipelineArtifact.create(
                trace_id=trace_id,
                stage_name=STAGE_FEATURE_EXTRACTION,
                payload=features,
                previous=prev_artifact,
            )
            artifact_chain.add(prev_artifact)
            append_record(prev_artifact.stage_hash)
            stages_completed.append("feature_extraction")
            _dur2 = round((time.monotonic() - _t2) * 1000, 2)
            stage_log_entries.append({
                "stage": "feature_extraction",
                "status": "ok",
                "duration_ms": _dur2,
                "input": {
                    "skills": normalized_input.get("skills", [])[:3],
                    "interests": normalized_input.get("interests", [])[:3],
                },
                "output": {
                    "llm_extracted": features.get("llm_extracted", False),
                    "feature_keys": [k for k in features.keys() if not k.startswith("_")][:8],
                },
            })
            logger.debug(f"[{trace_id}] Stage 2 complete: feature_extraction")

            # ═══════════════════════════════════════════════════════════════
            # STAGE 3: KB Alignment
            # ═══════════════════════════════════════════════════════════════
            _t3 = time.monotonic()
            kb_alignment = self._align_with_knowledge_base(
                normalized_input, features, trace_id
            )
            prev_artifact = PipelineArtifact.create(
                trace_id=trace_id,
                stage_name=STAGE_KB_ALIGNMENT,
                payload=kb_alignment,
                previous=prev_artifact,
            )
            artifact_chain.add(prev_artifact)
            append_record(prev_artifact.stage_hash)
            stages_completed.append("kb_alignment")
            _dur3 = round((time.monotonic() - _t3) * 1000, 2)
            stage_log_entries.append({
                "stage": "kb_alignment",
                "status": "ok",
                "duration_ms": _dur3,
                "input": {
                    "skills": normalized_input.get("skills", [])[:3],
                    "interests": normalized_input.get("interests", [])[:3],
                },
                "output": {
                    "alignment_field_count": len(kb_alignment),
                    "alignment_keys": list(kb_alignment.keys())[:6],
                },
            })
            logger.debug(f"[{trace_id}] Stage 3 complete: kb_alignment")
            # P3-AUDIT: persist KB mapping to kb_mapping_log.jsonl
            _log_kb_mapping(
                trace_id=trace_id,
                kb_alignment_payload=kb_alignment,
                input_skills=normalized_input.get("skills", []),
                input_interests=normalized_input.get("interests", []),
            )

            # ═══════════════════════════════════════════════════════════════
            # STAGE 4: Merge
            # ═══════════════════════════════════════════════════════════════
            _t4 = time.monotonic()
            merged_profile = self._merge_data(normalized_input, features, kb_alignment)
            prev_artifact = PipelineArtifact.create(
                trace_id=trace_id,
                stage_name=STAGE_MERGE,
                payload=merged_profile,
                previous=prev_artifact,
            )
            artifact_chain.add(prev_artifact)
            append_record(prev_artifact.stage_hash)
            stages_completed.append("merge")
            _dur4 = round((time.monotonic() - _t4) * 1000, 2)
            stage_log_entries.append({
                "stage": "merge",
                "status": "ok",
                "duration_ms": _dur4,
                "input": {
                    "normalized_keys": list(normalized_input.keys())[:6],
                    "feature_keys": [k for k in features.keys() if not k.startswith("_")][:4],
                },
                "output": {
                    "merged_field_count": len(merged_profile),
                    "merged_keys": list(merged_profile.keys())[:8],
                },
            })
            logger.debug(f"[{trace_id}] Stage 4 complete: merge")

            # ═══════════════════════════════════════════════════════════════
            # STAGE 5: SIMGR Scoring (DETERMINISTIC - AUTHORITY)
            # ═══════════════════════════════════════════════════════════════
            _t5 = time.monotonic()
            rankings = await self._run_scoring(merged_profile, trace_id, scoring_breakdown=scoring_breakdown)
            # Convert rankings to serializable format for artifact
            rankings_payload = {
                "rankings": [r.model_dump() if hasattr(r, 'model_dump') else r.dict() for r in rankings],
                "count": len(rankings),
            }
            prev_artifact = PipelineArtifact.create(
                trace_id=trace_id,
                stage_name=STAGE_SIMGR_SCORING,
                payload=rankings_payload,
                previous=prev_artifact,
            )
            artifact_chain.add(prev_artifact)
            append_record(prev_artifact.stage_hash)
            stages_completed.append("simgr_scoring")
            _dur5 = round((time.monotonic() - _t5) * 1000, 2)
            stage_log_entries.append({
                "stage": "simgr_scoring",
                "status": "ok",
                "duration_ms": _dur5,
                "input": {
                    "ability_score": normalized_input.get("ability_score"),
                    "education_level": normalized_input.get("education_level"),
                    "skills_count": len(normalized_input.get("skills", [])),
                },
                "output": {
                    "careers_ranked": len(rankings),
                    "top_career": rankings[0].name if rankings else None,
                    "top_score": round(rankings[0].total_score, 4) if rankings else None,
                },
            })
            logger.debug(f"[{trace_id}] Stage 5 complete: simgr_scoring")

            # ═══════════════════════════════════════════════════════════════
            # STAGE 6: Drift Check (metadata-only – rankings UNCHANGED)
            # ═══════════════════════════════════════════════════════════════
            _t6 = time.monotonic()
            drift_result = self._run_drift_check(
                merged_profile, rankings_payload, trace_id
            )
            prev_artifact = PipelineArtifact.create(
                trace_id=trace_id,
                stage_name=STAGE_DRIFT_CHECK,
                payload=drift_result,
                previous=prev_artifact,
            )
            artifact_chain.add(prev_artifact)
            append_record(prev_artifact.stage_hash)
            stages_completed.append("drift_check")
            _dur6 = round((time.monotonic() - _t6) * 1000, 2)
            stage_log_entries.append({
                "stage": "drift_check",
                "status": "ok",
                "duration_ms": _dur6,
                "input": {
                    "top_career": rankings[0].name if rankings else None,
                    "rankings_count": len(rankings),
                },
                "output": {
                    "drift_detected": drift_result.get("drift_detected", False),
                    "drift_score": drift_result.get("drift_score"),
                },
            })
            logger.debug(f"[{trace_id}] Stage 6 complete: drift_check")
            # NOTE: rankings is NOT modified by drift_check (invariant enforced below)

            # ═══════════════════════════════════════════════════════════════
            # STAGE 7: Rule Engine
            # ═══════════════════════════════════════════════════════════════
            _t7 = time.monotonic()
            rule_engine_result = await self._apply_rules(rankings, merged_profile, trace_id)
            rankings = rule_engine_result.rankings          # always unchanged (frozen)
            rule_applied = rule_engine_result.rules_trace   # P7 audit trace
            rule_engine_payload = {
                "rankings_after_rules": [r.model_dump() if hasattr(r, 'model_dump') else r.dict() for r in rankings],
                "rules_applied": "FROZEN",  # Rule engine is frozen per architecture
                "rules_audited": len(rule_applied),
            }
            prev_artifact = PipelineArtifact.create(
                trace_id=trace_id,
                stage_name=STAGE_RULE_ENGINE,
                payload=rule_engine_payload,
                previous=prev_artifact,
            )
            artifact_chain.add(prev_artifact)
            append_record(prev_artifact.stage_hash)
            stages_completed.append("rule_engine")
            _dur7 = round((time.monotonic() - _t7) * 1000, 2)
            stage_log_entries.append({
                "stage": "rule_engine",
                "status": "frozen_pass_through",
                "duration_ms": _dur7,
                "input": {
                    "rankings_count": len(rankings),
                    "top_career": rankings[0].name if rankings else None,
                },
                "output": {
                    "rules_audited": len(rule_applied),
                    "frozen": True,
                    "rule_names_preview": [r["rule"] for r in rule_applied[:5]],
                },
            })
            # P10: persist rule trace to registry
            record_rule_execution(trace_id, rule_applied)
            logger.debug(f"[{trace_id}] Stage 7 complete: rule_engine")

            # ═══════════════════════════════════════════════════════════════
            # STAGE 8: Market Data Integration
            # ═══════════════════════════════════════════════════════════════
            market_insights: List[MarketInsight] = []
            _t8 = time.monotonic()
            if request.options and request.options.include_market_data:
                market_insights = await self._get_market_data(rankings[:5], trace_id)
            market_payload = {
                "insights": [m.model_dump() if hasattr(m, 'model_dump') else m.dict() for m in market_insights],
                "included": bool(request.options and request.options.include_market_data),
            }
            prev_artifact = PipelineArtifact.create(
                trace_id=trace_id,
                stage_name=STAGE_MARKET_DATA,
                payload=market_payload,
                previous=prev_artifact,
            )
            artifact_chain.add(prev_artifact)
            append_record(prev_artifact.stage_hash)
            stages_completed.append("market_data")
            _dur8 = round((time.monotonic() - _t8) * 1000, 2)
            stage_log_entries.append({
                "stage": "market_data",
                "status": "ok",
                "duration_ms": _dur8,
                "input": {
                    "careers_queried": [r.name for r in rankings[:5]],
                    "requested": bool(request.options and request.options.include_market_data),
                },
                "output": {
                    "insights_count": len(market_insights),
                    "demand_levels": [m.demand_level for m in market_insights[:5]],
                },
            })
            logger.debug(f"[{trace_id}] Stage 8 complete: market_data")

            # ═══════════════════════════════════════════════════════════════
            # STAGE 9: Explanation Layer
            # ═══════════════════════════════════════════════════════════════
            explanation: Optional[ExplanationResult] = None
            exp_state: Optional[_ExplanationState] = None
            _t9 = time.monotonic()
            if request.options and request.options.include_explanation:
                try:
                    # ── Timeout explanation generation to 8s (avoid stalling pipeline) ──
                    # If LLM is slow, skip and return deterministic fallback
                    exp_state = await asyncio.wait_for(
                        self._generate_explanation(
                            rankings[:3], merged_profile, features, trace_id,
                            scoring_breakdown=scoring_breakdown,
                        ),
                        timeout=8.0,
                    )
                    if exp_state:
                        explanation = exp_state.result
                        llm_used = True
                except asyncio.TimeoutError:
                    logger.warning(
                        f"[{trace_id}] Explanation generation timed out after 8s — skipping LLM"
                    )
                    exp_state = None
                    explanation = None
                except Exception as exp_err:
                    logger.warning(
                        f"[{trace_id}] Explanation generation failed: {exp_err} — continuing without explanation"
                    )
                    exp_state = None
                    explanation = None
            explanation_payload = {
                "explanation": explanation.model_dump() if explanation and hasattr(explanation, 'model_dump') else (explanation.dict() if explanation else None),
                "included": bool(request.options and request.options.include_explanation),
                "llm_used": llm_used,
                # ── Hash-chain metadata from ExplanationStorage.append_record() ──
                "record_hash":        exp_state.record_hash        if exp_state else "",
                "explanation_id":     exp_state.explanation_id     if exp_state else "",
                "stage3_input_hash":  exp_state.stage3_input_hash  if exp_state else "",
                "stage3_output_hash": exp_state.stage3_output_hash if exp_state else "",
            }
            prev_artifact = PipelineArtifact.create(
                trace_id=trace_id,
                stage_name=STAGE_EXPLANATION,
                payload=explanation_payload,
                previous=prev_artifact,
            )
            artifact_chain.add(prev_artifact)
            append_record(prev_artifact.stage_hash)
            stages_completed.append("explanation")
            _dur9 = round((time.monotonic() - _t9) * 1000, 2)
            stage_log_entries.append({
                "stage": "explanation",
                "status": "ok" if explanation else "skipped",
                "duration_ms": _dur9,
                "input": {
                    "top_careers": [r.name for r in rankings[:3]],
                    "llm_requested": bool(request.options and request.options.include_explanation),
                },
                "output": {
                    "confidence": explanation.confidence if explanation else None,
                    "summary_len": len(explanation.summary) if explanation else None,
                    "llm_used": llm_used,
                    "explanation_id": exp_state.explanation_id if exp_state else None,
                },
            })
            logger.debug(f"[{trace_id}] Stage 9 complete: explanation")
            
            # ═══════════════════════════════════════════════════════════════
            # BUILD RESPONSE
            # ═══════════════════════════════════════════════════════════════
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            top_career = rankings[0] if rankings else None

            # ─ P7: Build reasoning_path ────────────────────────────────────────────
            _ed = normalized_input.get("education_level", "Unknown")
            _ns = len(normalized_input.get("skills", []))
            _ni = len(normalized_input.get("interests", []))
            reasoning_path: List[str] = [
                f"[1] INPUT_NORMALIZE: {_ns} skills, {_ni} interests, education={_ed}, user_id={request.user_id}",
                f"[2] FEATURE_EXTRACTION: llm_used={llm_used}",
                f"[3] KB_ALIGNMENT: profile aligned with knowledge base",
                f"[4] MERGE: normalized profile merged with features + KB alignment",
                f"[5] SIMGR_SCORING: {len(rankings)} careers ranked; top='{top_career.name if top_career else 'N/A'}' score={(top_career.total_score if top_career else 0):.4f}",
                f"[6] DRIFT_CHECK: drift_detected={drift_result.get('drift_detected', False)}",
                f"[7] RULE_ENGINE: FROZEN pass-through; {len(rule_applied)} rules audited",
                f"[8] MARKET_DATA: {len(market_insights)} insights fetched",
                f"[9] EXPLANATION: {'generated confidence={:.2f}'.format(explanation.confidence) if explanation else 'skipped (no_main_controller or not_requested)'}",
            ]
            if explanation and explanation.reasoning_chain:
                for step in explanation.reasoning_chain:
                    reasoning_path.append(f"    └─ LLM_REASON: {step}")

            # ─ P10: Build diagnostics block ─────────────────────────────────────
            _stage_errors = [
                {"stage": s["stage"], "error": s.get("error")}
                for s in stage_log_entries
                if s.get("status") == "error" and s.get("error")
            ]
            diagnostics: Dict[str, Any] = {
                "total_latency_ms": duration_ms,
                "stage_count": len(stage_log_entries),
                "stage_passed": sum(
                    1 for s in stage_log_entries
                    if s.get("status") in ("ok", "frozen_pass_through")
                ),
                "stage_skipped": sum(
                    1 for s in stage_log_entries
                    if s.get("status") == "skipped"
                ),
                "stage_failed": sum(
                    1 for s in stage_log_entries
                    if s.get("status") == "error"
                ),
                "slowest_stage": max(
                    stage_log_entries,
                    key=lambda s: s.get("duration_ms", 0),
                    default={"stage": "n/a", "duration_ms": 0},
                ).get("stage"),
                "errors": _stage_errors,
                "llm_used": llm_used,
                "rules_audited": len(rule_applied),
            }
            
            # Create final response artifact
            response_payload = {
                "status": "SUCCESS",
                "top_career": top_career.model_dump() if top_career and hasattr(top_career, 'model_dump') else (top_career.dict() if top_career else None),
                "ranking_count": len(rankings),
                "duration_ms": duration_ms,
            }
            prev_artifact = PipelineArtifact.create(
                trace_id=trace_id,
                stage_name=STAGE_RESPONSE,
                payload=response_payload,
                previous=prev_artifact,
            )
            artifact_chain.add(prev_artifact)
            append_record(prev_artifact.stage_hash)
            
            # Compute cryptographic root of artifact chain
            chain_root = artifact_chain.compute_chain_root()
            logger.info(f"[{trace_id}] Artifact chain root: {chain_root[:16]}...")

            # ═══════════════════════════════════════════════════════════════
            # P14: LOG ARTIFACT CHAIN — persist version trace to JSONL
            # Must run BEFORE the audit hash-chain record so that the
            # version fingerprint is stored even if scoring validation fails.
            # ═══════════════════════════════════════════════════════════════
            log_artifact_chain(
                trace_id            = trace_id,
                versions            = _version_bundle,
                artifact_chain_root = chain_root,
                stage_count         = len(artifact_chain.artifacts),
            )

            # ═══════════════════════════════════════════════════════════════
            # STAGE 6: DECISION AUDIT HASH-CHAIN RECORD
            # Single mandatory record per pipeline decision capturing all
            # semantic fields that the per-stage artifact hashes embed only
            # implicitly.  Written BEFORE scoring consistency gate so that
            # even a scoring error is preceded by a hash-chain entry.
            # ═══════════════════════════════════════════════════════════════
            _input_hash_stage6 = (
                artifact_chain.artifacts[0].stage_hash
                if artifact_chain.artifacts
                else compute_stage_hash({"trace_id": trace_id})
            )
            _append_decision_audit_record(
                trace_id         = trace_id,
                input_hash       = _input_hash_stage6,
                breakdown_hash   = compute_stage_hash(scoring_breakdown.to_dict()),
                explanation_hash = (
                    exp_state.explanation_hash
                    if exp_state and exp_state.explanation_hash
                    else _NO_EXPLANATION_SENTINEL
                ),
                final_score      = scoring_breakdown.final_score,
                weights_version  = self._weights_version or "default",
            )

            # ═══════════════════════════════════════════════════════════════
            # SCORING CONSISTENCY GATE — must pass before response is built
            # Raises InconsistentScoringError if any invariant is violated.
            # Rule 4 is checked only when explanation contributions are available.
            # ═══════════════════════════════════════════════════════════════
            validate_scoring_consistency(
                scoring_breakdown,
                weight_version=self._weights_version,
                explanation_contributions=(
                    exp_state.contributions
                    if exp_state and exp_state.contributions
                    else None
                ),
                trace_id=trace_id,
            )

            response = DecisionResponse(
                trace_id=trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                status="SUCCESS",
                rankings=rankings,
                top_career=top_career,
                explanation=explanation,  # ExplanationResult (unwrapped from _ExplanationState)
                market_insights=market_insights,
                meta=DecisionMeta(
                    correlation_id=correlation_id,
                    pipeline_duration_ms=duration_ms,
                    model_version=_version_bundle.model_version,
                    weights_version=self._weights_version,
                    llm_used=llm_used,
                    stages_completed=stages_completed,
                    artifact_chain=[a.to_dict() for a in artifact_chain.artifacts],
                    # ── P14: version trace fields ──
                    rule_version=_version_bundle.rule_version,
                    taxonomy_version=_version_bundle.taxonomy_version,
                    schema_version=_version_bundle.schema_version,
                    schema_hash=_version_bundle.schema_hash,
                ),
                artifact_hash_chain_root=chain_root,
                # Extended scoring breakdown: ml_score, rule_score, penalty,
                # final_score, result_hash + sub-score decomposition.
                scoring_breakdown=_ScoringService.compute_decision_breakdown(
                    scoring_input=scoring_breakdown,
                    top_career=top_career,
                    rule_result=None,  # rule engine is FROZEN
                    trace_id=trace_id,
                ),
                rule_applied=rule_applied,
                reasoning_path=reasoning_path,
                stage_log=stage_log_entries,
                diagnostics=diagnostics,
            )
            
            # Log snapshot
            self._log_snapshot(trace_id, request, response)

            # ── EVAL-TRACK: log prediction to rolling evaluator ────────────
            # probability = top career score normalised to [0, 1] (max 100)
            try:
                _top_score_raw = top_career.total_score if top_career else 0.0
                _eval_prob     = float(min(max(_top_score_raw / 100.0, 0.0), 1.0))
                _exp_conf      = (explanation.confidence
                                  if explanation and hasattr(explanation, "confidence")
                                  else None)
                evaluator = get_rolling_evaluator()
                evaluator.log_prediction(
                    trace_id=trace_id,
                    predicted_label=top_career.name if top_career else "_none",
                    probability=_eval_prob,
                    model_version=self._model_version,
                    explanation_confidence=_exp_conf,
                )
                # Persist evaluation snapshot every 10 predictions
                if evaluator._samples and len(evaluator._samples) % 10 == 0:
                    snap = evaluator.snapshot()
                    _log_eval_snapshot(snap)
                    if snap.active_alerts:
                        for alert in snap.active_alerts:
                            logger.warning(
                                "[EVAL-ALERT] %s: %s",
                                alert.alert_type, alert.message,
                            )
            except Exception as _eval_exc:
                logger.debug("[%s] eval tracking non-fatal: %s", trace_id, _eval_exc)

            logger.info(f"[{trace_id}] Pipeline completed in {duration_ms}ms")
            return response

        except TaxonomyValidationError:
            # P8: let taxonomy errors bubble up as HTTP 400 — do NOT wrap in
            # a success-looking DecisionResponse.
            raise
            
        except Exception as e:
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.error(f"[{trace_id}] Pipeline failed: {e}")
            
            # Compute partial chain root if any artifacts were collected
            partial_chain_root = None
            if artifact_chain.artifacts:
                partial_chain_root = artifact_chain.compute_chain_root()
                logger.info(f"[{trace_id}] Partial artifact chain root: {partial_chain_root[:16]}...")
            
            # Return error response with partial artifact chain
            return DecisionResponse(
                trace_id=trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                status="ERROR",
                rankings=[],
                top_career=None,
                explanation=None,
                market_insights=[],
                meta=DecisionMeta(
                    correlation_id=correlation_id,
                    pipeline_duration_ms=duration_ms,
                    model_version=_version_bundle.model_version,
                    weights_version=self._weights_version,
                    llm_used=llm_used,
                    stages_completed=stages_completed,
                    artifact_chain=[a.to_dict() for a in artifact_chain.artifacts],
                    # ── P14: version trace fields ──
                    rule_version=_version_bundle.rule_version,
                    taxonomy_version=_version_bundle.taxonomy_version,
                    schema_version=_version_bundle.schema_version,
                    schema_hash=_version_bundle.schema_hash,
                ),
                artifact_hash_chain_root=partial_chain_root,
                rule_applied=[],
                reasoning_path=[
                    f"[ERROR] Pipeline failed at stage '"
                    f"{stages_completed[-1] if stages_completed else 'init'}': {e}"
                ],
                stage_log=stage_log_entries,
            )
        
        finally:
            # ═══════════════════════════════════════════════════════════════
            # CLEANUP: Always pop execution context
            # ═══════════════════════════════════════════════════════════════
            ExecutionContextRegistry.pop()
            logger.debug(f"[{trace_id}] Execution context cleared")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE STAGE METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _normalize_input(self, request: "DecisionRequest", *, trace_id: str = "-") -> Dict[str, Any]:
        """
        Stage 1: Validate and normalise scoring input.

        STRICT ENFORCEMENT — NO DEFAULTS, NO FALLBACKS.

        This method is the RUNTIME validation gate.  It must be the FIRST
        operation inside ``run_pipeline`` before any other stage executes.

        Validation order (fail-fast):
          1. ``validate_scoring_components()`` — presence matrix logged,
             ``MissingComponentError`` raised if ANY component absent.
          2. Skill list non-empty guard (redundant but explicit).
          3. Interests list non-empty guard.

        All values are taken EXCLUSIVELY from ``request.scoring_input``.
        There is NO derivation of ``ability_score`` or ``confidence_score``
        from optional features.  There is NO default ``education_level``.
        Every field must have been explicitly supplied by the caller.

        Returns a flat dict consumed by all downstream pipeline stages.

        Raises
        ------
        MissingComponentError
            If any of the six mandatory components (personal_profile,
            experience, goals, skills, education, preferences) is absent or
            empty.  Raised DETERMINISTICALLY — scoring cannot proceed.
        InputValidationError
            If skill or interest lists are empty after normalisation.
        """
        # ── GATE 1: mandatory component presence ─────────────────────────────
        # No try/except — MissingComponentError must propagate; it blocks scoring.
        validate_scoring_components(request.scoring_input, trace_id=trace_id)

        si = request.scoring_input

        # ── Normalise skills ──────────────────────────────────────────────────
        skills = [s.strip().lower() for s in si.skills if s and s.strip()]
        if not skills:
            raise InputValidationError(
                "scoring_input.skills must contain at least one non-empty entry."
            )

        # ── Normalise interests ───────────────────────────────────────────────
        interests = [
            i.strip().lower()
            for i in si.personal_profile.interests
            if i and i.strip()
        ]
        if not interests:
            raise InputValidationError(
                "scoring_input.personal_profile.interests must contain at least "
                "one non-empty entry."
            )

        # ── Build normalised profile dict (single source of truth) ───────────
        normalized: Dict[str, Any] = {
            "user_id": request.user_id,
            # core scoring fields
            "skills": skills,
            "interests": interests,
            "education_level": si.education.level,
            "ability_score": si.personal_profile.ability_score,
            "confidence_score": si.personal_profile.confidence_score,
            # extended components (for downstream stages + audit)
            "experience": si.experience.model_dump(),
            "goals": si.goals.model_dump(),
            "preferences": si.preferences.model_dump(),
            "education": si.education.model_dump(),
        }

        # ── P8 GATE 2: Taxonomy normalize + validate ─────────────────────────
        # All three input categories go through TaxonomyGate before scoring.
        # Raises TaxonomyValidationError (→ HTTP 400) if any list resolves empty.
        taxonomy_result = TaxonomyGate.normalize_and_validate(
            skills=skills,
            interests=interests,
            education_level=si.education.level,
            trace_id=trace_id,
        )
        # Re-apply taxonomy-normalized values (canonical labels, deduplicated)
        normalized["skills"] = taxonomy_result["skills"]
        normalized["interests"] = taxonomy_result["interests"]
        normalized["education_level"] = taxonomy_result["education_level"]
        normalized["taxonomy_applied"] = True

        # ── GATE 3: sub-score decomposition ──────────────────────────────────
        # Compute the fully-decomposed ScoringBreakdown from the validated
        # ScoringInput.  This runs BEFORE any downstream stage so the
        # breakdown is available to all pipeline stages and the final response.
        # assemble_breakdown() is deterministic and raises ValueError only if
        # weights are invalid (default weights are always valid).
        breakdown: ScoringBreakdown = assemble_breakdown(
            request.scoring_input, trace_id=trace_id
        )
        normalized["_scoring_breakdown"] = breakdown

        logger.info(
            "[%s] STAGE_1_NORMALIZE: skills=%d interests=%d "
            "education_level=%s ability=%.3f confidence=%.3f "
            "experience_years=%d goals=%d preferences_domains=%d "
            "final_score=%.2f",
            trace_id,
            len(skills),
            len(interests),
            normalized["education_level"],
            normalized["ability_score"],
            normalized["confidence_score"],
            si.experience.years,
            len(si.goals.career_aspirations),
            len(si.preferences.preferred_domains),
            breakdown.final_score,
        )
        return normalized
    
    async def _extract_features(
        self, request: DecisionRequest, trace_id: str
    ) -> Dict[str, Any]:
        """Stage 2: Extract features (use LLM if needed)."""
        features: Dict[str, Any] = {"llm_extracted": False}
        
        if request.features:
            for field, value in request.features.dict(exclude_none=True).items():
                features[field] = value
        
        # If missing critical features, could use LLM extraction
        # For now, use provided features only
        return features
    
    def _run_drift_check(
        self,
        merged_profile: Dict[str, Any],
        rankings_payload: Dict[str, Any],
        trace_id: str,
    ) -> Dict[str, Any]:
        """
        Stage 6: Runtime drift detection (metadata-only).

        Delegates to RetrainingMonitor.evaluate() and wraps the result in the
        required artifact schema.  This stage MUST NOT alter ``rankings`` or
        any variable that feeds downstream scoring.

        Invariants enforced here:
          - rankings_payload is passed by value (never mutated)
          - return value contains only metadata fields
          - drift_detected=True triggers a WARNING log but does NOT block
            the pipeline or modify the response rankings

        Args:
            merged_profile:   Stage 4 output (merged input + features + kb_alignment).
            rankings_payload: Stage 5 output dict with ``{rankings, count}``.
            trace_id:         Decision trace ID for log correlation.

        Returns:
            Artifact payload dict::

                {
                    "drift_score":    float,   # computed drift metric [0, 1]
                    "threshold":      float,   # configured threshold
                    "drift_detected": bool,    # True when drift_score > threshold
                    "feature_count":  int,     # features evaluated
                    "top_score":      float,   # top ranking score (context only)
                    "method":         str,     # algorithm name
                }
        """
        # Build a flat feature vector from the merged profile
        feature_vector: Dict[str, float] = {}
        raw_features = merged_profile.get("features", {})
        for key, value in raw_features.items():
            if isinstance(value, (int, float)):
                # Normalise from [0, 10] scale if needed
                feature_vector[key] = float(value) / 10.0 if float(value) > 1.0 else float(value)

        # Also include ability_score / confidence_score if present
        for scalar_key in ("ability_score", "confidence_score"):
            val = merged_profile.get(scalar_key)
            if isinstance(val, (int, float)):
                feature_vector[scalar_key] = float(val)

        try:
            # ── Primary: RetrainingMonitor (weighted-MAD drift score) ──────
            monitor = RetrainingMonitor(RetrainingConfig())
            drift_result = monitor.evaluate(
                feature_vector=feature_vector,
                score_output=rankings_payload,
            )

            # ── Secondary: DistributionDriftDetector (JSD + adaptive thr) ─
            #   Feed feature scores as feature_drift and prediction scores as
            #   prediction_drift so both drift types are tracked historically.
            dist_detector: DistributionDriftDetector = get_drift_detector()

            # Feature drift — record each feature dimension
            feature_drift_metrics = dist_detector.record_scores(
                feature_vector, drift_type=DRIFT_TYPE_FEATURE
            )

            # Prediction drift — top score from rankings
            top_score: float = drift_result.get("top_score", 0.0)
            pred_drift_metrics = []
            if rankings_payload.get("rankings"):
                pred_drift_metric = dist_detector.record_score(
                    "prediction_score", top_score, drift_type=DRIFT_TYPE_PREDICTION
                )
                if pred_drift_metric and pred_drift_metric.is_drift:
                    pred_drift_metrics = [pred_drift_metric]

            # Aggregate distribution-level drift info
            all_dist_drifts = feature_drift_metrics + pred_drift_metrics
            dist_drift_detected = len(all_dist_drifts) > 0
            dist_drift_types = list({m.drift_type for m in all_dist_drifts}) if all_dist_drifts else []
            dist_jsd_max = max((m.js_divergence for m in all_dist_drifts), default=0.0)

            # Merge: drift is detected if EITHER monitor triggers
            combined_drift_detected = (
                drift_result.get("drift_detected", False) or dist_drift_detected
            )
            drift_result["drift_detected"]       = combined_drift_detected
            drift_result["dist_drift_detected"]  = dist_drift_detected
            drift_result["dist_drift_types"]     = dist_drift_types
            drift_result["max_jsd"]              = round(dist_jsd_max, 6)
            drift_result["drift_classifications"] = (
                dist_drift_types or (
                    [DRIFT_TYPE_FEATURE] if drift_result.get("drift_detected") else []
                )
            )

            # ── Persistent event logging ─────────────────────────────────
            # Always log; triggered=True when value > threshold
            _drift_log_kwargs = dict(
                decision_trace_id=trace_id,
                model_version=getattr(self, "_weights_version", "unknown"),
            )
            # Log primary MAD score as feature_drift entry
            try:
                log_drift_event(
                    drift_type=DRIFT_TYPE_FEATURE,
                    divergence_value=drift_result.get("drift_score", 0.0),
                    threshold=drift_result.get("threshold", 0.0),
                    divergence_metric=METRIC_PSI,
                    **_drift_log_kwargs,
                )
            except Exception as _delog_exc:
                logger.debug("[%s] drift event log write skipped: %s", trace_id, _delog_exc)

            # Log each distribution-level drift metric that triggered
            for _dm in all_dist_drifts:
                try:
                    log_drift_event(
                        drift_type=_dm.drift_type,
                        divergence_value=_dm.js_divergence,
                        threshold=_dm.adaptive_threshold or 0.0,
                        divergence_metric=METRIC_JSD,
                        feature_name=_dm.metric_name,
                        **_drift_log_kwargs,
                    )
                except Exception as _delog_exc:
                    logger.debug("[%s] drift dist event log write skipped: %s", trace_id, _delog_exc)

        except Exception as exc:
            # Drift check failure must NEVER break the pipeline
            logger.warning(
                f"[{trace_id}] DRIFT_CHECK: evaluation error (non-fatal): {exc}"
            )
            drift_result = {
                "drift_score": 0.0,
                "threshold": RetrainingConfig().max_drift_threshold,
                "drift_detected": False,
                "feature_count": len(feature_vector),
                "top_score": 0.0,
                "method": "unavailable",
                "dist_drift_detected": False,
                "dist_drift_types": [],
                "max_jsd": 0.0,
                "drift_classifications": [],
                "error": str(exc),
            }

        if drift_result.get("drift_detected"):
            logger.warning(
                f"[{trace_id}] DRIFT_CHECK: drift DETECTED "
                f"score={drift_result['drift_score']} "
                f"threshold={drift_result['threshold']}. "
                f"Rankings unchanged — retraining evaluation recommended."
            )
        else:
            logger.info(
                f"[{trace_id}] DRIFT_CHECK: no drift "
                f"score={drift_result.get('drift_score', 0.0)} "
                f"threshold={drift_result.get('threshold')}"
            )

        return drift_result

    def _align_with_knowledge_base(
        self,
        normalized: Dict[str, Any],
        features: Dict[str, Any],
        trace_id: str,
    ) -> Dict[str, Any]:
        """
        Stage 3: KB Alignment.

        Independently validates and annotates extracted features against the
        knowledge base before they enter the merge stage.  This stage is the
        explicit boundary between raw LLM-extracted features and the
        KB-validated representation that feeds scoring.

        Responsibilities:
          - Verify each feature key is a recognised KB concept.
          - Annotate features with the KB reference version they were
            aligned against (for audit / lineage).
          - Flag any feature that has no KB mapping so downstream stages
            can surface the gap without failing silently.
          - Produce a self-contained artifact payload that is independent
            of the merge payload.

        Args:
            normalized: Output of Stage 1 (normalised input dict).
            features:   Output of Stage 2 (feature extraction dict).
            trace_id:   Decision trace ID propagated from run_pipeline.

        Returns:
            Dict with keys:
              decision_trace_id     — echoed trace ID for artifact integrity
              stage_name            — always "kb_alignment"
              kb_reference_version  — version string of the active KB snapshot
              aligned_features      — feature dict annotated with kb_mapped flag
              unrecognised_keys     — list of feature keys not found in KB
              skills_kb_matches     — KB career-domain tags inferred from skills
              interests_kb_matches  — KB career-domain tags inferred from interests
        """
        # ── KB reference version ─────────────────────────────────────────────
        # In production this would be read from a versioned KB snapshot file.
        # The constant provides a stable, auditable reference for every artifact.
        KB_REFERENCE_VERSION = "kb-v1.0-20260222"

        # ── Recognised feature keys (mirrors ScoringFormula.COMPONENTS) ──────
        RECOGNISED_FEATURE_KEYS = {
            "math_score", "logic_score", "physics_score", "literature_score",
            "history_score", "geography_score", "biology_score",
            "chemistry_score", "economics_score", "creativity_score",
            "interest_tech", "interest_science", "interest_arts",
            "interest_social", "llm_extracted",
        }

        # ── Domain tag maps (lightweight static KB) ──────────────────────────
        SKILL_DOMAIN_MAP: Dict[str, List[str]] = {
            "python":      ["software_engineering", "data_science"],
            "math":        ["engineering", "finance", "data_science"],
            "writing":     ["journalism", "law", "education"],
            "biology":     ["medicine", "biotechnology", "research"],
            "economics":   ["finance", "policy", "business"],
            "design":      ["ux_design", "architecture", "arts"],
            "teaching":    ["education", "training"],
            "research":    ["academia", "science", "engineering"],
            "leadership":  ["management", "policy", "consulting"],
            "statistics":  ["data_science", "finance", "research"],
        }
        INTEREST_DOMAIN_MAP: Dict[str, List[str]] = {
            "technology":  ["software_engineering", "data_science", "cybersecurity"],
            "science":     ["research", "medicine", "engineering"],
            "arts":        ["design", "media", "education"],
            "social":      ["policy", "education", "ngo"],
            "finance":     ["banking", "investment", "consulting"],
            "health":      ["medicine", "public_health", "biotechnology"],
            "environment": ["sustainability", "ecology", "policy"],
        }

        # ── Annotate features ─────────────────────────────────────────────────
        raw_features = {k: v for k, v in features.items() if k != "llm_extracted"}
        aligned_features: Dict[str, Any] = {}
        unrecognised_keys: List[str] = []

        for key, value in raw_features.items():
            is_known = key in RECOGNISED_FEATURE_KEYS
            aligned_features[key] = {
                "value": value,
                "kb_mapped": is_known,
                "kb_reference_version": KB_REFERENCE_VERSION,
            }
            if not is_known:
                unrecognised_keys.append(key)

        # ── Skills → KB domain tags ───────────────────────────────────────────
        skills_kb_matches: Dict[str, List[str]] = {}
        for skill in normalized.get("skills", []):
            skill_lower = skill.lower()
            for keyword, domains in SKILL_DOMAIN_MAP.items():
                if keyword in skill_lower:
                    skills_kb_matches[skill] = domains
                    break
            else:
                skills_kb_matches[skill] = []

        # ── Interests → KB domain tags ────────────────────────────────────────
        interests_kb_matches: Dict[str, List[str]] = {}
        for interest in normalized.get("interests", []):
            interest_lower = interest.lower()
            for keyword, domains in INTEREST_DOMAIN_MAP.items():
                if keyword in interest_lower:
                    interests_kb_matches[interest] = domains
                    break
            else:
                interests_kb_matches[interest] = []

        payload = {
            "decision_trace_id": trace_id,
            "stage_name": "kb_alignment",
            "kb_reference_version": KB_REFERENCE_VERSION,
            "aligned_features": aligned_features,
            "unrecognised_keys": unrecognised_keys,
            "skills_kb_matches": skills_kb_matches,
            "interests_kb_matches": interests_kb_matches,
        }

        if unrecognised_keys:
            logger.warning(
                f"[{trace_id}] KB_ALIGNMENT: {len(unrecognised_keys)} unrecognised "
                f"feature key(s): {unrecognised_keys}"
            )
        logger.info(
            f"[{trace_id}] KB_ALIGNMENT: aligned {len(aligned_features)} feature(s) "
            f"against {KB_REFERENCE_VERSION}"
        )
        return payload

    def _merge_data(
        self,
        normalized: Dict[str, Any],
        features: Dict[str, Any],
        kb_alignment: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Stage 4: Merge normalised input, extracted features, and KB alignment
        into a unified profile consumed by SIMGR Scoring.

        The kb_alignment output is attached under the ``kb_alignment`` key so
        that every downstream stage—including the explanation layer—can access
        the KB-validated feature set and reference version without re-running
        alignment.
        """
        return {
            **normalized,
            "features": {k: v for k, v in features.items() if k != "llm_extracted"},
            "kb_alignment": kb_alignment,
        }
    
    async def _run_scoring(
        self, profile: Dict[str, Any], trace_id: str,
        scoring_breakdown: Optional["ScoringBreakdown"] = None,
    ) -> List[CareerResult]:
        """
        Stage 4: SIMGR Scoring (DETERMINISTIC - AUTHORITY).
        
        This uses the core scoring engine which is the FINAL AUTHORITY.
        LLM cannot override these scores.
        """
        if self._main_controller:
            try:
                result = await self._main_controller.dispatch(
                    service="scoring",
                    action="rank",
                    payload={
                        "user_profile": profile,
                        "careers": self._get_career_database(),
                    },
                    context={"trace_id": trace_id},
                )
                
                # Update weights version from result
                if "_validation" in result:
                    self._weights_version = result["_validation"].get("config_version", "default")
                
                # Convert to CareerResult objects
                rankings = []
                for career in result.get("ranked_careers", []):
                    rankings.append(CareerResult(
                        name=career.get("name", "Unknown"),
                        domain=career.get("domain", "general"),
                        total_score=career.get("total_score", 0),
                        skill_score=career.get("skill_score", 0),
                        interest_score=career.get("interest_score", 0),
                        market_score=career.get("market_score", 0.5),
                        growth_potential=career.get("growth_potential", 0.5),
                        ai_relevance=career.get("ai_relevance", 0.5),
                    ))
                return rankings
                
            except Exception as e:
                logger.warning(f"[{trace_id}] Scoring dispatch failed: {e}, using direct SIMGR fallback")
        
        # Direct SIMGR scoring (no MainController needed)
        logger.info("[%s] MainController unavailable — running SIMGR scoring directly via ScoringService", trace_id)
        try:
            result = _ScoringService.rank(
                user_profile=profile,
                careers=self._get_career_database(),
            )
            ranked_careers = result.get("ranked_careers", [])
            rankings = []
            # Base score from sub_scorer (deterministic, already computed in Stage 1).
            # sub_scorer uses [0, 100] range; RankingEngine uses [0, 1] range.
            # Normalise to [0, 1] so the frontend's *100 display gives correct %.
            base_score = (scoring_breakdown.final_score / 100.0) if scoring_breakdown else 0.0
            all_zero = all(c.get("total_score", 0.0) == 0.0 for c in ranked_careers)
            for i, career in enumerate(ranked_careers):
                # When engine returns 0.0 for all, distribute sub_scorer scores by rank
                if all_zero and base_score > 0:
                    decay = 1.0 / (i + 1)  # rank decay: 1st=100%, 2nd=50%, ...
                    total = round(min(base_score * decay, 1.0), 4)
                    # contributions are also in [0, 100] — normalise to [0, 1]
                    skill_s = round(min((scoring_breakdown.contributions.get("skill", 0.0) / 100.0 if scoring_breakdown else 0.0) * decay, 1.0), 4)
                    interest_s = round(min((scoring_breakdown.contributions.get("goal_alignment", 0.0) / 100.0 if scoring_breakdown else 0.0) * decay, 1.0), 4)
                else:
                    total = min(career.get("total_score", 0.0), 1.0)
                    skill_s = career.get("skill_score", 0.0)
                    interest_s = career.get("interest_score", 0.0)
                rankings.append(CareerResult(
                    name=career.get("name", "Unknown"),
                    domain=career.get("domain", "general"),
                    total_score=total,
                    skill_score=skill_s,
                    interest_score=interest_s,
                    market_score=career.get("market_score", 0.5),
                    growth_potential=career.get("growth_potential", 0.5),
                    ai_relevance=career.get("ai_relevance", 0.5),
                ))
            if rankings:
                return rankings
        except Exception as exc:
            logger.error("[%s] Direct SIMGR scoring failed: %s", trace_id, exc)
        
        return self._fallback_scoring(profile)
    
    async def _apply_rules(
        self,
        rankings: List[CareerResult],
        profile: Dict[str, Any],
        trace_id: str,
    ) -> _RuleEngineResult:
        """
        Stage 7: Rule Engine (EXPLICITLY FROZEN)
        
        ARCHITECTURE DECISION (REMEDIATION):
        Rule Engine is INTENTIONALLY FROZEN to preserve SIMGR authority.
        
        RATIONALE:
        1. SIMGR scoring is the DETERMINISTIC AUTHORITY for career rankings
        2. Rule-based adjustments could invalidate baseline reproducibility
        3. Any post-scoring modifications break audit trail consistency
        4. Business rules should be encoded in SIMGR weights, not as post-hoc adjustments
        
        POLICY:
        - This stage MUST return rankings UNMODIFIED
        - Re-ranking is PROHIBITED
        - Score adjustments are PROHIBITED
        - Filtering is PROHIBITED

        P7 TRACE:
        Rule engine execution is logged AND a per-rule audit trace is returned.
        """
        from backend.rule_engine.rule_service import rule_service  # noqa: PLC0415

        # ── Evaluate profile to build audit trace (does NOT change rankings) ─
        rules_trace: List[Dict[str, Any]] = []
        try:
            eval_result = rule_service.evaluate_profile(dict(profile))
            flagged: List[str] = eval_result.get("flags", [])
            warnings: List[str] = eval_result.get("warnings", [])
            # Retrieve the full rule list for audit completeness
            rule_list = rule_service.list_rules(page_size=100).get("rules", [])
            for r in rule_list:
                rules_trace.append({
                    "rule": r["name"],
                    "category": r["category"],
                    "priority": r.get("priority", 0),
                    "outcome": "flagged" if r["name"] in flagged else "pass_through",
                    "frozen": True,  # engine frozen — no ranking change
                })
        except Exception as exc:
            logger.warning("[%s] Rule trace collection failed: %s", trace_id, exc)
            warnings = []
            rules_trace = [{"rule": "_trace_unavailable", "outcome": "error", "frozen": True}]

        logger.info(
            "[%s] Stage 7 RULE_ENGINE: FROZEN (pass-through). "
            "Rankings preserved: %d careers. Rules audited: %d",
            trace_id, len(rankings), len(rules_trace),
        )

        return _RuleEngineResult(rankings=rankings, rules_trace=rules_trace)
    
    async def _get_market_data(
        self, top_careers: List[CareerResult], trace_id: str
    ) -> List[MarketInsight]:
        """Stage 6: Get market data for top careers."""
        insights = []
        
        if self._main_controller:
            try:
                for career in top_careers:
                    result = await self._main_controller.dispatch(
                        service="market",
                        action="signal",
                        payload={"career_name": career.name},
                        context={"trace_id": trace_id},
                    )
                    
                    if result.get("status") == "ok":
                        insights.append(MarketInsight(
                            career_name=career.name,
                            demand_level=result.get("demand", "MEDIUM"),
                            salary_range=result.get("salary_range", {"min": 0, "max": 0, "currency": "VND"}),
                            growth_rate=result.get("growth_rate", 0.05),
                            competition_level=result.get("competition", "MEDIUM"),
                        ))
            except Exception as e:
                logger.warning(f"[{trace_id}] Market data fetch failed: {e}")
        
        # Fallback: Generate placeholder insights
        if not insights:
            for career in top_careers:
                insights.append(MarketInsight(
                    career_name=career.name,
                    demand_level="MEDIUM",
                    salary_range={"min": 15000000, "max": 35000000, "currency": "VND"},
                    growth_rate=0.08,
                    competition_level="MEDIUM",
                ))
        
        return insights
    
    async def _generate_explanation(
        self,
        top_careers: List[CareerResult],
        profile: Dict[str, Any],
        features: Dict[str, Any],
        trace_id: str,
        scoring_breakdown: Optional["ScoringBreakdown"] = None,
    ) -> Optional[_ExplanationState]:
        """
        Stage 9: Generate explanation via XAI layer and persist as UnifiedExplanation.

        LLM is used ONLY for formatting explanation text, NOT for scoring.

        When *scoring_breakdown* is provided, the UnifiedExplanation is built
        with authoritative sub-score data and persisted to the explanation
        store so that API and storage representations are always consistent.

        Returns
        -------
        _ExplanationState or None
            Contains the API-facing ExplanationResult plus the hash-chain
            metadata (record_hash, explanation_id, stage3_*_hash) needed
            to enrich the Stage-9 pipeline artifact.
        """
        if self._main_controller:
            try:
                # Prepare features for explanation.
                # Absent features default to 0.0 — non-zero defaults fabricate
                # phantom signal and are illegal per DATA_PURITY invariant.
                explain_features = {
                    "math_score": features.get("math_score", 0.0),
                    "logic_score": features.get("logic_score", 0.0),
                    **{k: v for k, v in features.items() if k not in ("llm_extracted",)},
                }

                result = await self._main_controller.dispatch(
                    service="explain",
                    action="run",
                    payload={
                        "user_id": profile.get("user_id", "anonymous"),
                        "features": explain_features,
                        "top_career": top_careers[0].name if top_careers else None,
                    },
                    context={"trace_id": trace_id},
                )

                # ── Force-XAI Policy ─────────────────────────────────────────────
                # If dispatch returned a stub (delegated / no reasoning_chain),
                # replace result with deterministic explanation built exclusively
                # from cached SIMGR scoring artifacts — no LLM, no re-scoring.
                _xai_is_stub = (
                    result.get("status") in (
                        "delegated",
                        "delegated_to_explain_controller",
                    )
                    or not result.get("reasoning_chain")
                )
                if _xai_is_stub and (top_careers or scoring_breakdown is not None):
                    logger.info(
                        "[%s] XAI dispatch stub detected — using deterministic "
                        "fallback from SIMGR scoring artifacts (no LLM).",
                        trace_id,
                    )
                    result = self._build_deterministic_explain_payload(
                        top_careers, profile, features, scoring_breakdown
                    )

                if result.get("status") != "error":
                    # ── Build UnifiedExplanation (authoritative schema) ────
                    breakdown: Dict[str, float] = {}
                    per_component_contributions: Dict[str, float] = {}
                    if scoring_breakdown is not None:
                        breakdown = dict(scoring_breakdown.weights)
                        per_component_contributions = dict(
                            scoring_breakdown.contributions
                        )

                    reasoning: List[str] = result.get("reasoning_chain", [])
                    input_summary: Dict[str, Any] = {
                        k: (float(v) if isinstance(v, (int, float)) else str(v))
                        for k, v in explain_features.items()
                    }
                    rule_path: List[Dict[str, Any]] = result.get("rule_path", [])
                    rule_weights: Dict[str, float] = {
                        r.get("rule_id", f"rule_{i}"): float(r.get("weight", 0.0))
                        for i, r in enumerate(rule_path)
                    }
                    evidence_list: List[Dict[str, Any]] = result.get("evidence", [])

                    try:
                        unified = UnifiedExplanation.build(
                            trace_id=trace_id,
                            model_id=self._model_version,
                            kb_version="default",
                            weight_version=self._weights_version,
                            breakdown=breakdown,
                            per_component_contributions=per_component_contributions,
                            reasoning=reasoning,
                            input_summary=input_summary,
                            feature_snapshot={
                                k: float(v)
                                for k, v in explain_features.items()
                                if isinstance(v, (int, float))
                            },
                            rule_path=rule_path,
                            weights=rule_weights,
                            evidence=evidence_list,
                            confidence=float(result.get("confidence", 0.7)),
                            prediction={
                                "career": top_careers[0].name if top_careers else "",
                                "score": float(top_careers[0].total_score) if top_careers else 0.0,
                            },
                            stage3_input_hash=result.get(
                                "stage3_input_hash",
                                result.get("input_hash", ""),
                            ),
                            stage3_output_hash=result.get(
                                "stage3_output_hash",
                                result.get("output_hash", ""),
                            ),
                        )
                        # ── ① After explanation assembly: validate math consistency ──
                        # Validation runs BEFORE artifact creation and BEFORE
                        # response return.  If scoring_breakdown is available,
                        # contributions must match it exactly or the pipeline fails.
                        if scoring_breakdown is not None:
                            validate_explanation_consistency(
                                unified,
                                scoring_breakdown,
                                self._weights_version,
                            )
                        # ── ② Before artifact creation: persist unified explanation ──
                        # append_unified() delegates to append_record() for the
                        # canonical chain-hash write, then enriches the row with
                        # unified schema columns.  The returned record_hash is the
                        # SHA-256 chain link that ties this explanation to the log.
                        try:
                            storage = get_explanation_storage()
                            unified, record_hash, explanation_db_id = await storage.append_unified(unified)
                        except Exception as _store_err:
                            # Storage failure must not block XAI output.
                            # Use explanation_hash as a deterministic pseudo-record_hash
                            # so the hash-chain field is populated (not empty).
                            logger.warning(
                                "[%s] Explanation storage failed (%s) — hash-only fallback.",
                                trace_id,
                                type(_store_err).__name__,
                            )
                            record_hash = unified.explanation_hash
                            explanation_db_id = "xai-hash-" + unified.explanation_hash[:8]
                        logger.debug(
                            "[%s] UnifiedExplanation persisted "
                            "(explanation_id=%s record_hash=%s... expl_hash=%s...)",
                            trace_id,
                            explanation_db_id,
                            record_hash[:16],
                            unified.explanation_hash[:16],
                        )
                        # ── Capture Stage-3 hashes for artifact propagation ──
                        _stage3_in  = result.get("stage3_input_hash",  result.get("input_hash",  ""))
                        _stage3_out = result.get("stage3_output_hash", result.get("output_hash", ""))
                        # Derive API response from the unified schema
                        api_data = unified.to_api_response()
                        factors = [
                            ExplanationFactor(
                                name=f["name"],
                                contribution=f["contribution"],
                                description=f["description"],
                            )
                            for f in api_data["factors"]
                        ]
                        # ── ③ Before response return: wrap in _ExplanationState ──
                        # ── Stage 4b: Analytical summary via dedicated prompt ──────
                        # Attempt to enrich the summary using the reasoning-engine
                        # prompt (analytical_explanation.txt).  Any failure falls
                        # back silently to the default XAI summary so the pipeline
                        # is never blocked.
                        #
                        # NOTE: api_data["summary"] = reasoning[0] = the mechanical
                        # "[Stage 1 - Input Summary]" template text — NEVER show that
                        # to users.  Build a human-readable Vietnamese fallback first;
                        # LLM output replaces it if Ollama responds in time.
                        _base_summary = self._build_readable_summary(
                            profile, top_careers, scoring_breakdown
                        )
                        try:
                            from backend.explain.stage4 import generate_analytical_summary  # noqa: PLC0415
                            import functools as _functools  # noqa: PLC0415
                            _profile_blob = {
                                "skills":          profile.get("skills", []),
                                "interests":       profile.get("interests", []),
                                "education_level": profile.get("education_level", ""),
                                "ability_score":   float(profile.get("ability_score", 0.0)),
                                "goals":           profile.get("goals", {}),
                                "top_career":      top_careers[0].name if top_careers else "",
                                "total_score":     float(top_careers[0].total_score) if top_careers else 0.0,
                                "score_breakdown": (
                                    dict(scoring_breakdown.contributions)
                                    if scoring_breakdown else {}
                                ),
                            }
                            _profile_json_str = json.dumps(_profile_blob, ensure_ascii=False)
                            _loop = asyncio.get_event_loop()
                            _analytical = await asyncio.wait_for(
                                _loop.run_in_executor(
                                    None,
                                    _functools.partial(
                                        generate_analytical_summary,
                                        _profile_json_str,
                                        6.0,
                                    ),
                                ),
                                timeout=6.0,
                            )
                            if _analytical:
                                _base_summary = _analytical
                                logger.info(
                                    "[%s] Analytical summary generated (%d chars)",
                                    trace_id, len(_base_summary),
                                )
                        except asyncio.TimeoutError:
                            logger.debug("[%s] Analytical summary timed out — using XAI summary", trace_id)
                        except Exception as _anal_err:
                            logger.debug("[%s] Analytical summary skipped: %s", trace_id, _anal_err)

                        return _ExplanationState(
                            result=ExplanationResult(
                                summary=_base_summary,
                                factors=factors,
                                confidence=api_data["confidence"],
                                reasoning_chain=api_data["reasoning_chain"],
                            ),
                            record_hash=record_hash,
                            explanation_id=explanation_db_id,
                            stage3_input_hash=_stage3_in,
                            stage3_output_hash=_stage3_out,
                            # Carry explanation_hash for Stage-6 decision audit record
                            explanation_hash=unified.explanation_hash,
                            # Carry per-component contributions for Rule-4 check
                            contributions=dict(unified.per_component_contributions),
                        )
                    except ExplanationInconsistencyError:
                        # Hard pipeline error — explanation arithmetic mismatch.
                        # Must NOT be silently swallowed; re-raise immediately.
                        raise
                    except Exception as build_err:
                        # UnifiedExplanation.build() failed.
                        # Do NOT produce an _ExplanationState with empty record_hash /
                        # explanation_id — that would bypass the hash-chain contract.
                        # Re-raise so the outer handler can log and return None cleanly.
                        logger.warning(
                            "[%s] UnifiedExplanation build failed: %s",
                            trace_id, build_err,
                        )
                        raise

            except ExplanationInconsistencyError:
                # Consistency violation: hard contract failure — propagate to caller.
                raise
            except Exception as e:
                # Dispatch, build, or storage failed.
                # Log with ASCII-safe repr to avoid cp1252 encode issues.
                logger.warning(
                    "[%s] Explanation path failed (%s) — direct-artifact fallback.",
                    trace_id,
                    type(e).__name__,
                )
                # Last-resort: build _ExplanationState directly from scoring
                # artifacts, bypassing UnifiedExplanation.build() and storage.
                if top_careers and scoring_breakdown is not None:
                    return self._build_xai_state_direct(
                        top_careers, profile, features, scoring_breakdown, trace_id
                    )
                return None

        # No main_controller: still produce a deterministic explanation from
        # cached SIMGR scoring artifacts — Force-XAI policy applies here too.
        if top_careers and scoring_breakdown is not None:
            logger.info(
                "[%s] XAI: no main_controller — deterministic explanation from SIMGR artifacts.",
                trace_id,
            )
            return self._build_xai_state_direct(
                top_careers, profile, features, scoring_breakdown, trace_id
            )
        return None
    
    # ─────────────────────────────────────────────────────────────────────────
    # DETERMINISTIC XAI HELPERS  (Force-XAI policy, no LLM)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_readable_summary(
        profile: Dict[str, Any],
        top_careers: List["CareerResult"],
        scoring_breakdown: Optional["ScoringBreakdown"],
    ) -> str:
        """
        Human-readable Vietnamese summary for use as the LLM-fallback.
        Never shows raw [Stage X - ...] template strings to end users.
        """
        skills      = profile.get("skills", []) or []
        education   = profile.get("education_level", "") or ""
        top         = top_careers[0] if top_careers else None
        top_name    = top.name if top else "ngành phù hợp"
        top_score   = float(top.total_score) if top else 0.0

        skill_parts = skills[:3]
        skill_list  = ", ".join(skill_parts) if skill_parts else "các kỹ năng hiện có"
        more_skills = f" và {len(skills) - 3} kỹ năng khác" if len(skills) > 3 else ""
        edu_part    = f" với nền tảng học vấn {education}" if education else ""

        if scoring_breakdown is not None:
            s_goal  = scoring_breakdown.contributions.get("goal_alignment", 0.0)
            s_skill = scoring_breakdown.contributions.get("skill", 0.0)
            s_edu   = scoring_breakdown.contributions.get("education", 0.0)
            # Pick the dominant dimension for the narrative
            dims = {"định hướng nghề nghiệp": s_goal, "kỹ năng chuyên môn": s_skill, "nền tảng học vấn": s_edu}
            strength = max(dims, key=dims.get)  # type: ignore[arg-type]
        else:
            strength = "kỹ năng chuyên môn"

        readiness = "tốt" if top_score >= 0.6 else "trung bình" if top_score >= 0.35 else "cần cải thiện"
        return (
            f"Hồ sơ cho thấy sự phù hợp với {top_name} "
            f"nhờ {strength} nổi bật — đặc biệt là {skill_list}{more_skills}{edu_part}. "
            f"Điểm tổng hợp SIMGR đạt {top_score:.2f}, phản ánh mức độ sẵn sàng {readiness} "
            f"cho lộ trình phát triển trong lĩnh vực này."
        )

    def _build_deterministic_explain_payload(
        self,
        top_careers: List["CareerResult"],
        profile: Dict[str, Any],
        features: Dict[str, Any],
        scoring_breakdown: Optional["ScoringBreakdown"],
    ) -> Dict[str, Any]:
        """
        Build a fully deterministic XAI explanation dict from SIMGR scoring
        artifacts.  No LLM is called.  No scoring is recomputed.

        Implements the 6-stage XAI contract:
          stage_1_input_summary      — profile fields
          stage_2_feature_reasoning  — feature + skill analysis
          stage_3_kb_mapping_logic   — KB career selection rationale
          stage_4_score_breakdown    — authoritative SIMGR sub-scores
          stage_5_gap_analysis       — gap from target thresholds
          stage_6_action_roadmap     — timeline-aware career roadmap
        """
        top = top_careers[0] if top_careers else None
        top_name  = top.name  if top else "Unknown"
        top_score = float(top.total_score if top else 0.0)

        skills    = profile.get("skills", [])
        interests = profile.get("interests", [])
        education = profile.get("education_level", "Unknown")
        ability   = float(profile.get("ability_score", 0.0))
        goals_raw = profile.get("goals", {})
        career_asp  = (
            goals_raw.get("career_aspirations", []) if isinstance(goals_raw, dict) else []
        )
        timeline  = (
            int(goals_raw.get("timeline_years", 3)) if isinstance(goals_raw, dict) else 3
        )

        # Sub-score contributions from ScoringBreakdown (no recomputation)
        if scoring_breakdown is not None:
            s_skill = scoring_breakdown.contributions.get("skill",           0.0)
            s_edu   = scoring_breakdown.contributions.get("education",       0.0)
            s_exp   = scoring_breakdown.contributions.get("experience",      0.0)
            s_goal  = scoring_breakdown.contributions.get("goal_alignment",  0.0)
            s_pref  = scoring_breakdown.contributions.get("preference",      0.0)
            s_final = scoring_breakdown.final_score
        else:
            s_skill = s_edu = s_exp = s_goal = s_pref = 0.0
            s_final = top_score

        skill_list = ", ".join(skills[:3]) if skills else "none"
        stage1 = (
            f"[Stage 1 - Input Summary] Profile: {len(skills)} skills"
            f" ({skill_list}), education={education},"
            f" ability={ability:.2f}, {len(interests)} interests."
        )
        stage2 = (
            f"[Stage 2 - Feature Reasoning] Skills aligned to {top_name} domain."
            f" Skill contribution: {s_skill:.4f}."
            f" Education contribution: {s_edu:.4f}."
        )
        stage3 = (
            f"[Stage 3 - KB Mapping] Top match: '{top_name}'"
            f" selected from {len(top_careers)} candidate(s)."
        )
        stage4 = (
            f"[Stage 4 - Score Breakdown] SIMGR final={s_final:.4f}:"
            f" skill={s_skill:.4f}, edu={s_edu:.4f},"
            f" exp={s_exp:.4f}, goal={s_goal:.4f}, pref={s_pref:.4f}."
        )
        skill_gap = max(0.0, 0.25 - s_skill)
        stage5 = (
            f"[Stage 5 - Gap Analysis] Skill gap: {skill_gap:.4f} vs target 0.25."
            f" Goal alignment: {s_goal:.4f}."
            f" Priority: strengthen domain-specific skills for '{top_name}'."
        )
        aspire = career_asp[0] if career_asp else top_name
        stage6 = (
            f"[Stage 6 - Roadmap] Target: {aspire} in {timeline} yr(s)."
            f" Step 1: Build core {top_name} skills."
            f" Step 2: Gain project experience."
            f" Step 3: Pursue certifications."
            f" Current readiness score: {s_final:.4f}."
        )

        reasoning_chain = [stage1, stage2, stage3, stage4, stage5, stage6]
        return {
            "status": "ok",
            "reasoning_chain": reasoning_chain,
            "confidence": min(0.5 + float(s_final), 0.95),
            "rule_path": [],
            "evidence": [],
            "explanation": stage1,
            "stage3_input_hash": "",
            "stage3_output_hash": "",
            # Structured 6-stage XAI output (contract fields)
            "xai_stage_1_input_summary":     stage1,
            "xai_stage_2_feature_reasoning": stage2,
            "xai_stage_3_kb_mapping_logic":  stage3,
            "xai_stage_4_score_breakdown": {
                "skill_match":      round(s_skill, 6),
                "gap_score":        round(skill_gap, 6),
                "readiness_index":  round(float(ability), 6),
                "final_score":      round(s_final, 6),
            },
            "xai_stage_5_gap_analysis":   stage5,
            "xai_stage_6_action_roadmap": stage6,
        }

    def _build_xai_state_direct(
        self,
        top_careers: List["CareerResult"],
        profile: Dict[str, Any],
        features: Dict[str, Any],
        scoring_breakdown: "ScoringBreakdown",
        trace_id: str,
    ) -> "_ExplanationState":
        """
        Build _ExplanationState directly from scoring artifacts without going
        through UnifiedExplanation.build() or ExplanationStorage.

        Used as a last-resort fallback when the full explanation pipeline fails.
        The record_hash is derived deterministically from contributions so the
        hash-chain field is populated (non-empty) and stable across runs.
        """
        import hashlib as _hl, json as _jn

        payload = self._build_deterministic_explain_payload(
            top_careers, profile, features, scoring_breakdown
        )
        per_contrib = dict(scoring_breakdown.contributions)
        reasoning   = payload["reasoning_chain"]
        confidence  = float(payload["confidence"])

        # Deterministic pseudo-record_hash from contributions
        contrib_canon = _jn.dumps(per_contrib, sort_keys=True)
        det_hash = _hl.sha256(contrib_canon.encode("utf-8")).hexdigest()
        record_hash    = det_hash
        explanation_id = "xai-direct-" + det_hash[:8]

        factors = [
            ExplanationFactor(
                name=comp,
                contribution=float(contrib),
                description=(
                    comp.replace("_", " ").title()
                    + f" sub-score contribution: {contrib:.4f}"
                ),
            )
            for comp, contrib in per_contrib.items()
        ]
        logger.debug(
            "[%s] XAI direct state built — explanation_id=%s record_hash=%s...",
            trace_id, explanation_id, det_hash[:16],
        )
        return _ExplanationState(
            result=ExplanationResult(
                summary=self._build_readable_summary(profile, top_careers, scoring_breakdown),
                factors=factors,
                confidence=confidence,
                reasoning_chain=reasoning,
            ),
            record_hash=record_hash,
            explanation_id=explanation_id,
            stage3_input_hash="",
            stage3_output_hash="",
            explanation_hash=det_hash,
            contributions=per_contrib,
        )

    def _fallback_scoring(self, profile: Dict[str, Any]) -> List[CareerResult]:
        """
        REMEDIATED: Fallback scoring - NOW RETURNS CONTROLLED ERROR.
        
        RATIONALE:
        - Hardcoded career lists break determinism guarantee
        - Rankings from non-SIMGR source create audit trail inconsistency
        - Production MUST use MainController.dispatch() only
        
        POLICY: Circuit breaker pattern - fail fast with clear error.
        """
        logger.error(
            "[FALLBACK_BLOCKED] Scoring fallback denied - MainController required. "
            "This is a controlled circuit breaker failure."
        )
        
        # REMEDIATION: Raise exception instead of returning fake data
        raise ScoringUnavailableError(
            "Scoring service unavailable. MainController is required for deterministic scoring. "
            "Fallback to hardcoded careers is disabled to maintain baseline integrity."
        )
    
    # _fallback_explanation() REMOVED — it produced an _ExplanationState with
    # empty record_hash and explanation_id, bypassing the hash-chain contract (BYP-3).
    # When explanation is unavailable, _generate_explanation() now returns None
    # and the Stage-9 artifact is emitted without an explanation field.
    
    def _get_career_database(self) -> List[Dict[str, Any]]:
        """Get career database from KB (falls back to hardcoded list)."""
        try:
            from backend.kb.database import get_db  # noqa: PLC0415
            from backend.kb.service import KnowledgeBaseService  # noqa: PLC0415
            from backend.kb import schemas as kb_schemas  # noqa: PLC0415
            db = next(get_db())
            kb = KnowledgeBaseService(db)
            careers = kb.list_careers(filters=kb_schemas.CareerFilter(), skip=0, limit=200)
            if careers:
                result = []
                for c in careers:
                    domain = c.domain.name if c.domain else "general"
                    req_skills = [
                        cs.skill.name for cs in (c.career_skills or [])
                        if getattr(cs, "requirement_type", "") == "required" and cs.skill
                    ]
                    pref_skills = [
                        cs.skill.name for cs in (c.career_skills or [])
                        if getattr(cs, "requirement_type", "") != "required" and cs.skill
                    ]
                    result.append({
                        "name": c.name,
                        "required_skills": req_skills,
                        "preferred_skills": pref_skills,
                        "domain": domain,
                        "domain_interests": [domain.lower()],
                        "ai_relevance": float(getattr(c, "ai_relevance", 0.6) or 0.6),
                        "growth_rate": float(getattr(c, "growth_rate", 0.1) or 0.1),
                        "competition": float(getattr(c, "competition", 0.5) or 0.5),
                    })
                return result
        except Exception as exc:
            logger.warning("KB career load failed, using hardcoded fallback: %s", exc)
        # Hardcoded fallback
        return [
            {
                "name": "Software Engineer",
                "required_skills": ["programming", "problem-solving"],
                "preferred_skills": ["teamwork", "communication"],
                "domain": "Technology",
                "domain_interests": ["technology", "innovation"],
                "ai_relevance": 0.8,
                "growth_rate": 0.15,
                "competition": 0.6,
            },
            {
                "name": "Data Scientist",
                "required_skills": ["statistics", "programming", "math"],
                "preferred_skills": ["communication", "visualization"],
                "domain": "Technology",
                "domain_interests": ["science", "technology", "research"],
                "ai_relevance": 0.9,
                "growth_rate": 0.2,
                "competition": 0.5,
            },
        ]
    
    def _log_snapshot(
        self, trace_id: str, request: DecisionRequest, response: DecisionResponse
    ) -> None:
        """Log full snapshot for audit trail."""
        snapshot = {
            "trace_id": trace_id,
            "timestamp": response.timestamp,
            "input": {
                "user_id": request.user_id,
                "scoring_input": request.scoring_input.model_dump(),
                "features": request.features.dict() if request.features else None,
            },
            "output": {
                "status": response.status,
                "rankings_count": len(response.rankings),
                "top_career": response.top_career.name if response.top_career else None,
            },
            "meta": response.meta.dict(),
        }
        logger.info(f"[SNAPSHOT] {trace_id}: {snapshot}")


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_decision_controller: Optional[DecisionController] = None


def get_decision_controller() -> DecisionController:
    """Get or create decision controller singleton."""
    global _decision_controller
    if _decision_controller is None:
        _decision_controller = DecisionController()
    return _decision_controller


def set_decision_controller_main(controller) -> None:
    """Set main controller on decision controller."""
    get_decision_controller().set_main_controller(controller)


def set_decision_controller_ops(ops) -> None:
    """Set ops hub on decision controller."""
    get_decision_controller().set_ops_hub(ops)
