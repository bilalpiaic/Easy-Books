"""Per-user dashboard layout store (#52 §3 / dual-home v4).

The backend treats the layout as an opaque JSON object — the widget registry
+ merge live in the frontend. Schema v4 stores two independently customized
homes under `dashboards.financial` and `dashboards.operations`.
"""
import json
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import select

from models import UserDashboardLayout

from .common import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class LayoutBody(BaseModel):
    layout: dict


@router.get("/layout")
def get_layout(session: SessionDep, user: CurrentUserDep):
    row = session.exec(
        select(UserDashboardLayout).where(
            UserDashboardLayout.tenant_id == user.tenant_id,
            UserDashboardLayout.user_id == user.id,
        )
    ).first()
    if row is None:
        return {"layout": None}
    try:
        return {"layout": json.loads(row.layout_json)}
    except (ValueError, TypeError):
        return {"layout": None}


@router.put("/layout")
def put_layout(session: SessionDep, user: CurrentUserDep, body: LayoutBody):
    # CurrentUserDep (not WriteUserDep): saving one's OWN dashboard layout is a
    # personal UI preference (Financial + Operations slices in one v4 blob),
    # so even viewer-role users may persist it.
    row = session.exec(
        select(UserDashboardLayout).where(
            UserDashboardLayout.tenant_id == user.tenant_id,
            UserDashboardLayout.user_id == user.id,
        )
    ).first()
    payload = json.dumps(body.layout)
    if row is None:
        row = UserDashboardLayout(
            tenant_id=user.tenant_id, user_id=user.id, layout_json=payload,
        )
        session.add(row)
    else:
        row.layout_json = payload
        row.updated_at = datetime.utcnow()
        session.add(row)
    session.commit()
    return {"ok": True}
