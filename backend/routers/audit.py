"""Audit log read endpoint (writes happen inline from other routers)."""
from typing import Optional

from fastapi import APIRouter
from sqlmodel import func, select

from models import AuditLog, User

from .common import CurrentUserDep, SessionDep
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/audit-log", tags=["audit"], dependencies=[perm_dep("audit_log")])


@router.get("")
def get_audit_log(
    session: SessionDep, user: CurrentUserDep,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    user_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    skip: int = 0, limit: int = 100,
):
    # Build the filter predicates once and apply to both the page query and the
    # count query so the reported total always matches the filtered rows.
    conditions = [AuditLog.tenant_id == user.tenant_id]
    if entity_type:
        conditions.append(AuditLog.entity_type.ilike(f"%{entity_type}%"))
    if entity_id is not None:
        conditions.append(AuditLog.entity_id == entity_id)
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if date_from:
        conditions.append(AuditLog.timestamp >= date_from)
    if date_to:
        conditions.append(AuditLog.timestamp <= date_to + "T23:59:59")

    q = (
        select(AuditLog, User)
        .join(User, AuditLog.user_id == User.id)
        .where(*conditions)
        .order_by(AuditLog.timestamp.desc())
    )
    total_q = select(func.count()).select_from(AuditLog).where(*conditions)
    total = session.exec(total_q).one()
    rows = session.exec(q.offset(skip).limit(limit)).all()
    return {
        "total": total,
        "items": [
            {
                "id": log.id,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "detail": log.detail,
                "timestamp": log.timestamp.isoformat(),
                "user_name": usr.full_name or usr.email,
                "user_id": usr.id,
            }
            for log, usr in rows
        ],
    }
