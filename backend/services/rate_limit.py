"""Global rate-limiting middleware.

Per-process, in-memory sliding-window limiter — mirrors routers/ai_chat.py's
`_RATE` pattern exactly (a deque of monotonic timestamps per identity, lazy
left-pop pruning on each check). No Redis: this app ships as an offline
Electron desktop app and a standalone script installer with no external
services, so cross-worker-exact rate limiting isn't attempted here — the
same tradeoff already accepted for the AI chat rate limiter.

Identity is resolved by decoding the bearer token / cookie inline, the same
way services/idempotency.py's `_resolve_tenant_id` already does — middleware
runs before FastAPI's dependency injection, so `CurrentUserDep` isn't
available here.
"""
import os
import time
from collections import defaultdict, deque

from fastapi import Request
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from auth import ALGORITHM, SECRET_KEY

_WINDOW_SECONDS = 60

# /api/auth/login already has its own DB-backed throttle (LoginAttempt,
# correct across workers) — counting it here too would only be redundant,
# not additive, so it's exempted rather than double-throttled.
_EXEMPT_PATHS = {
    "/api/auth/login", "/api/v1/auth/login",
    "/docs", "/openapi.json", "/api/version",
}


def _resolve_identity(request: Request) -> tuple[str, object]:
    """Returns ("auth", (tenant_id, sub)) for a decodable JWT, else
    ("anon", client_ip). API keys (eb_live_... prefix, added in a later PR)
    aren't recognized here — jwt.decode fails on them and they fall through
    to "anon", bucketing that traffic at the stricter unauthenticated limit
    until this is revisited alongside the API-key work. Not a correctness
    or security issue, just a coarser bucket than ideal in the meantime."""
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
    return "anon", (request.client.host if request.client else "unknown")


_AUTH_BUCKETS: dict[tuple, deque] = defaultdict(deque)
_ANON_BUCKETS: dict[object, deque] = defaultdict(deque)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        kind, key = _resolve_identity(request)
        if kind == "auth":
            limit = int(os.environ.get("RATE_LIMIT_AUTHENTICATED_PER_MIN", "1000"))
            bucket = _AUTH_BUCKETS[key]
        else:
            limit = int(os.environ.get("RATE_LIMIT_UNAUTHENTICATED_PER_MIN", "100"))
            bucket = _ANON_BUCKETS[key]

        now = time.monotonic()
        while bucket and now - bucket[0] > _WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= limit:
            return JSONResponse(
                {"detail": f"Rate limit exceeded ({limit}/minute). Try again shortly."},
                status_code=429,
            )
        bucket.append(now)
        return await call_next(request)
