"""Store Issue — departmental/cost-center consumption out of the store
(#137 Phase 3). Deliberately separate from ProductionOrder's own
raw-material consumption path. Posts GL and relieves stock immediately on
create — no draft/approve gate; block_negative_stock is the control."""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import func, select

from models import Account, AnalyticAccount, Product, Settings, StockLocation, StoreIssue, StoreIssueLine
from routers.common import SessionDep, WriteUserDep, get_or_create_account, log_audit, next_number
from services.inventory import InventoryError, consume_stock
from services.money import D, money
from services.permissions import apply_own_filter, perm_dep
from services.posting import EntryInput, post_transaction
from services.analytics import pack_analytics

router = APIRouter(
    prefix="/api/store-issues", tags=["store-issues"],
    dependencies=[perm_dep("store.issue")],
)


class SILineIn(BaseModel):
    product_id: int
    qty: float


class SIIn(BaseModel):
    issue_date: str
    from_location_id: int
    analytic_account_id: Optional[int] = None
    analytic_2_id: Optional[int] = None
    analytic_3_id: Optional[int] = None
    analytic_ids: Optional[List[int]] = None
    debit_account_id: int
    notes: Optional[str] = None
    lines: List[SILineIn] = []


def _get_si(session, user, si_id: int) -> StoreIssue:
    si = session.exec(
        select(StoreIssue).where(
            StoreIssue.id == si_id, StoreIssue.tenant_id == user.tenant_id
        )
    ).first()
    if not si:
        raise HTTPException(404, "Store issue not found")
    return si


def _serialize_many(session, rows: list[StoreIssue]) -> list[dict]:
    if not rows:
        return []
    ids = [si.id for si in rows if si.id is not None]
    loc_ids = {si.from_location_id for si in rows if si.from_location_id}
    acct_ids = {si.debit_account_id for si in rows if si.debit_account_id}
    aa_ids = {si.analytic_account_id for si in rows if si.analytic_account_id}

    lines_by: dict[int, list] = {i: [] for i in ids}
    if ids:
        for line in session.exec(
            select(StoreIssueLine)
            .where(StoreIssueLine.store_issue_id.in_(ids))  # type: ignore[attr-defined]
            .order_by(StoreIssueLine.id)
        ).all():
            lines_by.setdefault(line.store_issue_id, []).append(line.model_dump())

    locs = {}
    if loc_ids:
        locs = {
            loc.id: loc.name
            for loc in session.exec(
                select(StockLocation).where(StockLocation.id.in_(loc_ids))  # type: ignore[attr-defined]
            ).all()
        }
    accts = {}
    if acct_ids:
        accts = {
            a.id: a.name
            for a in session.exec(
                select(Account).where(Account.id.in_(acct_ids))  # type: ignore[attr-defined]
            ).all()
        }
    aas = {}
    if aa_ids:
        aas = {
            a.id: a.name
            for a in session.exec(
                select(AnalyticAccount).where(AnalyticAccount.id.in_(aa_ids))  # type: ignore[attr-defined]
            ).all()
        }

    result = []
    for si in rows:
        out = si.model_dump()
        out["lines"] = lines_by.get(si.id, [])
        out["location_name"] = locs.get(si.from_location_id)
        out["debit_account_name"] = accts.get(si.debit_account_id)
        out["analytic_account_name"] = (
            aas.get(si.analytic_account_id) if si.analytic_account_id else None
        )
        result.append(out)
    return result


def _serialize(session, si: StoreIssue) -> dict:
    return _serialize_many(session, [si])[0]


def _block_negative_stock(session, tenant_id: int) -> bool:
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == tenant_id, Settings.key == "block_negative_stock",
        )
    ).first()
    return bool(row and (row.value or "").lower() == "true")


