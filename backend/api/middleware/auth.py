# backend/api/middleware/auth.py
"""
Authentication Middleware (Stub)
================================

Authentication/authorization middleware for API endpoints.

Status: STUB - Not yet enabled in production.

When enabled:
  - Validates JWT/API key tokens
  - Extracts user identity
  - Checks permissions

Usage::

    from backend.api.middleware.auth import AuthMiddleware
    
    # Add to FastAPI
    app.add_middleware(AuthMiddleware)
    
    # Or use dependency
    @app.post("/explain")
    async def explain(
        request: ExplainRequest,
        auth: AuthResult = Depends(verify_token)
    ):
        ...
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api.middleware.auth")


# ==============================================================================
# Configuration
# ==============================================================================

@dataclass
class AuthConfig:
    """Authentication configuration."""
    
    enabled: bool = False
    token_header: str = "Authorization"
    api_key_header: str = "X-API-Key"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    allowed_api_keys: list = None
    
    def __post_init__(self):
        if self.allowed_api_keys is None:
            self.allowed_api_keys = []


# Global config (can be updated at runtime)
_auth_config = AuthConfig()


def configure_auth(config: Dict[str, Any]) -> None:
    """Configure authentication settings."""
    global _auth_config
    auth_settings = config.get("auth", {})
    _auth_config = AuthConfig(
        enabled=auth_settings.get("enabled", False),
        token_header=auth_settings.get("token_header", "Authorization"),
        api_key_header=auth_settings.get("api_key_header", "X-API-Key"),
        jwt_secret=auth_settings.get("jwt_secret", ""),
        jwt_algorithm=auth_settings.get("jwt_algorithm", "HS256"),
        allowed_api_keys=auth_settings.get("allowed_api_keys", []),
    )
    logger.info(f"Auth configured: enabled={_auth_config.enabled}")


# ==============================================================================
# Auth Result
# ==============================================================================

@dataclass
class AuthResult:
    """Authentication result."""
    
    authenticated: bool
    user_id: Optional[str] = None
    roles: list = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.roles is None:
            self.roles = []
        if self.metadata is None:
            self.metadata = {}


# ==============================================================================
# Token Verification (Stub)
# ==============================================================================

async def verify_token(request: Request) -> AuthResult:
    """
    Verify authentication token from request.
    
    STUB: Currently returns anonymous user when auth is disabled.
    
    Args:
        request: FastAPI request
        
    Returns:
        AuthResult with user info
        
    Raises:
        HTTPException: If auth is enabled and token is invalid
    """
    global _auth_config
    
    # If auth is disabled (dev/stub mode), return full-access bypass
    if not _auth_config.enabled:
        return AuthResult(
            authenticated=True,
            user_id="dev_bypass",
            roles=["admin"],
        )
    
    # Try API key first
    api_key = request.headers.get(_auth_config.api_key_header)
    if api_key:
        if api_key in _auth_config.allowed_api_keys:
            return AuthResult(
                authenticated=True,
                user_id=f"api_key_{api_key[:8]}",
                roles=["api_user"],
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    
    # Try JWT token
    auth_header = request.headers.get(_auth_config.token_header)
    if auth_header:
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # STUB: Token verification not implemented
            # TODO: Implement JWT verification when enabled
            logger.warning("JWT verification not implemented - rejecting")
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="JWT authentication not implemented",
            )
    
    # No auth provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


# ==============================================================================
# Auth Middleware
# ==============================================================================

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for FastAPI.
    
    STUB: Currently passes through all requests when disabled.
    
    When enabled, validates tokens and adds user info to request state.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Process request through auth middleware."""
        global _auth_config
        
        # Skip auth if disabled
        if not _auth_config.enabled:
            # Add anonymous auth info to request state
            request.state.auth = AuthResult(
                authenticated=False,
                user_id="anonymous",
                roles=["anonymous"],
            )
            return await call_next(request)
        
        # Skip auth for health endpoints
        if request.url.path in ["/health", "/healthz", "/ready"]:
            request.state.auth = AuthResult(
                authenticated=False,
                user_id="health_check",
                roles=["health"],
            )
            return await call_next(request)
        
        # Verify token
        try:
            auth_result = await verify_token(request)
            request.state.auth = auth_result
            return await call_next(request)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Auth middleware error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication error",
            )
