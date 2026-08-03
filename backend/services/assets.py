"""Fixed-asset GL helpers — IAS 16 / IAS 36 (#258).

All GL writes go through `services.posting.post_transaction`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select

from models import AssetImpairment, DepreciationEntry, FixedAsset, User
from routers.common import get_or_create_account
from services.money import D, ZERO, money
from services.posting import EntryInput, PostingError, post_transaction


class AssetError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def nbv(asset: FixedAsset) -> Decimal:
    """Net book value = cost − accum_depr − accum_impairment."""
    if asset.is_disposed:
        return ZERO
    return money(
        D(asset.acquisition_cost)
        - D(asset.accumulated_depreciation)
        - D(asset.accum_impairment)
    )


def is_parent(session: Session, asset: FixedAsset) -> bool:
    """True when the asset has at least one child in the same tenant."""
    child = session.exec(
        select(FixedAsset).where(
            FixedAsset.parent_id == asset.id,
            FixedAsset.tenant_id == asset.tenant_id,
        )
    ).first()
    return child is not None


def children(session: Session, asset_id: int, tenant_id: int) -> list[FixedAsset]:
    return list(
        session.exec(
            select(FixedAsset).where(
                FixedAsset.parent_id == asset_id,
                FixedAsset.tenant_id == tenant_id,
            ).order_by(FixedAsset.id)
        ).all()
    )


def _require_leaf(session: Session, asset: FixedAsset, action: str) -> None:
    if asset.is_disposed:
        raise AssetError(f"Cannot {action} a disposed asset")
    if is_parent(session, asset):
        raise AssetError(
            f"Cannot {action} a parent asset — dispose/impair components first"
        )


def post_impairment(
    session: Session,
    user: User,
    asset: FixedAsset,
    *,
    recoverable_amount: Decimal,
    impairment_date: str,
    notes: Optional[str] = None,
) -> AssetImpairment:
    """IAS 36 impairment loss: Dr 5061 / Cr accum_depr; bump accum_impairment."""
    _require_leaf(session, asset, "impair")

    carrying = nbv(asset)
    recoverable = money(recoverable_amount)
    loss = money(max(ZERO, carrying - recoverable))
    if loss <= ZERO:
        raise AssetError("No impairment — recoverable amount >= carrying amount")

    impair_acc = get_or_create_account(
        session, user.tenant_id, "5061", "Impairment Loss", "Expense"
    )

    try:
        txn = post_transaction(
            session, user,
            date=impairment_date,
            description=f"Impairment — {asset.name}",
            entries=[
                EntryInput(account_id=impair_acc.id, debit=loss),
                EntryInput(account_id=asset.accum_depr_account_id, credit=loss),
            ],
            voucher_type="JV",
            audit_entity_type="fixed_asset",
            audit_detail={
                "asset_id": asset.id,
                "kind": "impairment",
                "amount": str(loss),
            },
        )
    except PostingError as e:
        raise AssetError(str(e)) from e

    asset.accum_impairment = money(D(asset.accum_impairment) + loss)
    asset.book_value = nbv(asset)
    session.add(asset)

    row = AssetImpairment(
        tenant_id=user.tenant_id,
        asset_id=asset.id,
        impairment_date=impairment_date,
        recoverable_amount=recoverable,
        carrying_before=carrying,
        amount=loss,
        notes=notes,
        transaction_id=txn.id,
        created_by_id=user.id,
    )
    session.add(row)
    session.flush()
    return row


def post_impairment_reversal(
    session: Session,
    user: User,
    asset: FixedAsset,
    *,
    amount: Decimal,
    impairment_date: str,
    notes: Optional[str] = None,
) -> AssetImpairment:
    """Reverse prior impairment (capped at accum_impairment): Dr accum_depr / Cr 5061."""
    _require_leaf(session, asset, "reverse impairment on")

    amt = money(amount)
    if amt <= ZERO:
        raise AssetError("Reversal amount must be > 0")
    cap = money(asset.accum_impairment)
    if amt > cap:
        amt = cap
    if amt <= ZERO:
        raise AssetError("No accumulated impairment to reverse")

    impair_acc = get_or_create_account(
        session, user.tenant_id, "5061", "Impairment Loss", "Expense"
    )
    carrying = nbv(asset)

    try:
        txn = post_transaction(
            session, user,
            date=impairment_date,
            description=f"Impairment reversal — {asset.name}",
            entries=[
                EntryInput(account_id=asset.accum_depr_account_id, debit=amt),
                EntryInput(account_id=impair_acc.id, credit=amt),
            ],
            voucher_type="JV",
            audit_entity_type="fixed_asset",
            audit_detail={
                "asset_id": asset.id,
                "kind": "impairment_reversal",
                "amount": str(amt),
            },
        )
    except PostingError as e:
        raise AssetError(str(e)) from e

    asset.accum_impairment = money(D(asset.accum_impairment) - amt)
    asset.book_value = nbv(asset)
    session.add(asset)

    row = AssetImpairment(
        tenant_id=user.tenant_id,
        asset_id=asset.id,
        impairment_date=impairment_date,
        recoverable_amount=money(carrying + amt),
        carrying_before=carrying,
        amount=money(-amt),
        notes=notes,
        transaction_id=txn.id,
        created_by_id=user.id,
    )
    session.add(row)
    session.flush()
    return row


def dispose_asset(
    session: Session,
    user: User,
    asset: FixedAsset,
    *,
    disposal_date: str,
    proceeds: Decimal = ZERO,
    proceeds_account_id: Optional[int] = None,
    mode: str = "sale",
) -> FixedAsset:
    """Derecognise a leaf asset — sale or scrap — with gain/loss to P&L."""
    from models import Account

    _require_leaf(session, asset, "dispose")
    if mode not in ("sale", "scrap"):
        raise AssetError("mode must be 'sale' or 'scrap'")

    if mode == "scrap":
        proceeds_amt = ZERO
    else:
        proceeds_amt = money(proceeds)
        if proceeds_amt < ZERO:
            raise AssetError("proceeds cannot be negative")
        if proceeds_amt > ZERO:
            if not proceeds_account_id:
                raise AssetError("proceeds_account_id required when proceeds > 0")
            pay = session.exec(
                select(Account).where(
                    Account.id == proceeds_account_id,
                    Account.tenant_id == user.tenant_id,
                )
            ).first()
            if not pay:
                raise AssetError(
                    f"Proceeds account {proceeds_account_id} not found for this tenant"
                )

    cost = money(asset.acquisition_cost)
    accum_total = money(D(asset.accumulated_depreciation) + D(asset.accum_impairment))
    carrying = money(cost - accum_total)  # = nbv before dispose
    gain_loss = money(proceeds_amt - carrying)  # +gain / -loss

    gain_acc = get_or_create_account(
        session, user.tenant_id, "4904", "Gain on Asset Disposal", "Revenue"
    )
    loss_acc = get_or_create_account(
        session, user.tenant_id, "5062", "Loss on Asset Disposal", "Expense"
    )

    # Dr accum (accum_depr+impair), Dr proceeds, Dr loss | Cr cost, Cr gain
    entries: list[EntryInput] = []
    if accum_total > ZERO:
        entries.append(EntryInput(account_id=asset.accum_depr_account_id, debit=accum_total))
    if proceeds_amt > ZERO:
        entries.append(EntryInput(account_id=proceeds_account_id, debit=proceeds_amt))
    if gain_loss < ZERO:
        entries.append(EntryInput(account_id=loss_acc.id, debit=money(-gain_loss)))
    entries.append(EntryInput(account_id=asset.asset_account_id, credit=cost))
    if gain_loss > ZERO:
        entries.append(EntryInput(account_id=gain_acc.id, credit=gain_loss))

    # Balance check: accum + proceeds + loss = cost + gain
    try:
        txn = post_transaction(
            session, user,
            date=disposal_date,
            description=f"Asset disposal ({mode}) — {asset.name}",
            entries=entries,
            voucher_type="JV",
            audit_entity_type="fixed_asset",
            audit_detail={
                "asset_id": asset.id,
                "kind": "disposal",
                "mode": mode,
                "proceeds": str(proceeds_amt),
                "gain_loss": str(gain_loss),
            },
        )
    except PostingError as e:
        raise AssetError(str(e)) from e

    asset.is_disposed = True
    asset.book_value = ZERO
    asset.disposal_date = disposal_date
    asset.disposal_proceeds = proceeds_amt
    asset.disposal_transaction_id = txn.id
    session.add(asset)
    session.flush()
    return asset


def _sum_depr_before(
    session: Session, asset_id: int, as_of: str, *, inclusive: bool
) -> Decimal:
    q = select(DepreciationEntry).where(DepreciationEntry.asset_id == asset_id)
    rows = session.exec(q).all()
    total = ZERO
    for r in rows:
        if inclusive:
            if r.depreciation_date <= as_of:
                total += D(r.depreciation_amount)
        else:
            if r.depreciation_date < as_of:
                total += D(r.depreciation_amount)
    return money(total)


def _sum_impair_before(
    session: Session, asset_id: int, as_of: str, *, inclusive: bool
) -> Decimal:
    q = select(AssetImpairment).where(AssetImpairment.asset_id == asset_id)
    rows = session.exec(q).all()
    total = ZERO
    for r in rows:
        if inclusive:
            if r.impairment_date <= as_of:
                total += D(r.amount)
        else:
            if r.impairment_date < as_of:
                total += D(r.amount)
    return money(total)


def _nbv_as_of(
    session: Session,
    asset: FixedAsset,
    as_of: str,
    *,
    inclusive: bool = False,
) -> Decimal:
    """Carrying amount at `as_of`.

    inclusive=False → opening (movements with date < as_of).
    inclusive=True  → closing (movements with date <= as_of).
    Returns 0 if not yet acquired, or disposed on/before the boundary.
    """
    if asset.acquisition_date > as_of:
        return ZERO
    if asset.acquisition_date == as_of and not inclusive:
        # Acquired on as_of day → not in opening
        return ZERO

    if asset.is_disposed and asset.disposal_date:
        if inclusive and asset.disposal_date <= as_of:
            return ZERO
        if not inclusive and asset.disposal_date < as_of:
            return ZERO

    depr = _sum_depr_before(session, asset.id, as_of, inclusive=inclusive)
    impair = _sum_impair_before(session, asset.id, as_of, inclusive=inclusive)
    # Acquisition on as_of with inclusive (closing): include full cost
    if not inclusive and asset.acquisition_date >= as_of:
        return ZERO
    return money(D(asset.acquisition_cost) - depr - impair)


def rollforward(
    session: Session,
    tenant_id: int,
    start: str,
    end: str,
) -> dict:
    """Asset register rollforward for leaf assets in [start, end]."""
    leaves = session.exec(
        select(FixedAsset).where(FixedAsset.tenant_id == tenant_id)
    ).all()

    # Exclude pure parents (have children) from leaf rows; optional parent subtotals later
    parent_ids = {
        a.parent_id for a in leaves if a.parent_id is not None
    }

    rows: list[dict] = []
    totals = {
        "opening_nbv": ZERO,
        "additions": ZERO,
        "disposals_nbv": ZERO,
        "depreciation": ZERO,
        "impairment_net": ZERO,
        "closing_nbv": ZERO,
    }

    for asset in leaves:
        if asset.id in parent_ids:
            continue  # skip parent shells

        acq = asset.acquisition_date
        if acq > end:
            continue
        if asset.is_disposed and asset.disposal_date and asset.disposal_date < start:
            continue

        opening = _nbv_as_of(session, asset, start, inclusive=False)
        additions = (
            money(asset.acquisition_cost) if start <= acq <= end else ZERO
        )

        depr_rows = session.exec(
            select(DepreciationEntry).where(
                DepreciationEntry.asset_id == asset.id,
                DepreciationEntry.depreciation_date >= start,
                DepreciationEntry.depreciation_date <= end,
            )
        ).all()
        depreciation = money(sum((D(r.depreciation_amount) for r in depr_rows), ZERO))

        impair_rows = session.exec(
            select(AssetImpairment).where(
                AssetImpairment.asset_id == asset.id,
                AssetImpairment.impairment_date >= start,
                AssetImpairment.impairment_date <= end,
            )
        ).all()
        impairment_net = money(sum((D(r.amount) for r in impair_rows), ZERO))

        disposed_in_period = (
            asset.is_disposed
            and asset.disposal_date
            and start <= asset.disposal_date <= end
        )
        if disposed_in_period:
            closing = ZERO
            # Identity: opening + additions − depr − impair − disposals = closing
            disposals_nbv = money(
                opening + additions - depreciation - impairment_net - closing
            )
        else:
            closing = _nbv_as_of(session, asset, end, inclusive=True)
            disposals_nbv = ZERO

        row = {
            "asset_id": asset.id,
            "name": asset.name,
            "code": asset.code,
            "parent_id": asset.parent_id,
            "opening_nbv": float(opening),
            "additions": float(additions),
            "disposals_nbv": float(disposals_nbv),
            "depreciation": float(depreciation),
            "impairment_net": float(impairment_net),
            "closing_nbv": float(closing),
        }
        rows.append(row)
        for k in totals:
            totals[k] = money(totals[k] + D(row[k]))

    # Optional parent subtotals
    by_parent: dict[int, dict] = {}
    for row in rows:
        pid = row.get("parent_id")
        if pid is None:
            continue
        if pid not in by_parent:
            by_parent[pid] = {
                "asset_id": pid,
                "name": None,
                "code": None,
                "parent_id": None,
                "is_subtotal": True,
                "opening_nbv": 0.0,
                "additions": 0.0,
                "disposals_nbv": 0.0,
                "depreciation": 0.0,
                "impairment_net": 0.0,
                "closing_nbv": 0.0,
            }
        for k in (
            "opening_nbv", "additions", "disposals_nbv",
            "depreciation", "impairment_net", "closing_nbv",
        ):
            by_parent[pid][k] = float(
                money(D(by_parent[pid][k]) + D(row[k]))
            )

    if by_parent:
        parents = {
            p.id: p
            for p in session.exec(
                select(FixedAsset).where(
                    FixedAsset.tenant_id == tenant_id,
                    FixedAsset.id.in_(list(by_parent.keys())),
                )
            ).all()
        }
        for pid, sub in by_parent.items():
            p = parents.get(pid)
            if p:
                sub["name"] = p.name
                sub["code"] = p.code
            rows.append(sub)

    return {
        "start": start,
        "end": end,
        "rows": rows,
        "totals": {k: float(v) for k, v in totals.items()},
    }
