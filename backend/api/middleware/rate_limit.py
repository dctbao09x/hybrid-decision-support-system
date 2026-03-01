# backend/api/middleware/rate_limit.py
"""
Rate Limiting Middleware (Stub)
===============================

Rate limiting middleware for API endpoints.

Status: STUB - Not yet enabled in production.

When enabled:
  - Limits requests per user/IP
  - Uses sliding window algorithm
  - Returns 429 when exceeded

Usage::

    from backend.api.middleware.rate_limit import RateLimitMiddleware
    
    # Add to FastAPI
    app.add_middleware(RateLimitMiddleware)
    
    # Or use dependency
    @app.post("/explain")
    async def explain(
        request: ExplainRequest,
        _: None = Depends(check_rate_limit)
    ):
        ...
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api.middleware.rate_limit")


# ==============================================================================
# Configuration
# ==============================================================================

@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    
    enabled: bool = False
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    window_seconds: int = 60
    by_user: bool = True  # Rate limit by user_id
    by_ip: bool = True    # Rate limit by IP
    
    # Excluded paths (no rate limiting)
    excluded_paths: list = None
    
    def __post_init__(self):
        if self.excluded_paths is None:
            self.excluded_paths = ["/health", "/healthz", "/ready"]


# Global config
_rate_config = RateLimitConfig()


def configure_rate_limit(config: Dict[str, Any]) -> None:
    """Configure rate limiting settings."""
    global _rate_config
    rate_settings = config.get("rate_limit", {})
    _rate_config = RateLimitConfig(
        enabled=rate_settings.get("enabled", False),
        requests_per_minute=rate_settings.get("requests_per_minute", 60),
        requests_per_hour=rate_settings.get("requests_per_hour", 1000),
        burst_limit=rate_settings.get("burst_limit", 10),
        window_seconds=rate_settings.get("window_seconds", 60),
        by_user=rate_settings.get("by_user", True),
        by_ip=rate_settings.get("by_ip", True),
        excluded_paths=rate_settings.get("excluded_paths", ["/health", "/healthz"]),
    )
    logger.info(
        f"Rate limit configured: enabled={_rate_config.enabled}, "
        f"rpm={_rate_config.requests_per_minute}"
    )


# ==============================================================================
# Rate Limit State (In-Memory - Use Redis in production)
# ==============================================================================

@dataclass
class RateLimitState:
    """Rate limit state for a key."""
    
    request_count: int = 0
    window_start: float = 0.0
    burst_count: int = 0
    burst_start: float = 0.0


# In-memory storage (STUB - use Redis in production)
_rate_state: Dict[str, RateLimitState] = defaultdict(RateLimitState)


def _get_client_key(request: Request) -> str:
    """Get rate limit key from request."""
    parts = []
    
    if _rate_config.by_user:
        # Try to get user_id from request state or body
        user_id = getattr(request.state, "user_id", None) or "anonymous"
        parts.append(f"user:{user_id}")
    
    if _rate_config.by_ip:
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        # Check for forwarded header
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        parts.append(f"ip:{client_ip}")
    
    return "|".join(parts) if parts else "global"


def _check_limit(key: str) -> tuple[bool, Dict[str, Any]]:
    """
    Check if rate limit exceeded.
    
    Returns:
        (exceeded: bool, info: dict)
    """
    global _rate_state
    
    now = time.time()
    state = _rate_state[key]
    
    # Reset window if expired
    if now - state.window_start >= _rate_config.window_seconds:
        state.window_start = now
        state.request_count = 0
    
    # Reset burst window if expired (1 second)
    if now - state.burst_start >= 1.0:
        state.burst_start = now
        state.burst_count = 0
    
    # Check burst limit
    if state.burst_count >= _rate_config.burst_limit:
        return True, {
            "limit_type": "burst",
            "limit": _rate_config.burst_limit,
            "remaining": 0,
            "reset_at": state.burst_start + 1.0,
        }
    
    # Check per-minute limit
    if state.request_count >= _rate_config.requests_per_minute:
        return True, {
            "limit_type": "per_minute",
            "limit": _rate_config.requests_per_minute,
            "remaining": 0,
            "reset_at": state.window_start + _rate_config.window_seconds,
        }
    
    # Increment counters
    state.request_count += 1
    state.burst_count += 1
    
    return False, {
        "limit_type": "per_minute",
        "limit": _rate_config.requests_per_minute,
        "remaining": _rate_config.requests_per_minute - state.request_count,
        "reset_at": state.window_start + _rate_config.window_seconds,
    }


# ==============================================================================
# Rate Limit Check
# ==============================================================================

async def check_rate_limit(request: Request) -> None:
    """
    Check rate limit for request.
    
    STUB: Currently passes all requests when disabled.
    
    Args:
        request: FastAPI request
        
    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    global _rate_config
    
    # Skip if disabled
    if not _rate_config.enabled:
        return
    
    # Skip excluded paths
    if request.url.path in _rate_config.excluded_paths:
        return
    
    # Get client key
    key = _get_client_key(request)
    
    # Check limit
    exceeded, info = _check_limit(key)
    
    if exceeded:
        logger.warning(f"Rate limit exceeded for {key}: {info}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "limit_type": info["limit_type"],
                "limit": info["limit"],
                "retry_after": int(info["reset_at"] - time.time()),
            },
            headers={
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(info["reset_at"])),
                "Retry-After": str(int(info["reset_at"] - time.time())),
            },
        )


# ==============================================================================
# Rate Limit Middleware
# ==============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.
    
    STUB: Currently passes through all requests when disabled.
    
    When enabled, enforces request rate limits per user/IP.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Process request through rate limit middleware."""
        global _rate_config
        
        # Skip if disabled
        if not _rate_config.enabled:
            return await call_next(request)
        
        # Skip excluded paths
        if request.url.path in _rate_config.excluded_paths:
            return await call_next(request)
        
        # Check rate limit
        try:
            await check_rate_limit(request)
        except HTTPException:
            raise
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        key = _get_client_key(request)
        _, info = _check_limit(key)
        
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(int(info["reset_at"]))
        
        return response
