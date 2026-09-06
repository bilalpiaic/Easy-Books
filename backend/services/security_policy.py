"""Launch-time auth policy (#118 remainder).

Env flags (default off so demo/dev and pytest stay usable):

- ``REQUIRE_OWNER_TOTP`` — owners must enable authenticator 2FA. Login still
  succeeds so they can enroll; mutating API calls outside ``/api/auth`` return
  403 until ``totp_enabled``. Demo mill logins (``demo.*@easy-books.app``) are
  exempt so QA tenants keep working.
- ``ALLOW_DEMO_LOGIN`` — when false, ``demo.*@easy-books.app`` password login
  returns 403. Pair with ``SEED_DEMO=false`` on production.
"""
from __future__ import annotations

import os

from models import User


def _flag(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def require_owner_totp() -> bool:
    return _flag("REQUIRE_OWNER_TOTP", default=False)


def demo_login_allowed() -> bool:
    return _flag("ALLOW_DEMO_LOGIN", default=True)


def is_demo_email(email: str | None) -> bool:
    e = (email or "").strip().lower()
    return e.endswith("@easy-books.app") and e.startswith("demo.")


def owner_must_setup_totp(user: User) -> bool:
    if not require_owner_totp():
        return False
    if (user.role or "").lower() != "owner":
        return False
    if is_demo_email(user.email):
        return False
    return not bool(getattr(user, "totp_enabled", False))


def owner_totp_locked(user: User) -> bool:
    """True when this owner is not allowed to turn 2FA off."""
    if not require_owner_totp():
        return False
    if (user.role or "").lower() != "owner":
        return False
    if is_demo_email(user.email):
        return False
    return True
