"""Fixed asset register and depreciation runs. IAS 16 / IAS 38."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import DepreciationEntry, FixedAsset
from routers.common import SessionDep, WriteUserDep, log_audit
from services.depreciation import compute_depreciation
from services.money import D, money
from services.posting import EntryInput, post_transaction

router = APIRouter(prefix="/api/assets", tags=["assets"])


class AssetCreate(BaseModel):
    name: str
    code: Optional[str] = None
    asset_account_id: int
    accum_depr_account_id: int
    depr_expense_account_id: int
    acquisition_date: str
    acquisition_cost: Decimal
    salvage_value: Decimal = Decimal("0")
    useful_life_months: int
    method: str = "straight_line"


class DepreciationRun(BaseModel):
    depreciation_date: str


@router.get("")
def list_assets(session: SessionDep, user: WriteUserDep, skip: int = 0, limit: int = 50):
    q = select(FixedAsset).where(
        FixedAsset.tenant_id == user.tenant_id,
        FixedAsset.is_disposed == False,  # noqa: E712
    )
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(FixedAsset.acquisition_date.desc()).offset(skip).limit(limit)).all()
    return {"total": total, "items": items}


@router.get("/{asset_id}")
def get_asset(session: SessionDep, user: WriteUserDep, asset_id: int):
    asset = session.exec(
        select(FixedAsset).where(
            FixedAsset.id == asset_id, FixedAsset.tenant_id == user.tenant_id
        )
    ).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    entries = session.exec(
        select(DepreciationEntry).where(DepreciationEntry.asset_id == asset_id)
        .order_by(DepreciationEntry.depreciation_date.desc())
    ).all()
    return {**asset.model_dump(), "depreciation_entries": [e.model_dump() for e in entries]}


@router.post("", status_code=201)
def create_asset(session: SessionDep, user: WriteUserDep, body: AssetCreate):
    if body.method not in ("straight_line", "reducing_balance"):
        raise HTTPException(400, "method must be 'straight_line' or 'reducing_balance'")

    asset = FixedAsset(
        tenant_id=user.tenant_id,
        book_value=body.acquisition_cost,
        **body.model_dump(),
    )
    session.add(asset)
    log_audit(session, user, "CREATE", "fixed_asset", None, {"name": body.name})
    session.commit()
    session.refresh(asset)
    return asset


@router.post("/{asset_id}/depreciate")
def run_depreciation(
    session: SessionDep, user: WriteUserDep, asset_id: int, body: DepreciationRun
):
    asset = session.exec(
        select(FixedAsset).where(
            FixedAsset.id == asset_id, FixedAsset.tenant_id == user.tenant_id
        )
    ).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    if asset.is_disposed:
        raise HTTPException(400, "Cannot depreciate a disposed asset")

    charge = compute_depreciation(
        acquisition_cost=asset.acquisition_cost,
        salvage_value=asset.salvage_value,
        useful_life_months=asset.useful_life_months,
        accumulated_depreciation=asset.accumulated_depreciation,
        method=asset.method,
    )
    if charge <= D("0"):
        return {"message": "Asset fully depreciated", "depreciation_amount": 0}

    txn = post_transaction(
        session,
        user,
        date=body.depreciation_date,
        description=f"Depreciation — {asset.name}",
        entries=[
            EntryInput(account_id=asset.depr_expense_account_id, debit=charge),
            EntryInput(account_id=asset.accum_depr_account_id, credit=charge),
        ],
        audit_entity_type="fixed_asset",
        audit_detail={"asset_id": asset_id, "charge": str(charge)},
    )

    session.add(
        DepreciationEntry(
            tenant_id=user.tenant_id,
            asset_id=asset_id,
            depreciation_date=body.depreciation_date,
            depreciation_amount=charge,
            transaction_id=txn.id,
        )
    )

    asset.accumulated_depreciation = money(D(asset.accumulated_depreciation) + charge)
    asset.book_value = money(D(asset.acquisition_cost) - D(asset.accumulated_depreciation))
    asset.last_depreciation_date = body.depreciation_date
    session.add(asset)
    log_audit(session, user, "UPDATE", "fixed_asset", asset_id, {"depreciation": str(charge)})
    session.commit()
    return {"jv_number": txn.jv_number, "depreciation_amount": charge}


@router.patch("/{asset_id}/dispose")
def dispose_asset(session: SessionDep, user: WriteUserDep, asset_id: int):
    asset = session.exec(
        select(FixedAsset).where(
            FixedAsset.id == asset_id, FixedAsset.tenant_id == user.tenant_id
        )
    ).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    asset.is_disposed = True
    session.add(asset)
    log_audit(session, user, "UPDATE", "fixed_asset", asset_id, {"action": "disposed"})
    session.commit()
    return {"success": True}
