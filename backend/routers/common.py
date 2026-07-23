"""
Shared dependencies for all routers.

Anything an endpoint needs from "outside the request" lives here so each
router stays focused on its own domain logic:
  - SessionDep / CurrentUserDep — the two annotations every protected
    endpoint takes (DB session + authenticated user).
  - log_audit — single source of truth for writing AuditLog rows.
  - _get_or_create_account — auto-resolves a CoA account by code, used by
    the auto-posting endpoints to seed default accounts when the tenant
    hasn't picked one explicitly.

Keeping these out of any individual router prevents the import cycles that
would otherwise force everything back into one mega-file.
"""
import hashlib as _hashlib
import json as _json
from datetime import datetime as _datetime
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session, select

from auth import ALGORITHM, SECRET_KEY
from db import get_session
from models import Account, ApiKey, AuditLog, RevokedToken, SequenceCounter, Settings, User


# auto_error=False so a missing Authorization header falls through to the
# cookie reader rather than raising 401 outright.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

ACCESS_COOKIE_NAME = "eb_access"

# Machine-to-machine API keys (#113) share the Authorization: Bearer header
# with JWTs; this static prefix disambiguates them without ever attempting
# (and failing) a jwt.decode on a raw key.
API_KEY_PREFIX = "eb_live_"


