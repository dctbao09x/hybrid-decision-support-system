"""State Store - Persistence layer for scheduler state (last_retrain_at, run history)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional


@dataclass
class SchedulerState:
    """Represents the current state of the retrain scheduler."""
    last_retrain_at: Optional[str] = None
    last_trigger: Optional[str] = None
    last_run_id: Optional[str] = None
    last_status: Optional[str] = None
    total_auto_retrains: int = 0
    total_blocked_by_cooldown: int = 0
    total_blocked_by_storm: int = 0
    consecutive_failures: int = 0
    run_history: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_retrain_at": self.last_retrain_at,
            "last_trigger": self.last_trigger,
            "last_run_id": self.last_run_id,
            "last_status": self.last_status,
            "total_auto_retrains": self.total_auto_retrains,
            "total_blocked_by_cooldown": self.total_blocked_by_cooldown,
            "total_blocked_by_storm": self.total_blocked_by_storm,
            "consecutive_failures": self.consecutive_failures,
            "run_history": self.run_history[-100:],  # Keep last 100 entries
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchedulerState":
        return cls(
            last_retrain_at=data.get("last_retrain_at"),
            last_trigger=data.get("last_trigger"),
            last_run_id=data.get("last_run_id"),
            last_status=data.get("last_status"),
            total_auto_retrains=data.get("total_auto_retrains", 0),
            total_blocked_by_cooldown=data.get("total_blocked_by_cooldown", 0),
            total_blocked_by_storm=data.get("total_blocked_by_storm", 0),
            consecutive_failures=data.get("consecutive_failures", 0),
            run_history=data.get("run_history", []),
            updated_at=data.get("updated_at"),
        )


class StateStore:
    """Persistent storage for scheduler state.
    
    Supports JSON file storage by default, with the option to extend to SQLite or Redis.
    """

    def __init__(
        self,
        storage_path: Optional[str] = None,
        backend: str = "json",
    ):
        """Initialize the state store.
        
        Args:
            storage_path: Path to store state. Defaults to storage/mlops/scheduler_state.json
            backend: Storage backend type ('json', 'sqlite'). Default is 'json'.
        """
        self._root = Path(__file__).resolve().parents[3]
        self._backend = backend
        
        if storage_path:
            self._path = Path(storage_path)
        else:
            self._path = self._root / "storage" / "mlops" / "scheduler_state.json"
        
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._state: Optional[SchedulerState] = None
        
        # Initialize state from storage or create new
        self._load_or_init()

    def _load_or_init(self) -> None:
        """Load state from storage or initialize with defaults."""
        if self._backend == "json":
            if self._path.exists():
                try:
                    with self._path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._state = SchedulerState.from_dict(data)
                except (json.JSONDecodeError, KeyError, TypeError):
                    self._state = SchedulerState()
            else:
                self._state = SchedulerState()
                self._persist()
        else:
            self._state = SchedulerState()

    def _persist(self) -> None:
        """Persist current state to storage."""
        if self._state is None:
            return
        
        self._state.updated_at = datetime.now(timezone.utc).isoformat()
        
        if self._backend == "json":
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(self._state.to_dict(), f, ensure_ascii=False, indent=2)

    def get_state(self) -> SchedulerState:
        """Get current scheduler state."""
        with self._lock:
            if self._state is None:
                self._load_or_init()
            return self._state  # type: ignore

    def get_last_retrain_at(self) -> Optional[datetime]:
        """Get the timestamp of the last retrain operation."""
        with self._lock:
            state = self.get_state()
            if state.last_retrain_at:
                return datetime.fromisoformat(state.last_retrain_at)
            return None

    def record_retrain(
        self,
        run_id: str,
        trigger: str,
        status: str,
        metrics: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record a retrain operation.
        
        Args:
            run_id: Unique identifier for the run
            trigger: What triggered the retrain ('auto', 'manual', 'alarm')
            status: Result status ('success', 'failed')
            metrics: Optional metrics from the training run
            error: Optional error message if failed
        """
        with self._lock:
            state = self.get_state()
            now = datetime.now(timezone.utc).isoformat()
            
            # Update state
            state.last_retrain_at = now
            state.last_trigger = trigger
            state.last_run_id = run_id
            state.last_status = status
            
            if trigger == "auto":
                state.total_auto_retrains += 1
            
            if status == "success":
                state.consecutive_failures = 0
            else:
                state.consecutive_failures += 1
            
            # Add to history
            entry = {
                "run_id": run_id,
                "trigger": trigger,
                "status": status,
                "timestamp": now,
                "metrics": metrics,
                "error": error,
            }
            state.run_history.append(entry)
            
            # Keep only last 100 entries
            if len(state.run_history) > 100:
                state.run_history = state.run_history[-100:]
            
            self._persist()

    def record_block(self, block_type: str, reason: str) -> None:
        """Record a blocked retrain attempt.
        
        Args:
            block_type: Type of block ('cooldown', 'storm')
            reason: Detailed reason for the block
        """
        with self._lock:
            state = self.get_state()
            now = datetime.now(timezone.utc).isoformat()
            
            if block_type == "cooldown":
                state.total_blocked_by_cooldown += 1
            elif block_type == "storm":
                state.total_blocked_by_storm += 1
            
            # Add to history
            entry = {
                "run_id": None,
                "trigger": "blocked",
                "status": f"blocked_{block_type}",
                "timestamp": now,
                "reason": reason,
            }
            state.run_history.append(entry)
            
            if len(state.run_history) > 100:
                state.run_history = state.run_history[-100:]
            
            self._persist()

    def get_recent_runs(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get runs from the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of run entries within the time window
        """
        with self._lock:
            state = self.get_state()
            cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
            
            recent = []
            for entry in state.run_history:
                try:
                    ts = datetime.fromisoformat(entry.get("timestamp", "")).timestamp()
                    if ts >= cutoff:
                        recent.append(entry)
                except (ValueError, TypeError):
                    continue
            
            return recent

    def reset_state(self) -> None:
        """Reset state to defaults (for testing/maintenance)."""
        with self._lock:
            self._state = SchedulerState()
            self._persist()


# Singleton instance
_state_store: Optional[StateStore] = None


def get_state_store() -> StateStore:
    """Get the singleton StateStore instance."""
    global _state_store
    if _state_store is None:
        _state_store = StateStore()
    return _state_store
