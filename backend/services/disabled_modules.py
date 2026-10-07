"""Server-wide module kill switch (#430).

``DISABLED_MODULES`` is a comma-separated list of ``MODULE_REGISTRY`` ids.
SaaS production/staging sets ``healthcare`` so those APIs 404 even when a
tenant still has the module entitled. Desktop/on-prem leave the env empty.
"""
from __future__ import annotations

import os

_MODULE_PREFIXES: dict[str, tuple[str, ...]] = {
    "healthcare": (
        "/api/healthcare",
        "/api/v1/healthcare",
    ),
}


def disabled_modules() -> set[str]:
    raw = os.environ.get("DISABLED_MODULES") or ""
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


def is_module_disabled(module_id: str | None) -> bool:
    if not module_id:
        return False
    return module_id.strip().lower() in disabled_modules()


def disabled_path_prefixes() -> list[str]:
    out: list[str] = []
    disabled = disabled_modules()
    for mid, prefixes in _MODULE_PREFIXES.items():
        if mid in disabled:
            out.extend(prefixes)
    return out


def path_hits_disabled_module(path: str) -> bool:
    for prefix in disabled_path_prefixes():
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False
