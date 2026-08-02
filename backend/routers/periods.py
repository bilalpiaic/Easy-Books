"""Accounting periods: create, list, lock/unlock, delete, period-end close."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import func, select

from models import (
    AccountBalance, Account, AccountingPeriod, CloseChecklistItem,
    JournalEntry, Transaction,
)
from services.close_pack import (
    assert_can_lock, build_audit_pack_zip, ensure_checklist, serialize_item,
)
from services.events import emit
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, WriteUserDep, get_or_create_account, log_audit
from services.permissions import perm_dep

router = APIRouter(prefix="/api/periods", tags=["periods"], dependencies=[perm_dep("period_close")])


class PeriodCreate(BaseModel):
    name: Optional[str] = None
    period_start: str
    period_end: str


class ChecklistPatch(BaseModel):
    is_done: Optional[bool] = None
    notes: Optional[str] = None


def _get_period(session, user, period_id: int) -> AccountingPeriod:
    p = session.exec(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.tenant_id == user.tenant_id,
        )
    ).first()
    if not p:
        raise HTTPException(404, "Period not found")
    return p


@router.get("")
def list_periods(session: SessionDep, user: CurrentUserDep):
    return session.exec(
        select(AccountingPeriod)
        .where(AccountingPeriod.tenant_id == user.tenant_id)
        .order_by(AccountingPeriod.period_start.desc())
    ).all()


@router.post("", status_code=201)
def create_period(session: SessionDep, user: WriteUserDep, body: PeriodCreate):
    p = AccountingPeriod(tenant_id=user.tenant_id, **body.model_dump())
    session.add(p)
    session.flush()
    ensure_checklist(session, p)
    session.commit()
    session.refresh(p)
    return p


@router.get("/{period_id}/checklist")
def get_checklist(session: SessionDep, user: CurrentUserDep, period_id: int):
    p = _get_period(session, user, period_id)
    items = ensure_checklist(session, p)
    session.commit()
    return [serialize_item(i) for i in items]


@router.patch("/{period_id}/checklist/{item_id}")
def patch_checklist_item(
    session: SessionDep, user: WriteUserDep, period_id: int, item_id: int, body: ChecklistPatch,
):
    p = _get_period(session, user, period_id)
    item = session.exec(
        select(CloseChecklistItem).where(
            CloseChecklistItem.id == item_id,
            CloseChecklistItem.period_id == p.id,
            CloseChecklistItem.tenant_id == user.tenant_id,
        )
    ).first()
    if not item:
        raise HTTPException(404, "Checklist item not found")
    if body.is_done is not None:
        item.is_done = body.is_done
        if body.is_done:
            item.completed_at = datetime.utcnow()
            item.completed_by_id = user.id
        else:
            item.completed_at = None
            item.completed_by_id = None
    if body.notes is not None:
        item.notes = body.notes
    session.add(item)
    session.commit()
    session.refresh(item)
    return serialize_item(item)


@router.get("/{period_id}/audit-pack")
def download_audit_pack(session: SessionDep, user: CurrentUserDep, period_id: int):
    """ZIP of TB / GL / aging / inventory / FA / cash flow for the period (#262)."""
    p = _get_period(session, user, period_id)
    try:
        data = build_audit_pack_zip(session, user, p)
    except Exception as exc:
        raise HTTPException(500, f"Audit pack failed: {exc}") from exc
    log_audit(session, user, "EXPORT", "period_audit_pack", p.id, {
        "period_start": p.period_start, "period_end": p.period_end, "bytes": len(data),
    })
    session.commit()
    name = (p.name or f"period-{p.id}").replace(" ", "_")
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="audit-pack-{name}.zip"',
        },
    )


@router.patch("/{period_id}/lock")
def toggle_period_lock(
    session: SessionDep, user: WriteUserDep, period_id: int, is_locked: bool
):
    p = _get_period(session, user, period_id)
    if is_locked:
        try:
            assert_can_lock(session, p)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    p.is_locked = is_locked
    session.add(p)
    if is_locked:
        emit(session, user.tenant_id, "period.closed", {
            "period_id": p.id, "name": p.name,
            "period_start": p.period_start, "period_end": p.period_end,
        })
    session.commit()
    return p


@router.delete("/{period_id}", status_code=204)
def delete_period(session: SessionDep, user: WriteUserDep, period_id: int):
    p = _get_period(session, user, period_id)
    for item in session.exec(
        select(CloseChecklistItem).where(
            CloseChecklistItem.period_id == p.id,
            CloseChecklistItem.tenant_id == user.tenant_id,
        )
    ).all():
        session.delete(item)
    session.delete(p)
    session.commit()