def _user_from_api_key(session: Session, token: str, credentials_exception) -> User:
    """Resolve an eb_live_ key to its owning User. The key authenticates AS
    that user — role checks, permission gates, and audit attribution behave
    exactly as if they had presented a JWT."""
    key_hash = _hashlib.sha256(token.encode()).hexdigest()
    api_key = session.exec(select(ApiKey).where(ApiKey.key_hash == key_hash)).first()
    if (
        api_key is None
        or not api_key.is_active
        or (api_key.expires_at is not None and api_key.expires_at < _datetime.utcnow())
    ):
        raise credentials_exception
    user = session.get(User, api_key.user_id)
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact an administrator.",
        )
    api_key.last_used = _datetime.utcnow()
    session.add(api_key)
    session.commit()
    return user


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
    token: Optional[str] = Depends(oauth2_scheme),
) -> User:
    """Resolve the authenticated user from the Authorization: Bearer header
    (a JWT or an eb_live_ API key — SDK / curl clients) or the HttpOnly
    access cookie (SPA clients).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        raise credentials_exception
    if token.startswith(API_KEY_PREFIX):
        return _user_from_api_key(session, token, credentials_exception)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        tenant_id: int = payload.get("tenant_id")
        if email is None or tenant_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Logout inserts the token's jti into RevokedToken (#113) — reject a
    # revoked token on every request, not just at natural expiry. Tokens
    # minted before jti existed carry none and skip the check (no forced
    # re-login on deploy).
    jti = payload.get("jti")
    if jti is not None:
        revoked = session.exec(
            select(RevokedToken).where(RevokedToken.jti == jti)
        ).first()
        if revoked is not None:
            raise credentials_exception

    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        # A deactivated user is locked out immediately, even with a still-valid
        # token — the check happens on every request, not just at login.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact an administrator.",
        )
    # Active-tenant claim must match DB (#220). Stale tokens after a switch
    # are rejected until the client uses the reminted token.
    if int(tenant_id) != int(user.tenant_id):
        raise credentials_exception
    return user


SessionDep = Annotated[Session, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ── RBAC ─────────────────────────────────────────────────────────────────────
# Higher index = more privilege. require_min_role picks the floor.
_ROLE_ORDER = ("viewer", "accountant", "admin", "owner")


def _rank(role: str) -> int:
    try:
        return _ROLE_ORDER.index(role)
    except ValueError:
        return -1


def require_min_role(min_role: str):
    """Dependency factory: returns the current user iff their role rank is
    at least `min_role`. Raises 403 otherwise. Use as a Depends() override of
    CurrentUserDep on endpoints that mutate financial data.
    """
    floor = _rank(min_role)

    def _dep(user: User = Depends(get_current_user)) -> User:
        if _rank(user.role) < floor:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' lacks permission (need '{min_role}+')",
            )
        return user

    return _dep


# Convenience deps — most write endpoints want accountant+, admin endpoints
# want admin+.
WriteUserDep = Annotated[User, Depends(require_min_role("accountant"))]
AdminUserDep = Annotated[User, Depends(require_min_role("admin"))]


def log_audit(
    session: Session,
    user: User,
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    detail: Optional[dict] = None,
) -> None:
    """Append a single AuditLog row. Caller is responsible for commit."""
    session.add(
        AuditLog(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=_json.dumps(detail) if detail else None,
        )
    )


def next_number(
    session: Session, tenant_id: int, name: str, prefix: str, *,
    width: int = 4, fmt: Optional[str] = None,
) -> str:
    """Atomic per-tenant document numbering.

    Reads (or creates) the SequenceCounter row with `SELECT … FOR UPDATE`
    so concurrent callers serialise on the same row. Returns a formatted
    string like 'INV-0007' and advances the counter.

    Caller is responsible for commit; the increment is part of the same
    transaction as the document being numbered, so a rollback releases the
    consumed value.

    If `fmt` is provided it is a template string supporting tokens:
      {prefix}    → the prefix value (e.g. "INV")
      {seq:04d}   → zero-padded sequence number (width in the token overrides `width`)
      {seq}       → sequence number with default width
      {YYYY}      → 4-digit year
      {MM}        → 2-digit month
    """
    import re
    from datetime import date as _date

    row = session.exec(
        select(SequenceCounter)
        .where(
            SequenceCounter.tenant_id == tenant_id,
            SequenceCounter.name == name,
        )
        .with_for_update()
    ).first()
    if row is None:
        row = SequenceCounter(tenant_id=tenant_id, name=name, next_value=1)
        session.add(row)
        session.flush()
    value = row.next_value
    row.next_value = value + 1
    session.add(row)
    session.flush()

    if fmt:
        now = _date.today()
        result = fmt.replace("{prefix}", prefix)
        result = result.replace("{YYYY}", str(now.year))
        result = result.replace("{MM}", f"{now.month:02d}")
        # {seq:04d} or {seq:Nd}
        result = re.sub(
            r"\{seq(?::(\d+)d)?\}",
            lambda m: f"{value:0{int(m.group(1)) if m.group(1) else width}d}",
            result,
        )
        return result
    return f"{prefix}-{value:0{width}d}"


def mark_onboarding_step(session: Session, tenant_id: int, step: str) -> None:
    """Set a single onboarding step to True without committing (caller commits)."""
    import json as _j
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == "onboarding_steps")
    ).first()
    steps: dict = {}
    if row and row.value:
        try:
            steps = _j.loads(row.value)
        except Exception:
            steps = {}
    if steps.get(step):
        return
    steps[step] = True
    if row:
        row.value = _j.dumps(steps)
    else:
        row = Settings(tenant_id=tenant_id, key="onboarding_steps", value=_j.dumps(steps))
    session.add(row)


def get_default_account(
    session: Session,
    tenant_id: int,
    setting_key: str,
    fallback_code: str,
    fallback_name: str,
    fallback_type: str,
) -> Account:
    """Resolve a default GL account: tenant setting → code lookup → auto-create.

    Checks Settings[setting_key] for the tenant; if it contains a valid account
    code, uses that. Otherwise falls back to `fallback_code`.
    """
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == tenant_id,
            Settings.key == setting_key,
        )
    ).first()
    code = row.value if (row and row.value) else fallback_code
    return get_or_create_account(session, tenant_id, code, fallback_name, fallback_type)


def get_or_create_account(
    session: Session, tenant_id: int, code: str, name: str, acct_type: str
) -> Account:
    """Look up a CoA account by code; create it on demand if missing.

    Used by the auto-posting flows (invoice/bill/payment) so that a fresh
    tenant doesn't have to pre-configure every default account before the
    first sale.
    """
    acc = session.exec(
        select(Account).where(Account.tenant_id == tenant_id, Account.code == code)
    ).first()
    if not acc:
        acc = Account(code=code, name=name, type=acct_type, tenant_id=tenant_id)
        session.add(acc)
        session.flush()
    return acc
