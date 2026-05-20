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

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session, select

from auth import ALGORITHM, SECRET_KEY
from db import get_session
from models import Account, AuditLog, User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def get_current_user(
    session: Session = Depends(get_session),
    token: str = Depends(oauth2_scheme),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
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
