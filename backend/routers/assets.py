"""Fixed asset register and depreciation runs. IAS 16 / IAS 36 (#258)."""
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Account, AssetImpairment, DepreciationEntry, FixedAsset
from routers.common import SessionDep, WriteUserDep, log_audit
from services import assets as asset_svc
from services.assets import AssetError
from services.depreciation import compute_depreciation
from services.money import D, money
from services.posting import EntryInput, post_transaction
from services.permissions import perm_dep

router = APIRouter(prefix="/api/assets", tags=["assets"], dependencies=[perm_dep("assets")])


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
    funding_account_id: Optional[int] = None
    parent_id: Optional[int] = None


class DepreciationRun(BaseModel):
    depreciation_date: str


class ImpairBody(BaseModel):
    recoverable_amount: Decimal
    impairment_date: str
    notes: Optional[str] = None


class ImpairReverseBody(BaseModel):
    amount: Decimal
    impairment_date: str
    notes: Optional[str] = None


class DisposeBody(BaseModel):
    disposal_date: str
    proceeds: Decimal = Decimal("0")
    proceeds_account_id: Optional[int] = None
    mode: Literal["sale", "scrap"] = "sale"


def _http(exc: AssetError) -> HTTPException:
    return HTTPException(exc.status_code, exc.message)


def _asset_dict(asset: FixedAsset) -> dict:
    d = asset.model_dump()
    d["nbv"] = float(asset_svc.nbv(asset))
    return d


