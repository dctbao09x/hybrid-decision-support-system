# backend/api/middleware/telemetry.py
"""
Route Telemetry Middleware (Prompt 3)
======================================
Logs every HTTP request with:
  - route (path template)
  - method
  - payload size / first 512 bytes of body
  - duration (ms)
  - status code

Attached to the FastAPI app as a plain @app.middleware("http") function,
so it runs for ALL routers.

Body consumption safety:
  FastAPI streams the body via `request.body()`.  After we read and log it
  we call `app.state` to stash the bytes so downstream handlers can still
  read them through `Request.body()` — we do this via a patched receive
  callable, which is the canonical safe approach for Starlette.

No crash guarantee:
  All body and JSON parsing is guarded with try/except.  The request is
  always forwarded to the next handler regardless.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("api.telemetry")


# ─── Payload size config ───────────────────────────────────────────────────────
MAX_BODY_LOG_BYTES: int = 512   # truncate at 512 chars to keep logs readable
SKIP_PATHS: frozenset[str] = frozenset({"/metrics", "/favicon.ico"})


class RouteTelemetryMiddleware:
    """
    ASGI middleware — wraps receive so request body is never lost.

    For every request it emits a single structured log line:
        TELEMETRY | <method> <path> | status=<N> | <dur_ms>ms | body=<N>B

    The body is logged as a compact JSON snippet (first MAX_BODY_LOG_BYTES
    bytes) or as raw text for non-JSON payloads.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # ── Build a Request view of the incoming scope ──────────────────────
        request = Request(scope, receive)
        path: str = scope.get("path", "")

        # Skip noisy paths
        if path in SKIP_PATHS or path.startswith("/static"):
            await self.app(scope, receive, send)
            return

        # ── Safely buffer the request body ──────────────────────────────────
        raw_body: bytes = b""
        try:
            raw_body = await request.body()
        except Exception:
            pass  # body unavailable — proceed without logging it

        # Patch receive so downstream can still read the body
        body_iterator = iter([raw_body])
        body_consumed = False

        async def patched_receive() -> Message:
            nonlocal body_consumed
            if not body_consumed:
                body_consumed = True
                return {"type": "http.request", "body": raw_body, "more_body": False}
            # After the first read, return a disconnect message
            original = await receive()
            return original

        # ── Capture the response status without buffering response body ─────
        response_status: int = 0

        async def patched_send(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message.get("status", 0)
            await send(message)

        start = time.perf_counter()
        request_id = str(uuid.uuid4())[:8]

        try:
            await self.app(scope, patched_receive, patched_send)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000

            # ── Build payload summary ────────────────────────────────────────
            body_snippet = _summarise_body(raw_body)
            method = scope.get("method", "?")

            logger.info(
                "TELEMETRY | req=%s | %s %s | status=%d | dur=%.1fms | body=%dB%s",
                request_id,
                method,
                path,
                response_status,
                duration_ms,
                len(raw_body),
                f" | payload={body_snippet}" if body_snippet else "",
            )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _summarise_body(raw: bytes) -> str:
    """
    Returns a compact human-readable snippet of the payload.
    Returns empty string for empty bodies.
    """
    if not raw:
        return ""
    # Try JSON first
    try:
        obj = json.loads(raw)
        snippet = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        if len(snippet) > MAX_BODY_LOG_BYTES:
            snippet = snippet[:MAX_BODY_LOG_BYTES] + "…"
        return snippet
    except (json.JSONDecodeError, ValueError):
        pass
    # Plain text / form data
    try:
        text = raw.decode("utf-8", errors="replace")
        if len(text) > MAX_BODY_LOG_BYTES:
            return text[:MAX_BODY_LOG_BYTES] + "…"
        return text
    except Exception:
        return f"<binary {len(raw)}B>"
