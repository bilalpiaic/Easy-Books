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
import json as _json
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session, select

from auth import ALGORITHM, SECRET_KEY
from db import get_session
from models import Account, AuditLog, User


# auto_error=False so a missing Authorization header falls through to the
# cookie reader rather than raising 401 outright.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

ACCESS_COOKIE_NAME = "eb_access"


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
    token: Optional[str] = Depends(oauth2_scheme),
) -> User:
    """Resolve the authenticated user from either the Authorization: Bearer
    header (SDK / curl clients) or the HttpOnly access cookie (SPA clients).
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
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        tenant_id: int = payload.get("tenant_id")
        if email is None or tenant_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
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
