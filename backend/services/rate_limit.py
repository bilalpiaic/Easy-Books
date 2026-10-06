"""Global rate-limiting middleware.

Sliding-window limiter: Redis when REDIS_URL is set (shared across replicas),
in-memory fallback for desktop. Redis errors fail open (#427). Login keeps
its own DB-backed throttle.
"""
import os
from collections import defaultdict, deque

from fastapi import Request
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from auth import ALGORITHM, SECRET_KEY
from services.client_ip import client_ip
from services.sliding_window import allow

_WINDOW_SECONDS = 60

# /api/auth/login already has its own DB-backed throttle (LoginAttempt,
# correct across workers) — counting it here too would only be redundant,
# not additive, so it's exempted rather than double-throttled.
_EXEMPT_PATHS = {
    "/api/auth/login", "/api/v1/auth/login",
    "/docs", "/openapi.json", "/api/version",
    "/api/health", "/api/health/live", "/api/health/ready",
}


def _exempt(path: str) -> bool:
    if path in _EXEMPT_PATHS:
        return True
    return path.startswith("/api/health")


def _resolve_identity(request: Request) -> tuple[str, object]:
    """Returns ("auth", (tenant_id, sub)) for a decodable JWT, else
    ("anon", client_ip)."""
    auth_header = request.headers.get("authorization", "")
    token = None
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("eb_access")
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            tenant_id = payload.get("tenant_id")
            sub = payload.get("sub")
            if tenant_id is not None and sub is not None:
                return "auth", (tenant_id, sub)
        except JWTError:
            pass
    return "anon", client_ip(request)


_AUTH_BUCKETS: dict[tuple, deque] = defaultdict(deque)
_ANON_BUCKETS: dict[object, deque] = defaultdict(deque)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if _exempt(request.url.path):
            return await call_next(request)

        kind, key = _resolve_identity(request)
        if kind == "auth":
            limit = int(os.environ.get("RATE_LIMIT_AUTHENTICATED_PER_MIN", "1000"))
            memory = _AUTH_BUCKETS
        else:
            limit = int(os.environ.get("RATE_LIMIT_UNAUTHENTICATED_PER_MIN", "100"))
            memory = _ANON_BUCKETS

        if not allow(kind, key, limit=limit, window=_WINDOW_SECONDS, memory=memory):
            return JSONResponse(
                {"detail": f"Rate limit exceeded ({limit}/minute). Try again shortly."},
                status_code=429,
            )
        return await call_next(request)
