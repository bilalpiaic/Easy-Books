"""Scrap/damage reason-code catalog for production orders (#224)."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import ProductionScrap, ScrapReason
from services.permissions import perm_dep

from .common import CurrentUserDep, SessionDep, WriteUserDep

router = APIRouter(prefix="/api/scrap-reasons", tags=["scrap-reasons"])


class ReasonIn(BaseModel):
    code: str
    name: str
    is_active: bool = True


class ReasonUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None


def _serialise(r: ScrapReason) -> dict:
    return r.model_dump()


@router.get("")
def list_reasons(
    session: SessionDep,
    user: CurrentUserDep,
    active_only: bool = False,
):
    q = select(ScrapReason).where(ScrapReason.tenant_id == user.tenant_id)
    if active_only:
        q = q.where(ScrapReason.is_active == True)  # noqa: E712
    rows = session.exec(q.order_by(ScrapReason.code)).all()
    return {"items": [_serialise(r) for r in rows]}


@router.post("", status_code=201, dependencies=[perm_dep("production_orders", "edit")])
def create_reason(session: SessionDep, user: WriteUserDep, body: ReasonIn):
    code = body.code.strip().upper()
    name = body.name.strip()
    if not code or not name:
        raise HTTPException(400, "code and name are required")
    exists = session.exec(
        select(ScrapReason).where(
            ScrapReason.tenant_id == user.tenant_id,
            ScrapReason.code == code,
        )
    ).first()
    if exists:
        raise HTTPException(400, f"Reason code '{code}' already exists")
    row = ScrapReason(
        tenant_id=user.tenant_id,
        code=code,
        name=name,
        is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialise(row)


@router.put("/{reason_id}", dependencies=[perm_dep("production_orders", "edit")])
def update_reason(
    session: SessionDep, user: WriteUserDep, reason_id: int, body: ReasonUpdate,
):
    row = session.get(ScrapReason, reason_id)
    if not row or row.tenant_id != user.tenant_id:
        raise HTTPException(404, "Reason not found")
    data = body.model_dump(exclude_none=True)
    if "code" in data:
        code = data["code"].strip().upper()
        if not code:
            raise HTTPException(400, "code cannot be empty")
        clash = session.exec(
            select(ScrapReason).where(
                ScrapReason.tenant_id == user.tenant_id,
                ScrapReason.code == code,
                ScrapReason.id != reason_id,
            )
        ).first()
        if clash:
            raise HTTPException(400, f"Reason code '{code}' already exists")
        data["code"] = code
    if "name" in data:
        data["name"] = data["name"].strip()
        if not data["name"]:
            raise HTTPException(400, "name cannot be empty")
    for k, v in data.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialise(row)


@router.delete("/{reason_id}", dependencies=[perm_dep("production_orders", "edit")])
def delete_reason(session: SessionDep, user: WriteUserDep, reason_id: int):
    row = session.get(ScrapReason, reason_id)
    if not row or row.tenant_id != user.tenant_id:
        raise HTTPException(404, "Reason not found")
    used = session.exec(
        select(ProductionScrap).where(ProductionScrap.reason_id == reason_id)
    ).first()
    if used:
        raise HTTPException(
            400,
            "Reason is used on scrap records — deactivate it instead of deleting",
        )
    session.delete(row)
    session.commit()
    return {"ok": True}
