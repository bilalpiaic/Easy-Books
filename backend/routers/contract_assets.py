"""Contract assets + IFRS 15 contract balances report (#259)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import func, select

from models import ContractAsset
from routers.common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from services.ifrs15 import (
    certify_contract_asset,
    contract_balances_report,
    settle_contract_asset_standalone,
)
from services.permissions import perm_dep

router = APIRouter(tags=["contract-assets"])


class CertifyIn(BaseModel):
    customer_id: int
    amount: float
    certify_date: str
    description: str
    revenue_account_id: Optional[int] = None
    notes: Optional[str] = None


class SettleIn(BaseModel):
    invoice_id: int


def _ca_out(ca: ContractAsset) -> dict:
    rem = float(ca.amount or 0) - float(ca.recognised_amount or 0)
    return {
        "id": ca.id,
        "customer_id": ca.customer_id,
        "description": ca.description,
        "certify_date": ca.certify_date,
        "amount": float(ca.amount or 0),
        "recognised_amount": float(ca.recognised_amount or 0),
        "remaining": rem,
        "revenue_account_id": ca.revenue_account_id,
        "asset_account_id": ca.asset_account_id,
        "status": ca.status,
        "transaction_id": ca.transaction_id,
        "invoice_id": ca.invoice_id,
        "notes": ca.notes,
        "created_at": ca.created_at,
    }


@router.get(
    "/api/reports/contract-balances",
    dependencies=[perm_dep("deferred_revenue", "view")],
)
def report_contract_balances(session: SessionDep, user: CurrentUserDep):
    """Contract asset (unbilled) + contract liability (unearned) by customer."""
    return contract_balances_report(session, user.tenant_id)


@router.get("/api/contract-assets", dependencies=[perm_dep("deferred_revenue", "view")])
def list_contract_assets(
    session: SessionDep,
    user: CurrentUserDep,
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
):
    q = select(ContractAsset).where(ContractAsset.tenant_id == user.tenant_id)
    if status:
        q = q.where(ContractAsset.status == status)
    if customer_id:
        q = q.where(ContractAsset.customer_id == customer_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(ContractAsset.id.desc()).offset(skip).limit(limit)  # type: ignore[attr-defined]
    ).all()
    return {"total": total, "items": [_ca_out(x) for x in items]}


@router.post(
    "/api/contract-assets",
    status_code=201,
    dependencies=[perm_dep("deferred_revenue", "edit")],
)
def create_contract_asset(session: SessionDep, user: WriteUserDep, body: CertifyIn):
    ca = certify_contract_asset(
        session, user,
        customer_id=body.customer_id,
        amount=body.amount,
        certify_date=body.certify_date,
        description=body.description,
        revenue_account_id=body.revenue_account_id,
        notes=body.notes,
    )
    log_audit(
        session, user, "CREATE", "contract_asset", ca.id,
        {"amount": str(ca.amount), "customer_id": ca.customer_id},
    )
    session.commit()
    session.refresh(ca)
    return _ca_out(ca)


@router.post(
    "/api/contract-assets/{ca_id}/settle",
    dependencies=[perm_dep("deferred_revenue", "edit")],
)
def settle_contract_asset(
    session: SessionDep, user: WriteUserDep, ca_id: int, body: SettleIn,
):
    """Reclassify remaining CA: Dr Revenue / Cr 1140; link invoice."""
    ca = settle_contract_asset_standalone(session, user, ca_id, body.invoice_id)
    log_audit(
        session, user, "UPDATE", "contract_asset", ca.id,
        {"action": "settle", "invoice_id": body.invoice_id},
    )
    session.commit()
    session.refresh(ca)
    return _ca_out(ca)
