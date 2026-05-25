"""Audit log read endpoint (writes happen inline from other routers)."""
from typing import Optional

from fastapi import APIRouter
from sqlmodel import func, select

from models import AuditLog, User

from .common import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/audit-log", tags=["audit"])


@router.get("")
def get_audit_log(
    session: SessionDep, user: CurrentUserDep,
    entity_type: Optional[str] = None,
    user_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    skip: int = 0, limit: int = 100,
):
    q = (
        select(AuditLog, User)
        .join(User, AuditLog.user_id == User.id)
        .where(AuditLog.tenant_id == user.tenant_id)
    )
    if entity_type:
        q = q.where(AuditLog.entity_type.ilike(f"%{entity_type}%"))
    if user_id:
        q = q.where(AuditLog.user_id == user_id)
    if date_from:
        q = q.where(AuditLog.timestamp >= date_from)
    if date_to:
        q = q.where(AuditLog.timestamp <= date_to + "T23:59:59")
    q = q.order_by(AuditLog.timestamp.desc())

    total_q = (
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.tenant_id == user.tenant_id)
    )
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
