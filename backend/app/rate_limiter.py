from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window in-memory rate limiter with tiered limits."""

    def __init__(self):
        # Maps (identifier, endpoint_group) -> list of timestamp floats
        self._history: Dict[Tuple[str, str], List[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def _cleanup_old_entries(self, now: float, max_window: float = 60.0):
        """Purge entries older than max_window every 60 seconds to prevent memory growth."""
        if now - self._last_cleanup < 30.0:
            return
        self._last_cleanup = now
        expired_cutoff = now - max_window
        stale_keys = []
        for key, timestamps in self._history.items():
            self._history[key] = [t for t in timestamps if t > expired_cutoff]
            if not self._history[key]:
                stale_keys.append(key)
        for k in stale_keys:
            del self._history[k]

    def check_rate_limit(
        self, client_id: str, group: str, limit: int, window_seconds: float = 60.0
    ) -> Tuple[bool, int, int]:
        """Checks if a request is allowed. Returns (allowed, remaining, retry_after_seconds)."""
        now = time.time()
        self._cleanup_old_entries(now, window_seconds)
        key = (client_id, group)
        cutoff = now - window_seconds
        valid_timestamps = [t for t in self._history[key] if t > cutoff]
        self._history[key] = valid_timestamps

        if len(valid_timestamps) >= limit:
            oldest = valid_timestamps[0]
            retry_after = max(1, int(window_seconds - (now - oldest)))
            return False, 0, retry_after

        self._history[key].append(now)
        remaining = max(0, limit - len(self._history[key]))
        return True, remaining, 0


limiter = SlidingWindowRateLimiter()

# Tiered Limits: (max_requests, window_seconds)
TIER_AUTH = (12, 60.0)      # Max 12 auth attempts per minute (brute-force defense)
TIER_UPLOAD = (30, 60.0)    # Max 30 file uploads per minute
TIER_AI = (35, 60.0)        # Max 35 heavy generation/RAG requests per minute
TIER_GENERAL = (200, 60.0)  # Max 200 general API calls per minute


def get_client_identifier(request: Request) -> str:
    """Identifies client by user_id if authenticated, or falls back to client IP."""
    auth_header = request.headers.get("authorization") or request.headers.get("x-user-id")
    if auth_header:
        token = auth_header.replace("Bearer ", "").strip()
        if token:
            return f"usr:{token[:32]}"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_endpoint_tier(path: str) -> Tuple[str, int, float]:
    """Classifies path into appropriate rate limit tier."""
    if path.startswith("/api/auth/login") or path.startswith("/api/auth/signup") or path.startswith("/api/auth/reset-password"):
        return "auth", TIER_AUTH[0], TIER_AUTH[1]
    if path.startswith("/api/upload"):
        return "upload", TIER_UPLOAD[0], TIER_UPLOAD[1]
    if any(path.startswith(p) for p in [
        "/api/generate", "/api/rag/chat", "/api/chat",
        "/api/scenario/simulate", "/api/meeting/interrupter", "/api/audio/transcribe"
    ]):
        return "ai", TIER_AI[0], TIER_AI[1]
    return "general", TIER_GENERAL[0], TIER_GENERAL[1]


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Only apply rate limiting to /api endpoints; exclude static, health check endpoints, and HEAD/OPTIONS probes
        if (
            not path.startswith("/api")
            or path in ("/api/health", "/health", "/", "/ping")
            or request.method in ("HEAD", "OPTIONS")
        ):
            return await call_next(request)

        client_id = get_client_identifier(request)
        tier_name, max_reqs, window = get_endpoint_tier(path)
        allowed, remaining, retry_after = limiter.check_rate_limit(client_id, tier_name, max_reqs, window)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": f"Rate limit exceeded for {tier_name} operations. Please try again shortly.",
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_reqs),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_reqs)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
