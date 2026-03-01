"""
Kill Switch Router
==================
Provides unified kill-switch control endpoints that the frontend
opsApi.js and other admin components call.

Endpoints:
  GET  /api/v1/kill-switch/status       — current kill-switch state
  POST /api/v1/kill-switch/activate     — activate kill-switch (halt inference)
  POST /api/v1/kill-switch/deactivate   — deactivate kill-switch (resume)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("api.routers.kill_switch")

router = APIRouter(prefix="/api/v1/kill-switch", tags=["Kill Switch"])

# ---------------------------------------------------------------------------
# Shared state (in-process; production would use Redis/Postgres)
# ---------------------------------------------------------------------------

_kill_switch_state: Dict[str, Any] = {
    "active": False,
    "reason": None,
    "activated_at": None,
    "activated_by": None,
}


class KillSwitchActivateRequest(BaseModel):
    reason: str = "Emergency halt"
    scope: Optional[str] = "all"  # "all" | "inference" | "scoring"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    summary="Kill-switch status",
    response_description="Current kill-switch state",
)
async def kill_switch_status() -> Dict[str, Any]:
    """Returns the current kill-switch activation state."""
    return {
        "active": _kill_switch_state["active"],
        "reason": _kill_switch_state["reason"],
        "activated_at": _kill_switch_state["activated_at"],
        "activated_by": _kill_switch_state["activated_by"],
        "scope": "all",
    }


@router.post(
    "/activate",
    summary="Activate kill-switch",
    response_description="Kill-switch activated",
)
async def kill_switch_activate(
    body: KillSwitchActivateRequest,
) -> Dict[str, Any]:
    """
    Activates the kill-switch — halts new inference / scoring requests.
    Existing in-flight requests complete normally.
    """
    import time

    _kill_switch_state["active"] = True
    _kill_switch_state["reason"] = body.reason
    _kill_switch_state["activated_at"] = time.time()
    _kill_switch_state["activated_by"] = "admin"

    logger.warning(
        "KILL SWITCH ACTIVATED — reason='%s' scope='%s'",
        body.reason,
        body.scope,
    )
    return {
        "success": True,
        "active": True,
        "reason": body.reason,
        "scope": body.scope,
        "message": "Kill-switch activated — inference halted.",
    }


@router.post(
    "/deactivate",
    summary="Deactivate kill-switch",
    response_description="Kill-switch deactivated",
)
async def kill_switch_deactivate() -> Dict[str, Any]:
    """Deactivates the kill-switch — resumes normal operations."""
    _kill_switch_state["active"] = False
    _kill_switch_state["reason"] = None

    logger.info("Kill switch DEACTIVATED — operations resumed")
    return {
        "success": True,
        "active": False,
        "message": "Kill-switch deactivated — operations resumed.",
    }
