"""FRONTEND_ORIGIN parsing for CORS and email links.

The env var is a comma-separated allow-list (see CORSMiddleware in main.py).
Email links must use a single URL — always the first listed origin.
localhost and 127.0.0.1 are treated as twins so opening the UI on either
does not CORS-fail with a generic browser "Failed to fetch".
"""
from __future__ import annotations

import os

_DEFAULT = "http://localhost:3000,http://127.0.0.1:3000"

# Capacitor WebView origins when the shell loads local www/ (not a remote
# server.url). Harmless extras when the PWA is hosted — CORS still keys off
# the page origin for a remote URL wrapper.
_CAPACITOR_ORIGINS = (
    "capacitor://localhost",
    "ionic://localhost",
    "https://localhost",
    "http://localhost",
)


def parse_frontend_origins(raw: str | None = None) -> list[str]:
    value = (raw if raw is not None else os.environ.get("FRONTEND_ORIGIN", "")).strip()
    if not value:
        value = _DEFAULT
    origins: list[str] = []
    for part in value.split(","):
        origin = part.strip().rstrip("/")
        if origin and origin not in origins:
            origins.append(origin)
    extras: list[str] = []
    for origin in origins:
        twin = _localhost_twin(origin)
        if twin and twin not in origins and twin not in extras:
            extras.append(twin)
    for cap in _CAPACITOR_ORIGINS:
        if cap not in origins and cap not in extras:
            extras.append(cap)
    return origins + extras


def frontend_public_origin(raw: str | None = None) -> str:
    """First origin — used in invite / password-reset emails."""
    origins = parse_frontend_origins(raw)
    return origins[0] if origins else "http://localhost:3000"


def _localhost_twin(origin: str) -> str | None:
    if "://localhost" in origin:
        return origin.replace("://localhost", "://127.0.0.1", 1)
    if "://127.0.0.1" in origin:
        return origin.replace("://127.0.0.1", "://localhost", 1)
    return None
