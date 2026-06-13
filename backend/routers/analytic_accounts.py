"""Analytic accounts (cost centers, projects, departments). IAS 1 segment reporting."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import AnalyticAccount
from routers.common import SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/analytic-accounts", tags=["analytic-accounts"])


class AnalyticCreate(BaseModel):
    code: str
    name: str
    type: str = "cost_center"  # cost_center | project | department


class AnalyticUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("")
def list_analytic_accounts(
    session: SessionDep, user: WriteUserDep, skip: int = 0, limit: int = 100
):
    q = select(AnalyticAccount).where(AnalyticAccount.tenant_id == user.tenant_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(AnalyticAccount.code).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": items}


@router.get("/{aa_id}")
def get_analytic_account(session: SessionDep, user: WriteUserDep, aa_id: int):
    aa = session.exec(
        select(AnalyticAccount).where(
            AnalyticAccount.id == aa_id, AnalyticAccount.tenant_id == user.tenant_id
        )
    ).first()
    if not aa:
        raise HTTPException(404)
    return aa


@router.post("", status_code=201)
def create_analytic_account(session: SessionDep, user: WriteUserDep, body: AnalyticCreate):
    if body.type not in ("cost_center", "project", "department"):
        raise HTTPException(400, "type must be cost_center, project, or department")
    existing = session.exec(
        select(AnalyticAccount).where(
            AnalyticAccount.tenant_id == user.tenant_id,
            AnalyticAccount.code == body.code,
        )
    ).first()
    if existing:
        raise HTTPException(409, f"Analytic account code '{body.code}' already exists")
    aa = AnalyticAccount(tenant_id=user.tenant_id, **body.model_dump())
    session.add(aa)
    log_audit(session, user, "CREATE", "analytic_account", None, {"code": body.code})
    session.commit()
    session.refresh(aa)
    return aa


@router.put("/{aa_id}")
def update_analytic_account(
    session: SessionDep, user: WriteUserDep, aa_id: int, body: AnalyticUpdate
):
    aa = session.exec(
        select(AnalyticAccount).where(
            AnalyticAccount.id == aa_id, AnalyticAccount.tenant_id == user.tenant_id
        )
    ).first()
    if not aa:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(aa, k, v)
    session.add(aa)
    log_audit(session, user, "UPDATE", "analytic_account", aa_id, {"code": aa.code})
    session.commit()
    session.refresh(aa)
    return aa
