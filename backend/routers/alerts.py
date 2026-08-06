"""Per-user in-app Alerts inbox."""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import func, select

from models import UserAlert
from services.alerts import in_app_alerts_enabled, refresh_ops_alerts

from .common import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _serialize(a: UserAlert) -> dict:
    return {
        "id": a.id,
        "kind": a.kind,
        "severity": a.severity,
        "title": a.title,
        "body": a.body,
        "href": a.href,
        "entity_type": a.entity_type,
        "entity_id": a.entity_id,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "read_at": a.read_at.isoformat() if a.read_at else None,
        "unread": a.read_at is None,
    }


@router.get("")
def list_alerts(
    session: SessionDep,
    user: CurrentUserDep,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    # Soft refresh so alerts appear without waiting for the daily sweep
    if in_app_alerts_enabled(session, user.tenant_id):
        refresh_ops_alerts(session, tenant_id=user.tenant_id)
        try:
            from services.update_notices import sync_update_notices
            sync_update_notices(session)
        except Exception:
            pass

    filters = [
        UserAlert.tenant_id == user.tenant_id,
        UserAlert.user_id == user.id,
    ]
    if unread_only:
        filters.append(UserAlert.read_at.is_(None))

    total = session.exec(
        select(func.count()).select_from(UserAlert).where(*filters)
    ).one()

    rows = session.exec(
        select(UserAlert)
        .where(*filters)
        .order_by(UserAlert.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {"total": int(total), "items": [_serialize(a) for a in rows]}


@router.get("/unread-count")
def unread_count(session: SessionDep, user: CurrentUserDep):
    if not in_app_alerts_enabled(session, user.tenant_id):
        return {"count": 0, "enabled": False}
    # Light refresh so the badge stays current without opening the panel
    refresh_ops_alerts(session, tenant_id=user.tenant_id)
    try:
        from services.update_notices import sync_update_notices
        sync_update_notices(session)
    except Exception:
        pass
    count = session.exec(
        select(func.count()).select_from(UserAlert).where(
            UserAlert.tenant_id == user.tenant_id,
            UserAlert.user_id == user.id,
            UserAlert.read_at.is_(None),
        )
    ).one()
    return {"count": int(count), "enabled": True}


@router.patch("/{alert_id}/read")
def mark_read(session: SessionDep, user: CurrentUserDep, alert_id: int):
    alert = session.get(UserAlert, alert_id)
    if not alert or alert.tenant_id != user.tenant_id or alert.user_id != user.id:
        raise HTTPException(404, "Alert not found")
    if alert.read_at is None:
        alert.read_at = datetime.utcnow()
        session.add(alert)
        session.commit()
        session.refresh(alert)
    return _serialize(alert)


@router.post("/read-all")
def mark_all_read(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(UserAlert).where(
            UserAlert.tenant_id == user.tenant_id,
            UserAlert.user_id == user.id,
            UserAlert.read_at.is_(None),
        )
    ).all()
    now = datetime.utcnow()
    for a in rows:
        a.read_at = now
        session.add(a)
    session.commit()
    return {"marked": len(rows)}