def _pl_net_income(session, user, p) -> tuple[list, "Decimal"]:
    """Aggregate Revenue/Expense in [start, end]; return (rows, net_income).
    net_income > 0 = profit (credit to RE), < 0 = loss."""
    rows = session.exec(
        select(
            Account.id,
            Account.code,
            Account.name,
            Account.type,
            func.coalesce(func.sum(JournalEntry.debit), 0).label("dr"),
            func.coalesce(func.sum(JournalEntry.credit), 0).label("cr"),
        )
        .join(JournalEntry, JournalEntry.account_id == Account.id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(
            Transaction.tenant_id == user.tenant_id,
            Transaction.date >= p.period_start,
            Transaction.date <= p.period_end,
            Account.type.in_(("Revenue", "Expense")),
        )
        .group_by(Account.id, Account.type)
    ).all()
    net = ZERO
    for r in rows:
        if r.type == "Revenue":
            net += D(r.cr) - D(r.dr)
        else:
            net -= D(r.dr) - D(r.cr)
    return rows, net


def _snapshot_balances(session, user, p) -> None:
    """Materialise per-account balances for the period so locked-period reads
    are fast. Includes any closing JV already posted. Skips all-zero rows."""
    snapshot = session.exec(
        select(
            Account.id.label("account_id"),
            func.coalesce(func.sum(JournalEntry.debit), 0).label("dr"),
            func.coalesce(func.sum(JournalEntry.credit), 0).label("cr"),
        )
        .join(JournalEntry, JournalEntry.account_id == Account.id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(
            Transaction.tenant_id == user.tenant_id,
            Transaction.date >= p.period_start,
            Transaction.date <= p.period_end,
        )
        .group_by(Account.id)
    ).all()
    for row in snapshot:
        if D(row.dr) == 0 and D(row.cr) == 0:
            continue
        session.add(
            AccountBalance(
                tenant_id=user.tenant_id, period_id=p.id, account_id=row.account_id,
                debit_total=money(row.dr), credit_total=money(row.cr),
            )
        )


@router.get("/{period_id}/close-preview")
def close_preview(session: SessionDep, user: CurrentUserDep, period_id: int):
    """Preview the P&L → Retained Earnings impact of a year-end close, without
    posting anything. Lets the UI show net income before the user commits."""
    p = session.exec(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.tenant_id == user.tenant_id,
        )
    ).first()
    if not p:
        raise HTTPException(404, "Period not found")
    rows, net = _pl_net_income(session, user, p)
    revenue = sum((D(r.cr) - D(r.dr) for r in rows if r.type == "Revenue"), ZERO)
    expense = sum((D(r.dr) - D(r.cr) for r in rows if r.type == "Expense"), ZERO)
    return {
        "period": {"start": p.period_start, "end": p.period_end, "name": p.name},
        "revenue_total": str(money(revenue)),
        "expense_total": str(money(expense)),
        "net_income": str(money(net)),
        "by_account": [
            {
                "code": r.code, "name": r.name, "type": r.type,
                "amount": str(money((D(r.cr) - D(r.dr)) if r.type == "Revenue"
                                    else (D(r.dr) - D(r.cr)))),
            }
            for r in rows
        ],
    }


@router.post("/{period_id}/close")
def close_period(
    session: SessionDep, user: WriteUserDep, period_id: int,
    mode: str = "year_end",
):
    """Close a period.

    mode="year_end" (default): post the P&L → Retained Earnings closing JV,
        snapshot balances, and lock. Use at fiscal year-end.
    mode="soft": lock + snapshot balances only — P&L is NOT zeroed, so
        within-year income statements stay cumulative and comparable. Use for
        monthly/quarterly management closes. Balance-sheet accounts carry
        forward automatically (live-from-GL continuity).
    """
    if mode not in ("year_end", "soft"):
        raise HTTPException(400, "mode must be 'year_end' or 'soft'")

    p = _get_period(session, user, period_id)
    if p.is_locked:
        raise HTTPException(400, "Period already closed/locked")
    try:
        assert_can_lock(session, p)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    net = ZERO
    entries_posted = 0

    if mode == "year_end":
        rows, net = _pl_net_income(session, user, p)
        entries: list[EntryInput] = []
        for r in rows:
            if r.type == "Revenue":
                amount = D(r.cr) - D(r.dr)
                if amount > 0:
                    entries.append(EntryInput(account_id=r.id, debit=money(amount)))
            else:  # Expense
                amount = D(r.dr) - D(r.cr)
                if amount > 0:
                    entries.append(EntryInput(account_id=r.id, credit=money(amount)))
        if entries and net != 0:
            re_acc = get_or_create_account(
                session, user.tenant_id, "3100", "Retained Earnings", "Equity"
            )
            if net > 0:
                entries.append(EntryInput(account_id=re_acc.id, credit=money(net)))
            else:
                entries.append(EntryInput(account_id=re_acc.id, debit=money(-net)))
            post_transaction(
                session, user,
                date=p.period_end,
                description=f"Year-end close: {p.period_start} → {p.period_end}",
                entries=entries,
                audit_entity_type="period",
                audit_detail={"period_id": p.id, "net_income": str(net)},
            )
            entries_posted = len(entries)

    p.is_locked = True
    session.add(p)
    _snapshot_balances(session, user, p)

    log_audit(session, user, "CLOSE", "period", p.id,
              {"mode": mode, "net_income": str(net)})
    session.commit()
    session.refresh(p)
    return {"period": p, "mode": mode, "net_income": str(net),
            "entries_posted": entries_posted}


@router.post("/{period_id}/reopen")
def reopen_period(session: SessionDep, user: WriteUserDep, period_id: int):
    """Reopen a closed period. Removes the materialised balance rows so
    trial-balance reads fall back to live aggregation again.

    Note: this does NOT un-post the closing JV. Reverse that JV manually if
    you also need to undo the retained-earnings rollover.
    """
    p = session.exec(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.tenant_id == user.tenant_id,
        )
    ).first()
    if not p:
        raise HTTPException(404, "Period not found")
    if not p.is_locked:
        raise HTTPException(400, "Period is already open")
    # Invalidate materialised balances for this period
    rows = session.exec(
        select(AccountBalance).where(
            AccountBalance.tenant_id == user.tenant_id,
            AccountBalance.period_id == p.id,
        )
    ).all()
    for r in rows:
        session.delete(r)
    p.is_locked = False
    session.add(p)
    log_audit(session, user, "REOPEN", "period", p.id, {})
    session.commit()
    session.refresh(p)
    return p
