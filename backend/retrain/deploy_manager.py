# backend/retrain/deploy_manager.py
"""
Deploy Manager
==============

Manages canary deployment and automatic rollback.

Deployment flow:
  1. Start canary (5% traffic to new model)
  2. Monitor metrics for observation period
  3. If metrics OK → promote to active
  4. If metrics FAIL → rollback canary
  5. Kill switch for emergency rollback
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from backend.inference.ab_router import ABRouter
from backend.inference.model_loader import ModelLoader
from backend.retrain.model_registry import ModelRegistry

logger = logging.getLogger("ml_retrain.deploy")


class DeployState(Enum):
    """Deployment state."""
    IDLE = "idle"
    CANARY = "canary"
    PROMOTING = "promoting"
    ROLLING_BACK = "rolling_back"


@dataclass
class DeployResult:
    """Result of a deployment operation."""
    success: bool
    action: str
    version: str
    state: str
    message: str
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "action": self.action,
            "version": self.version,
            "state": self.state,
            "message": self.message,
            "timestamp": self.timestamp,
        }


class DeployManager:
    """
    Manages canary deployment with automatic rollback.
    
    Usage::
    
        deploy = DeployManager(router, loader, registry)
        deploy.load_config(config)
        
        # Start canary
        result = deploy.start_canary("v2")
        
        # Monitor and auto-promote/rollback
        deploy.observe()
        
        # Or manual promotion
        deploy.promote()
        
        # Emergency rollback
        deploy.rollback()
    """
    
    def __init__(
        self,
        router: Optional[ABRouter] = None,
        loader: Optional[ModelLoader] = None,
        registry: Optional[ModelRegistry] = None,
    ):
        self._project_root = Path(__file__).resolve().parents[2]
        
        self._router = router or ABRouter()
        self._loader = loader or ModelLoader()
        self._registry = registry or ModelRegistry()
        
        # State
        self._state = DeployState.IDLE
        self._canary_version: Optional[str] = None
        self._canary_start_time: Optional[float] = None
        
        # Config (config-driven)
        self._canary_ratio = 0.05  # 5%
        self._observation_minutes = 30
        self._auto_rollback = True
        self._f1_threshold = 0.01  # F1_new >= F1_old - 0.01
        self._kill_switch = False
        
        # Monitoring
        self._observer_thread: Optional[threading.Thread] = None
        self._stop_observer = threading.Event()
        
        # Logs
        self._deploy_logs_dir = self._project_root / "deploy_logs"
        self._deploy_logs_dir.mkdir(parents=True, exist_ok=True)
    
    def load_config(self, config: Dict[str, Any]) -> None:
        """Load deployment configuration."""
        deploy_cfg = config.get("deploy", {})
        
        self._canary_ratio = deploy_cfg.get("canary_ratio", 0.05)
        self._observation_minutes = deploy_cfg.get("observation_minutes", 30)
        self._auto_rollback = deploy_cfg.get("auto_rollback", True)
        self._f1_threshold = deploy_cfg.get("f1_threshold", 0.01)
        
        logger.info(
            "Deploy config: canary=%.1f%% obs=%dmin auto_rollback=%s",
            self._canary_ratio * 100,
            self._observation_minutes,
            self._auto_rollback,
        )
    
    def get_state(self) -> Dict[str, Any]:
        """Get current deployment state."""
        return {
            "state": self._state.value,
            "canary_version": self._canary_version,
            "canary_start_time": self._canary_start_time,
            "canary_ratio": self._canary_ratio,
            "kill_switch": self._kill_switch,
            "auto_rollback": self._auto_rollback,
        }
    
    def start_canary(self, version: str) -> DeployResult:
        """
        Start canary deployment for a new version.
        
        Routes canary_ratio traffic to new model.
        """
        if self._state != DeployState.IDLE:
            return DeployResult(
                success=False,
                action="start_canary",
                version=version,
                state=self._state.value,
                message=f"Cannot start canary: already in {self._state.value} state",
            )
        
        if self._kill_switch:
            return DeployResult(
                success=False,
                action="start_canary",
                version=version,
                state=self._state.value,
                message="Cannot start canary: kill switch is enabled",
            )
        
        # Verify version exists
        version_info = self._registry.get_version(version)
        if not version_info:
            return DeployResult(
                success=False,
                action="start_canary",
                version=version,
                state=self._state.value,
                message=f"Version not found: {version}",
            )
        
        try:
            # Load canary model
            self._loader.load_canary(version)
            
            # Configure router
            active = self._registry.get_active()
            active_version = active.version if active else "unknown"
            
            self._router.configure(
                canary_ratio=self._canary_ratio,
                canary_version=version,
                active_version=active_version,
            )
            
            # Update state
            self._state = DeployState.CANARY
            self._canary_version = version
            self._canary_start_time = time.time()
            
            # Log
            self._log_deploy_event("canary_started", version, {
                "canary_ratio": self._canary_ratio,
                "active_version": active_version,
            })
            
            logger.info(
                "Started canary: %s with %.1f%% traffic",
                version, self._canary_ratio * 100,
            )
            
            return DeployResult(
                success=True,
                action="start_canary",
                version=version,
                state=self._state.value,
                message=f"Canary started with {self._canary_ratio*100:.1f}% traffic",
            )
            
        except Exception as e:
            logger.error("Failed to start canary: %s", e)
            return DeployResult(
                success=False,
                action="start_canary",
                version=version,
                state=self._state.value,
                message=str(e),
            )
    
    def promote(self) -> DeployResult:
        """Promote canary to active."""
        if self._state != DeployState.CANARY:
            return DeployResult(
                success=False,
                action="promote",
                version=self._canary_version or "",
                state=self._state.value,
                message=f"Cannot promote: not in canary state (current: {self._state.value})",
            )
        
        version = self._canary_version
        
        try:
            self._state = DeployState.PROMOTING
            
            # Activate in registry
            self._registry.activate(version)
            
            # Hot-swap in loader
            self._loader.hot_swap(version)
            
            # Update router (100% to new active)
            self._router.configure(
                canary_ratio=0.0,
                canary_version="",
                active_version=version,
            )
            self._router.promote_canary()
            
            # Reset state
            self._state = DeployState.IDLE
            self._canary_version = None
            self._canary_start_time = None
            
            # Log
            self._log_deploy_event("canary_promoted", version, {})
            
            logger.info("Promoted canary %s to active", version)
            
            return DeployResult(
                success=True,
                action="promote",
                version=version,
                state=self._state.value,
                message=f"Promoted {version} to active",
            )
            
        except Exception as e:
            logger.error("Failed to promote: %s", e)
            self._state = DeployState.CANARY  # Revert state
            return DeployResult(
                success=False,
                action="promote",
                version=version,
                state=self._state.value,
                message=str(e),
            )
    
    def rollback(self, reason: str = "manual") -> DeployResult:
        """
        Rollback canary or active deployment.
        
        If in canary state: abort canary
        If in idle state: rollback to previous version
        """
        version = self._canary_version or "active"
        
        try:
            self._state = DeployState.ROLLING_BACK
            
            if self._canary_version:
                # Abort canary
                self._router.rollback_canary()
                self._router.configure(
                    canary_ratio=0.0,
                    canary_version="",
                )
                
                old_canary = self._canary_version
                self._canary_version = None
                self._canary_start_time = None
                
                self._log_deploy_event("canary_rolled_back", old_canary, {
                    "reason": reason,
                })
                
                logger.info("Rolled back canary %s: %s", old_canary, reason)
                
            else:
                # Rollback active to previous
                rolled_to = self._registry.rollback()
                
                if rolled_to:
                    self._loader.rollback()
                    self._router.configure(active_version=rolled_to)
                    
                    self._log_deploy_event("active_rolled_back", rolled_to, {
                        "reason": reason,
                    })
                    
                    logger.info("Rolled back active to %s: %s", rolled_to, reason)
                else:
                    logger.warning("No rollback version available")
            
            self._state = DeployState.IDLE
            
            return DeployResult(
                success=True,
                action="rollback",
                version=version,
                state=self._state.value,
                message=f"Rolled back: {reason}",
            )
            
        except Exception as e:
            logger.error("Rollback failed: %s", e)
            self._state = DeployState.IDLE
            return DeployResult(
                success=False,
                action="rollback",
                version=version,
                state=self._state.value,
                message=str(e),
            )
    
    def set_kill_switch(self, enabled: bool) -> DeployResult:
        """Enable or disable kill switch."""
        self._kill_switch = enabled
        self._router.set_kill_switch(enabled)
        
        if enabled and self._state == DeployState.CANARY:
            # Abort canary deployment
            self.rollback("kill_switch_enabled")
        
        self._log_deploy_event(
            "kill_switch_changed",
            "",
            {"enabled": enabled},
        )
        
        return DeployResult(
            success=True,
            action="kill_switch",
            version="",
            state=self._state.value,
            message=f"Kill switch {'enabled' if enabled else 'disabled'}",
        )
    
    def start_observer(self) -> None:
        """Start background observer for auto-promote/rollback."""
        if self._observer_thread and self._observer_thread.is_alive():
            return
        
        self._stop_observer.clear()
        self._observer_thread = threading.Thread(
            target=self._observe_loop,
            daemon=True,
        )
        self._observer_thread.start()
        logger.info("Started deployment observer")
    
    def stop_observer(self) -> None:
        """Stop background observer."""
        self._stop_observer.set()
        if self._observer_thread:
            self._observer_thread.join(timeout=5)
        logger.info("Stopped deployment observer")
    
    def _observe_loop(self) -> None:
        """Background observation loop."""
        while not self._stop_observer.is_set():
            if self._state == DeployState.CANARY and self._canary_start_time:
                elapsed_minutes = (time.time() - self._canary_start_time) / 60
                
                if elapsed_minutes >= self._observation_minutes:
                    # Check if we should promote or rollback
                    decision = self._evaluate_canary()
                    
                    if decision == "promote":
                        self.promote()
                    elif decision == "rollback":
                        if self._auto_rollback:
                            self.rollback("auto_rollback_metrics_failed")
            
            # Check every 30 seconds
            self._stop_observer.wait(30)
    
    def _evaluate_canary(self) -> str:
        """
        Evaluate whether canary should be promoted or rolled back.
        
        Returns: "promote", "rollback", or "continue"
        """
        # Get router stats
        stats = self._router.get_stats()
        
        # Get canary metrics
        canary_info = self._registry.get_version(self._canary_version)
        active_info = self._registry.get_active()
        
        if not canary_info or not active_info:
            return "continue"
        
        # Compare F1 scores
        canary_f1 = canary_info.f1
        active_f1 = active_info.f1
        
        # Promotion rule: F1_new >= F1_old - threshold
        if canary_f1 >= active_f1 - self._f1_threshold:
            logger.info(
                "Canary evaluation: PROMOTE (f1=%.4f >= %.4f - %.4f)",
                canary_f1, active_f1, self._f1_threshold,
            )
            return "promote"
        else:
            logger.warning(
                "Canary evaluation: ROLLBACK (f1=%.4f < %.4f - %.4f)",
                canary_f1, active_f1, self._f1_threshold,
            )
            return "rollback"
    
    def _log_deploy_event(
        self,
        event: str,
        version: str,
        details: Dict[str, Any],
    ) -> None:
        """Log deployment event."""
        log_entry = {
            "event": event,
            "version": version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details,
        }
        
        log_file = self._deploy_logs_dir / f"deploy_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
