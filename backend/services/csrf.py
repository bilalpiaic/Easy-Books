"""Double-submit-cookie CSRF protection.

When a request mutates state AND authenticates via the HttpOnly access
cookie, the client must echo the value of the non-HttpOnly `eb_csrf`
cookie in an `X-CSRF-Token` header. The middleware rejects mismatches
with 403.

Bearer-token clients (SDK / curl) are exempt — they don't have ambient
authority that a malicious origin could exploit, since CSRF relies on
the browser auto-sending cookies.

The `eb_csrf` cookie is set by /api/auth/login; logout clears it.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}

# Endpoints exempt from CSRF: the public auth endpoints that set the
# cookies in the first place, and the logout endpoint (idempotent).
_EXEMPT_PATHS = {
    "/api/auth/signup", "/api/v1/auth/signup",
    "/api/auth/login", "/api/v1/auth/login",
    "/api/auth/logout", "/api/v1/auth/logout",
    "/api/auth/forgot-password", "/api/v1/auth/forgot-password",
    "/api/auth/reset-password", "/api/v1/auth/reset-password",
}

# Magic-link portal is authenticated by the URL token, not cookies. Staff
# who mint a link while logged in would otherwise fail CSRF on pay/dispute.
_EXEMPT_PREFIXES = (
    "/api/portal/",
    "/api/v1/portal/",
    "/api/stripe/webhook",
    "/api/v1/stripe/webhook",
)


class CsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in _MUTATING:
            return await call_next(request)
        path = request.url.path
        if path in _EXEMPT_PATHS or any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)
        # If the caller sent an Authorization header we skip CSRF — they
        # can't be a browser-cookie-style victim.
        if request.headers.get("authorization", "").lower().startswith("bearer "):
            return await call_next(request)
        # Cookie-authenticated mutation → require matching CSRF header.
        access = request.cookies.get("eb_access")
        if not access:
            # No cookie auth either — let downstream auth dep reject it
            return await call_next(request)
        cookie_csrf = request.cookies.get("eb_csrf")
        header_csrf = request.headers.get("x-csrf-token")
        if not cookie_csrf or not header_csrf or cookie_csrf != header_csrf:
            return JSONResponse(
                {"detail": "CSRF token missing or invalid"},
                status_code=403,
            )
        return await call_next(request)
