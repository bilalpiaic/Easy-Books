"""Analytic dimension types (#260) — up to 3 per tenant (CC / PROJ / LOC …)."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import func, select

from models import AnalyticAccount, AnalyticDimension
from routers.common import SessionDep, WriteUserDep, log_audit
from services.analytics import ensure_legacy_dimension
from services.permissions import perm_dep

router = APIRouter(
    prefix="/api/analytic-dimensions",
    tags=["analytic-dimensions"],
    dependencies=[perm_dep("analytic_accounts")],
)

_MAX_DIMENSIONS = 3


class DimensionCreate(BaseModel):
    code: str
    name: str
    required: bool = False
    sort_order: Optional[int] = None  # auto-assign next free slot if omitted
    is_active: bool = True


class DimensionUpdate(BaseModel):
    name: Optional[str] = None
    required: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(default=None, ge=0, le=2)


def _serialize(d: AnalyticDimension) -> dict:
    return {
        "id": d.id,
        "code": d.code,
        "name": d.name,
        "required": d.required,
        "sort_order": d.sort_order,
        "is_active": d.is_active,
    }


@router.get("")
def list_dimensions(session: SessionDep, user: WriteUserDep):
    dims = ensure_legacy_dimension(session, user.tenant_id)
    if dims:
        session.commit()
    if not dims:
        dims = list(
            session.exec(
                select(AnalyticDimension)
                .where(AnalyticDimension.tenant_id == user.tenant_id)
                .order_by(AnalyticDimension.sort_order)
            ).all()
        )
    return {"total": len(dims), "items": [_serialize(d) for d in dims]}


@router.post("", status_code=201)
def create_dimension(session: SessionDep, user: WriteUserDep, body: DimensionCreate):
    ensure_legacy_dimension(session, user.tenant_id)
    count = session.exec(
        select(func.count()).select_from(AnalyticDimension).where(
            AnalyticDimension.tenant_id == user.tenant_id,
        )
    ).one()
    if count >= _MAX_DIMENSIONS:
        raise HTTPException(400, f"Maximum of {_MAX_DIMENSIONS} dimension types per tenant")

    code = body.code.strip().upper()
    if not code:
        raise HTTPException(400, "code is required")
    if session.exec(
        select(AnalyticDimension).where(
            AnalyticDimension.tenant_id == user.tenant_id,
            AnalyticDimension.code == code,
        )
    ).first():
        raise HTTPException(409, f"Dimension code '{code}' already exists")

    used = {
        d.sort_order
        for d in session.exec(
            select(AnalyticDimension).where(AnalyticDimension.tenant_id == user.tenant_id)
        ).all()
    }
    if body.sort_order is not None:
        sort_order = body.sort_order
        if sort_order < 0 or sort_order > 2:
            raise HTTPException(400, "sort_order must be 0, 1, or 2")
        if sort_order in used:
            raise HTTPException(400, f"sort_order {sort_order} is already taken")
    else:
        free = [i for i in range(3) if i not in used]
        if not free:
            raise HTTPException(400, f"Maximum of {_MAX_DIMENSIONS} dimension types per tenant")
        sort_order = free[0]

    dim = AnalyticDimension(
        tenant_id=user.tenant_id,
        code=code,
        name=body.name.strip(),
        required=body.required,
        sort_order=sort_order,
        is_active=body.is_active,
    )
    session.add(dim)
    log_audit(session, user, "CREATE", "analytic_dimension", None, {"code": code})
    session.commit()
    session.refresh(dim)
    return _serialize(dim)


@router.put("/{dim_id}")
def update_dimension(
    session: SessionDep, user: WriteUserDep, dim_id: int, body: DimensionUpdate
):
    dim = session.exec(
        select(AnalyticDimension).where(
            AnalyticDimension.id == dim_id,
            AnalyticDimension.tenant_id == user.tenant_id,
        )
    ).first()
    if not dim:
        raise HTTPException(404)
    data = body.model_dump(exclude_none=True)
    if "sort_order" in data:
        clash = session.exec(
            select(AnalyticDimension).where(
                AnalyticDimension.tenant_id == user.tenant_id,
                AnalyticDimension.sort_order == data["sort_order"],
                AnalyticDimension.id != dim_id,
            )
        ).first()
        if clash:
            raise HTTPException(400, f"sort_order {data['sort_order']} is already taken")
    for k, v in data.items():
        setattr(dim, k, v)
    session.add(dim)
    log_audit(session, user, "UPDATE", "analytic_dimension", dim_id, {"code": dim.code})
    session.commit()
    session.refresh(dim)
    return _serialize(dim)


@router.delete("/{dim_id}")
def delete_dimension(session: SessionDep, user: WriteUserDep, dim_id: int):
    dim = session.exec(
        select(AnalyticDimension).where(
            AnalyticDimension.id == dim_id,
            AnalyticDimension.tenant_id == user.tenant_id,
        )
    ).first()
    if not dim:
        raise HTTPException(404)
    n = session.exec(
        select(func.count()).select_from(AnalyticAccount).where(
            AnalyticAccount.dimension_id == dim_id,
        )
    ).one()
    if n:
        raise HTTPException(
            400,
            f"Cannot delete dimension with {n} analytic value(s); reassign or deactivate instead",
        )
    session.delete(dim)
    log_audit(session, user, "DELETE", "analytic_dimension", dim_id, {"code": dim.code})
    session.commit()
    return {"ok": True}
