"""Retrain Scheduler - Automated model retraining based on metrics and feedback."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Dict, List, Optional

from backend.mlops.scheduler.policies import (
    AntiStormPolicy,
    CooldownPolicy,
    CooldownStatus,
    CooldownViolation,
    get_anti_storm_policy,
    get_cooldown_policy,
)
from backend.mlops.scheduler.state_store import StateStore, get_state_store

logger = logging.getLogger(__name__)


@dataclass
class RetrainTriggerCondition:
    """Conditions that can trigger automatic retraining."""
    metric_name: str
    threshold: float
    comparison: str  # 'gt', 'lt', 'gte', 'lte'
    weight: float = 1.0

    def evaluate(self, value: float) -> bool:
        """Check if the condition is met."""
        if self.comparison == "gt":
            return value > self.threshold
        elif self.comparison == "lt":
            return value < self.threshold
        elif self.comparison == "gte":
            return value >= self.threshold
        elif self.comparison == "lte":
            return value <= self.threshold
        return False


@dataclass
class SchedulerConfig:
    """Configuration for the retrain scheduler."""
    enabled: bool = True
    poll_interval_seconds: int = 300  # 5 minutes
    min_feedback_count: int = 100  # Minimum feedback before considering retrain
    accuracy_drop_threshold: float = 0.05
    drift_score_threshold: float = 0.25
    error_rate_threshold: float = 0.03
    feedback_negative_rate_threshold: float = 0.15

    @classmethod
    def from_env(cls) -> "SchedulerConfig":
        """Load configuration from environment variables."""
        return cls(
            enabled=os.getenv("MLOPS_SCHEDULER_ENABLED", "true").lower() in ("true", "1", "yes"),
            poll_interval_seconds=int(os.getenv("MLOPS_SCHEDULER_POLL_INTERVAL", "300")),
            min_feedback_count=int(os.getenv("MLOPS_SCHEDULER_MIN_FEEDBACK", "100")),
            accuracy_drop_threshold=float(os.getenv("MLOPS_SCHEDULER_ACCURACY_DROP", "0.05")),
            drift_score_threshold=float(os.getenv("MLOPS_SCHEDULER_DRIFT_THRESHOLD", "0.25")),
            error_rate_threshold=float(os.getenv("MLOPS_SCHEDULER_ERROR_RATE", "0.03")),
            feedback_negative_rate_threshold=float(os.getenv("MLOPS_SCHEDULER_NEGATIVE_FEEDBACK", "0.15")),
        )


class RetrainScheduler:
    """Automated retrain scheduler with cooldown and anti-storm protection.
    
    Polls metrics and feedback statistics to determine when retraining is needed.
    Enforces cooldown between retrains and prevents retrain storms.
    
    Example usage:
        scheduler = RetrainScheduler()
        await scheduler.start()
        
        # Or manually trigger check
        result = await scheduler.check_and_trigger()
    """

    def __init__(
        self,
        config: Optional[SchedulerConfig] = None,
        state_store: Optional[StateStore] = None,
        cooldown_policy: Optional[CooldownPolicy] = None,
        anti_storm_policy: Optional[AntiStormPolicy] = None,
    ):
        """Initialize the scheduler.
        
        Args:
            config: Scheduler configuration. If None, loads from env.
            state_store: State persistence store. If None, uses default.
            cooldown_policy: Cooldown policy. If None, uses default.
            anti_storm_policy: Anti-storm policy. If None, uses default.
        """
        self._config = config or SchedulerConfig.from_env()
        self._state_store = state_store or get_state_store()
        self._cooldown_policy = cooldown_policy or get_cooldown_policy()
        self._anti_storm_policy = anti_storm_policy or get_anti_storm_policy()
        
        self._lock = RLock()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # Callbacks for metric and feedback retrieval
        self._metric_provider: Optional[Callable[[], Dict[str, Any]]] = None
        self._feedback_provider: Optional[Callable[[], Dict[str, Any]]] = None
        self._train_callback: Optional[Callable[[str], Any]] = None
        
        # Default trigger conditions
        self._conditions = [
            RetrainTriggerCondition("accuracy_drop", self._config.accuracy_drop_threshold, "gte", 2.0),
            RetrainTriggerCondition("drift_score", self._config.drift_score_threshold, "gte", 1.5),
            RetrainTriggerCondition("error_rate", self._config.error_rate_threshold, "gte", 1.5),
            RetrainTriggerCondition("negative_feedback_rate", self._config.feedback_negative_rate_threshold, "gte", 1.0),
        ]

    def configure(
        self,
        metric_provider: Callable[[], Dict[str, Any]],
        feedback_provider: Callable[[], Dict[str, Any]],
        train_callback: Callable[[str], Any],
    ) -> None:
        """Configure the scheduler with data providers and training callback.
        
        Args:
            metric_provider: Function that returns current metrics
            feedback_provider: Function that returns feedback statistics
            train_callback: Function to call for training (receives trigger type)
        """
        self._metric_provider = metric_provider
        self._feedback_provider = feedback_provider
        self._train_callback = train_callback

    @property
    def enabled(self) -> bool:
        """Check if the scheduler is enabled."""
        return self._config.enabled

    @property
    def running(self) -> bool:
        """Check if the scheduler is currently running."""
        return self._running

    def get_cooldown_status(self) -> CooldownStatus:
        """Get the current cooldown status."""
        last_retrain = self._state_store.get_last_retrain_at()
        return self._cooldown_policy.check(last_retrain)

    def get_status(self) -> Dict[str, Any]:
        """Get full scheduler status including cooldown and state."""
        state = self._state_store.get_state()
        cooldown = self.get_cooldown_status()
        recent_runs = self._state_store.get_recent_runs(self._anti_storm_policy.window_hours)
        storm_status = self._anti_storm_policy.check(recent_runs)
        
        return {
            "enabled": self.enabled,
            "running": self.running,
            "poll_interval_seconds": self._config.poll_interval_seconds,
            "cooldown": cooldown.to_dict(),
            "anti_storm": storm_status.to_dict(),
            "last_retrain_at": state.last_retrain_at,
            "last_trigger": state.last_trigger,
            "last_status": state.last_status,
            "total_auto_retrains": state.total_auto_retrains,
            "total_blocked_by_cooldown": state.total_blocked_by_cooldown,
            "total_blocked_by_storm": state.total_blocked_by_storm,
            "consecutive_failures": state.consecutive_failures,
        }

    def _collect_metrics(self) -> Dict[str, Any]:
        """Collect current metrics from the configured provider."""
        if self._metric_provider is None:
            logger.warning("No metric provider configured")
            return {}
        
        try:
            return self._metric_provider()
        except Exception as e:
            logger.error("Failed to collect metrics: %s", e)
            return {}

    def _collect_feedback_stats(self) -> Dict[str, Any]:
        """Collect feedback statistics from the configured provider."""
        if self._feedback_provider is None:
            logger.warning("No feedback provider configured")
            return {}
        
        try:
            return self._feedback_provider()
        except Exception as e:
            logger.error("Failed to collect feedback stats: %s", e)
            return {}

    def _evaluate_conditions(
        self,
        metrics: Dict[str, Any],
        feedback_stats: Dict[str, Any],
    ) -> tuple[bool, List[str]]:
        """Evaluate trigger conditions against current data.
        
        Args:
            metrics: Current metrics
            feedback_stats: Current feedback statistics
            
        Returns:
            Tuple of (should_trigger, list of triggered reasons)
        """
        triggered_reasons: List[str] = []
        total_weight = 0.0
        
        combined = {**metrics, **feedback_stats}
        
        for condition in self._conditions:
            value = combined.get(condition.metric_name)
            if value is not None and condition.evaluate(float(value)):
                reason = f"{condition.metric_name}={value} ({condition.comparison} {condition.threshold})"
                triggered_reasons.append(reason)
                total_weight += condition.weight
        
        # Require at least one condition to trigger, or high weight
        should_trigger = len(triggered_reasons) >= 1 and total_weight >= 1.0
        
        return should_trigger, triggered_reasons

    async def check_and_trigger(self, force: bool = False) -> Dict[str, Any]:
        """Check conditions and trigger retrain if needed.
        
        Args:
            force: Force retrain even if conditions are not met (still respects cooldown)
            
        Returns:
            Result dictionary with status and details
        """
        with self._lock:
            result: Dict[str, Any] = {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "triggered": False,
                "blocked": False,
                "reason": None,
                "train_result": None,
            }
            
            # Check cooldown
            last_retrain = self._state_store.get_last_retrain_at()
            cooldown_status = self._cooldown_policy.check(last_retrain)
            result["cooldown_status"] = cooldown_status.to_dict()
            
            if cooldown_status.active and not force:
                self._state_store.record_block("cooldown", f"Remaining: {cooldown_status.remaining_hours:.2f}h")
                result["blocked"] = True
                result["reason"] = f"Cooldown active: {cooldown_status.remaining_hours:.2f}h remaining"
                logger.info("Retrain blocked by cooldown: %s", result["reason"])
                return result
            
            # Check anti-storm
            recent_runs = self._state_store.get_recent_runs(self._anti_storm_policy.window_hours)
            storm_status = self._anti_storm_policy.check(recent_runs)
            result["anti_storm_status"] = storm_status.to_dict()
            
            if storm_status.blocked:
                self._state_store.record_block("storm", storm_status.reason or "Storm protection")
                result["blocked"] = True
                result["reason"] = storm_status.reason
                logger.info("Retrain blocked by anti-storm: %s", result["reason"])
                return result
            
            # Collect data
            metrics = self._collect_metrics()
            feedback_stats = self._collect_feedback_stats()
            result["metrics"] = metrics
            result["feedback_stats"] = feedback_stats
            
            # Evaluate conditions
            if not force:
                should_trigger, reasons = self._evaluate_conditions(metrics, feedback_stats)
                result["trigger_reasons"] = reasons
                
                if not should_trigger:
                    result["reason"] = "No trigger conditions met"
                    return result
            else:
                result["trigger_reasons"] = ["forced"]
            
            # Trigger retrain
            result["triggered"] = True
            
            if self._train_callback is None:
                result["train_result"] = {"status": "error", "error": "No train callback configured"}
                return result
            
            try:
                logger.info("Triggering auto retrain. Reasons: %s", result.get("trigger_reasons"))
                train_result = await self._train_callback("auto")
                result["train_result"] = train_result
                
                # Record in state store
                run_id = train_result.get("run_id", "unknown")
                status = train_result.get("status", "unknown")
                self._state_store.record_retrain(
                    run_id=run_id,
                    trigger="auto",
                    status=status,
                    metrics=train_result.get("metrics"),
                    error=train_result.get("error"),
                )
                
                logger.info("Auto retrain completed: %s", status)
            except CooldownViolation as e:
                result["triggered"] = False
                result["blocked"] = True
                result["reason"] = str(e)
                result["train_result"] = {"status": "blocked", "error": str(e)}
            except Exception as e:
                logger.error("Auto retrain failed: %s", e)
                result["train_result"] = {"status": "failed", "error": str(e)}
                self._state_store.record_retrain(
                    run_id="error",
                    trigger="auto",
                    status="failed",
                    error=str(e),
                )
            
            return result

    async def _poll_loop(self) -> None:
        """Background polling loop."""
        logger.info(
            "Retrain scheduler started. Poll interval: %ds",
            self._config.poll_interval_seconds,
        )
        
        while self._running:
            try:
                await self.check_and_trigger()
            except Exception as e:
                logger.error("Poll loop error: %s", e)
            
            await asyncio.sleep(self._config.poll_interval_seconds)

    async def start(self) -> None:
        """Start the background scheduler."""
        if not self._config.enabled:
            logger.info("Retrain scheduler is disabled")
            return
        
        if self._running:
            logger.warning("Retrain scheduler already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Retrain scheduler started")

    async def stop(self) -> None:
        """Stop the background scheduler."""
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Retrain scheduler stopped")


# Singleton instance
_scheduler: Optional[RetrainScheduler] = None


def get_retrain_scheduler() -> RetrainScheduler:
    """Get the singleton RetrainScheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = RetrainScheduler()
    return _scheduler


async def initialize_scheduler(
    metric_provider: Callable[[], Dict[str, Any]],
    feedback_provider: Callable[[], Dict[str, Any]],
    train_callback: Callable[[str], Any],
) -> RetrainScheduler:
    """Initialize and start the scheduler with providers.
    
    Args:
        metric_provider: Function that returns current metrics
        feedback_provider: Function that returns feedback statistics
        train_callback: Async function to call for training
        
    Returns:
        The configured and started scheduler
    """
    scheduler = get_retrain_scheduler()
    scheduler.configure(
        metric_provider=metric_provider,
        feedback_provider=feedback_provider,
        train_callback=train_callback,
    )
    await scheduler.start()
    return scheduler