@router.get("")
def list_store_issues(
    session: SessionDep, user: WriteUserDep,
    from_location_id: Optional[int] = None, analytic_account_id: Optional[int] = None,
    start: Optional[str] = None, end: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    q = select(StoreIssue).where(StoreIssue.tenant_id == user.tenant_id)
    if from_location_id:
        q = q.where(StoreIssue.from_location_id == from_location_id)
    if analytic_account_id:
        q = q.where(StoreIssue.analytic_account_id == analytic_account_id)
    if start:
        q = q.where(StoreIssue.issue_date >= start)
    if end:
        q = q.where(StoreIssue.issue_date <= end)
    q = apply_own_filter(q, StoreIssue, user, session)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    rows = session.exec(
        q.order_by(StoreIssue.id.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": _serialize_many(session, list(rows))}


@router.get("/{si_id}")
def get_store_issue(session: SessionDep, user: WriteUserDep, si_id: int):
    return _serialize(session, _get_si(session, user, si_id))


@router.post("", status_code=201, dependencies=[perm_dep("store.issue", "edit")])
def create_store_issue(session: SessionDep, user: WriteUserDep, body: SIIn):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")

    loc = session.exec(
        select(StockLocation).where(
            StockLocation.id == body.from_location_id, StockLocation.tenant_id == user.tenant_id
        )
    ).first()
    if not loc:
        raise HTTPException(404, "Stock location not found")

    debit_acct = session.exec(
        select(Account).where(
            Account.id == body.debit_account_id, Account.tenant_id == user.tenant_id
        )
    ).first()
    if not debit_acct:
        raise HTTPException(404, "Debit account not found")
    if debit_acct.type != "Expense":
        raise HTTPException(400, f"Debit account must be an Expense-type account, got '{debit_acct.type}'")

    if body.analytic_account_id:
        aa = session.exec(
            select(AnalyticAccount).where(
                AnalyticAccount.id == body.analytic_account_id,
                AnalyticAccount.tenant_id == user.tenant_id,
            )
        ).first()
        if not aa:
            raise HTTPException(404, "Analytic account not found")

    for l in body.lines:
        if D(l.qty) <= 0:
            raise HTTPException(400, "qty must be positive")
        prod = session.exec(
            select(Product).where(
                Product.id == l.product_id, Product.tenant_id == user.tenant_id
            )
        ).first()
        if not prod:
            raise HTTPException(404, "Product not found")
        if prod.product_type != "stock":
            raise HTTPException(400, f"Product '{prod.name}' is not a stock item")

    number = next_number(
        session, user.tenant_id, "store_issue", "SI", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    si = StoreIssue(
        tenant_id=user.tenant_id, number=number, issue_date=body.issue_date,
        from_location_id=body.from_location_id,
        analytic_account_id=body.analytic_account_id,
        analytic_2_id=body.analytic_2_id,
        analytic_3_id=body.analytic_3_id,
        debit_account_id=body.debit_account_id, notes=body.notes, created_by_id=user.id,
    )
    session.add(si)
    session.flush()

    block_negative = _block_negative_stock(session, user.tenant_id)
    total_cost = D("0")
    for l in body.lines:
        qty = D(l.qty)
        try:
            cost = consume_stock(
                session, tenant_id=user.tenant_id, product_id=l.product_id, qty=qty,
                block_negative=block_negative, source_doc_id=si.id,
                source_doc_type="store_issue",
            )
        except InventoryError as e:
            raise HTTPException(400, str(e))
        total_cost += cost
        row = StoreIssueLine(
            store_issue_id=si.id, product_id=l.product_id, qty=qty,
            unit_cost=money(cost / qty),
        )
        session.add(row)

    if total_cost > 0:
        inv_acct = get_or_create_account(
            session, user.tenant_id, "1200", "Inventory (Raw Material)", "Asset"
        )
        txn = post_transaction(
            session, user, date=body.issue_date,
            description=f"Store issue — {number}",
            entries=[
                EntryInput(
                    account_id=debit_acct.id, debit=money(total_cost),
                    analytic_account_id=body.analytic_account_id,
                    analytic_2_id=body.analytic_2_id,
                    analytic_3_id=body.analytic_3_id,
                    analytic_ids=body.analytic_ids,
                ),
                EntryInput(account_id=inv_acct.id, credit=money(total_cost)),
            ],
            voucher_type="JV",
            audit_entity_type="store_issue",
            audit_detail={"si_number": number},
        )
        si.transaction_id = txn.id

    log_audit(session, user, "CREATE", "store_issue", si.id, {"number": number})
    session.commit()
    return _serialize(session, si)