@router.get("")
def list_assets(
    session: SessionDep,
    user: WriteUserDep,
    skip: int = 0,
    limit: int = 50,
    include_disposed: bool = False,
):
    q = select(FixedAsset).where(FixedAsset.tenant_id == user.tenant_id)
    if not include_disposed:
        q = q.where(FixedAsset.is_disposed == False)  # noqa: E712
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(
        q.order_by(FixedAsset.acquisition_date.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": [_asset_dict(a) for a in items]}


@router.get("/reports/rollforward")
def asset_rollforward(
    session: SessionDep,
    user: WriteUserDep,
    start: str,
    end: str,
):
    if not start or not end:
        raise HTTPException(400, "start and end query params are required")
    if start > end:
        raise HTTPException(400, "start must be <= end")
    return asset_svc.rollforward(session, user.tenant_id, start, end)


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
    comps = asset_svc.children(session, asset_id, user.tenant_id)
    impairments = session.exec(
        select(AssetImpairment).where(AssetImpairment.asset_id == asset_id)
        .order_by(AssetImpairment.impairment_date.desc(), AssetImpairment.id.desc())
    ).all()
    return {
        **_asset_dict(asset),
        "depreciation_entries": [e.model_dump() for e in entries],
        "components": [_asset_dict(c) for c in comps],
        "impairments": [i.model_dump() for i in impairments],
    }


@router.post("", status_code=201)
def create_asset(session: SessionDep, user: WriteUserDep, body: AssetCreate):
    if body.method not in ("straight_line", "reducing_balance"):
        raise HTTPException(400, "method must be 'straight_line' or 'reducing_balance'")

    # Verify all three account IDs belong to this tenant (IDOR protection)
    for aid in (body.asset_account_id, body.accum_depr_account_id, body.depr_expense_account_id):
        acc = session.exec(
            select(Account).where(Account.id == aid, Account.tenant_id == user.tenant_id)
        ).first()
        if not acc:
            raise HTTPException(400, f"Account {aid} not found for this tenant")

    if body.funding_account_id is not None:
        funding_acc = session.exec(
            select(Account).where(
                Account.id == body.funding_account_id, Account.tenant_id == user.tenant_id
            )
        ).first()
        if not funding_acc:
            raise HTTPException(400, f"Funding account {body.funding_account_id} not found for this tenant")

    parent_id = body.parent_id
    if parent_id is not None:
        parent = session.exec(
            select(FixedAsset).where(
                FixedAsset.id == parent_id,
                FixedAsset.tenant_id == user.tenant_id,
            )
        ).first()
        if not parent:
            raise HTTPException(400, f"Parent asset {parent_id} not found for this tenant")
        if parent.is_disposed:
            raise HTTPException(400, "Cannot add a component under a disposed parent")

    asset = FixedAsset(
        tenant_id=user.tenant_id,
        book_value=body.acquisition_cost,
        **body.model_dump(exclude={"funding_account_id"}),
    )
    session.add(asset)
    session.flush()

    if body.funding_account_id is not None:
        txn = post_transaction(
            session, user,
            date=body.acquisition_date,
            description=f"Asset acquisition: {body.name}",
            entries=[
                EntryInput(account_id=body.asset_account_id, debit=D(body.acquisition_cost)),
                EntryInput(account_id=body.funding_account_id, credit=D(body.acquisition_cost)),
            ],
            voucher_type="JV",
            audit_entity_type="fixed_asset",
            audit_detail={"asset_id": asset.id, "name": body.name},
        )
        asset.acquisition_transaction_id = txn.id
        session.add(asset)

    log_audit(session, user, "CREATE", "fixed_asset", asset.id, {"name": body.name})
    session.commit()
    session.refresh(asset)
    return _asset_dict(asset)


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
    if asset_svc.is_parent(session, asset):
        raise HTTPException(400, "Cannot depreciate a parent asset — depreciate components")

    charge = compute_depreciation(
        acquisition_cost=asset.acquisition_cost,
        salvage_value=asset.salvage_value,
        useful_life_months=asset.useful_life_months,
        accumulated_depreciation=asset.accumulated_depreciation,
        method=asset.method,
        accum_impairment=asset.accum_impairment,
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
    asset.book_value = asset_svc.nbv(asset)
    asset.last_depreciation_date = body.depreciation_date
    session.add(asset)
    log_audit(session, user, "UPDATE", "fixed_asset", asset_id, {"depreciation": str(charge)})
    session.commit()
    return {"jv_number": txn.jv_number, "depreciation_amount": charge}


@router.post("/{asset_id}/impair")
def impair_asset(
    session: SessionDep, user: WriteUserDep, asset_id: int, body: ImpairBody
):
    asset = session.exec(
        select(FixedAsset).where(
            FixedAsset.id == asset_id, FixedAsset.tenant_id == user.tenant_id
        )
    ).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    try:
        row = asset_svc.post_impairment(
            session, user, asset,
            recoverable_amount=body.recoverable_amount,
            impairment_date=body.impairment_date,
            notes=body.notes,
        )
    except AssetError as e:
        raise _http(e) from e
    log_audit(
        session, user, "UPDATE", "fixed_asset", asset_id,
        {"action": "impair", "amount": str(row.amount)},
    )
    impair_dump = row.model_dump(mode="json")
    session.commit()
    session.refresh(asset)
    return {
        **_asset_dict(asset),
        "impairment": impair_dump,
    }


@router.post("/{asset_id}/impair-reverse")
def impair_reverse(
    session: SessionDep, user: WriteUserDep, asset_id: int, body: ImpairReverseBody
):
    asset = session.exec(
        select(FixedAsset).where(
            FixedAsset.id == asset_id, FixedAsset.tenant_id == user.tenant_id
        )
    ).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    try:
        row = asset_svc.post_impairment_reversal(
            session, user, asset,
            amount=body.amount,
            impairment_date=body.impairment_date,
            notes=body.notes,
        )
    except AssetError as e:
        raise _http(e) from e
    log_audit(
        session, user, "UPDATE", "fixed_asset", asset_id,
        {"action": "impair_reverse", "amount": str(row.amount)},
    )
    impair_dump = row.model_dump(mode="json")
    session.commit()
    session.refresh(asset)
    return {
        **_asset_dict(asset),
        "impairment": impair_dump,
    }


@router.patch("/{asset_id}/dispose")
def dispose_asset_route(
    session: SessionDep, user: WriteUserDep, asset_id: int, body: DisposeBody
):
    asset = session.exec(
        select(FixedAsset).where(
            FixedAsset.id == asset_id, FixedAsset.tenant_id == user.tenant_id
        )
    ).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    try:
        asset_svc.dispose_asset(
            session, user, asset,
            disposal_date=body.disposal_date,
            proceeds=body.proceeds,
            proceeds_account_id=body.proceeds_account_id,
            mode=body.mode,
        )
    except AssetError as e:
        raise _http(e) from e
    log_audit(
        session, user, "UPDATE", "fixed_asset", asset_id,
        {"action": "disposed", "mode": body.mode, "proceeds": str(body.proceeds)},
    )
    session.commit()
    session.refresh(asset)
    return _asset_dict(asset)
