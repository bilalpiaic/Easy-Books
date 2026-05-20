"""Audit log read endpoint (writes happen inline from other routers)."""
from typing import Optional

from fastapi import APIRouter
from sqlmodel import select

from models import AuditLog, User

from .common import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/audit-log", tags=["audit"])


@router.get("")
def get_audit_log(
    session: SessionDep, user: CurrentUserDep,
    entity_type: Optional[str] = None, skip: int = 0, limit: int = 50,
):
    q = (
        select(AuditLog, User)
        .join(User, AuditLog.user_id == User.id)
        .where(AuditLog.tenant_id == user.tenant_id)
    )
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    q = q.order_by(AuditLog.timestamp.desc())
    total = len(session.exec(q).all())
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
            }
            for log, usr in rows
        ],
    }
