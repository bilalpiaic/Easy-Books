"""Period-end FX revaluation (IAS 21.23) for open foreign AR and AP.

Uses each document's carrying_rate (or issue exchange_rate) as the from-rate,
posts unrealised differences to 4901, then updates carrying_rate to the closing
rate so a re-run for the same rates is a no-op.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from sqlmodel import Session, func, select

from models import Account, Bill, Invoice, PaymentAllocation, Tenant, User
from services.fx import rate_to_base
from services.money import D, ZERO, money
from services.payment_fx import doc_carrying_rate
from services.posting import EntryInput, post_transaction


_OPEN_INV_STATUSES = ("draft", "posted", "partial", "sent", "open", "overdue")
_OPEN_BILL_STATUSES = ("draft", "posted", "partial", "open", "received")


def _default_party_account(
    session: Session, tenant_id: int, code: str, name: str, acc_type: str
) -> Optional[Account]:
    from routers.common import get_or_create_account
    return get_or_create_account(session, tenant_id, code, name, acc_type)


def run_fx_revaluation(
    session: Session,
    user: User,
    revaluation_date: str,
) -> dict[str, Any]:
    from routers.common import get_or_create_account

    tenant = session.get(Tenant, user.tenant_id)
    base_currency = tenant.base_currency if tenant else "USD"

    fx_acc = get_or_create_account(
        session, user.tenant_id, "4901", "Unrealised FX Gain/Loss", "Revenue"
    )
    default_ar = _default_party_account(
        session, user.tenant_id, "1100", "Accounts Receivable", "Asset"
    )
    default_ap = _default_party_account(
        session, user.tenant_id, "2000", "Accounts Payable", "Liability"
    )

    positions: list[dict[str, Any]] = []
    all_entries: list[EntryInput] = []
    touched_invoices: list[tuple[Invoice, Decimal]] = []
    touched_bills: list[tuple[Bill, Decimal]] = []

    open_invoices = session.exec(
        select(Invoice).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.status.in_(list(_OPEN_INV_STATUSES)),
            Invoice.transaction_id.is_not(None),
            Invoice.currency != base_currency,
        )
    ).all()

    for inv in open_invoices:
        alloc_total = session.exec(
            select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
                PaymentAllocation.invoice_id == inv.id
            )
        ).one()
        outstanding_doc = D(str(inv.total)) - D(str(alloc_total))
        if outstanding_doc <= ZERO:
            continue
        try:
            closing_rate = rate_to_base(
                session, user.tenant_id, inv.currency, revaluation_date
            )
        except LookupError:
            continue
        from_rate = doc_carrying_rate(inv)
        original_base = money(outstanding_doc * from_rate)
        closing_base = money(outstanding_doc * closing_rate)
        diff = closing_base - original_base
        if abs(diff) < D("0.01"):
            # Still stamp carrying_rate so later runs stay aligned
            if inv.carrying_rate is None or D(inv.carrying_rate) != closing_rate:
                touched_invoices.append((inv, closing_rate))
            continue

        ar_acc = session.get(Account, inv.ar_account_id) if inv.ar_account_id else default_ar
        if not ar_acc:
            continue

        if diff > ZERO:
            all_entries += [
                EntryInput(account_id=ar_acc.id, debit=diff),
                EntryInput(account_id=fx_acc.id, credit=diff),
            ]
        else:
            all_entries += [
                EntryInput(account_id=fx_acc.id, debit=-diff),
                EntryInput(account_id=ar_acc.id, credit=-diff),
            ]
        positions.append({
            "doc_type": "invoice",
            "id": inv.id,
            "number": inv.number,
            "currency": inv.currency,
            "outstanding_doc": float(outstanding_doc),
            "from_rate": float(from_rate),
            "to_rate": float(closing_rate),
            "base_before": float(original_base),
            "base_after": float(closing_base),
            "diff": float(diff),
        })
        touched_invoices.append((inv, closing_rate))

    open_bills = session.exec(
        select(Bill).where(
            Bill.tenant_id == user.tenant_id,
            Bill.status.in_(list(_OPEN_BILL_STATUSES)),
            Bill.transaction_id.is_not(None),
            Bill.currency != base_currency,
        )
    ).all()

    for bill in open_bills:
        alloc_total = session.exec(
            select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
                PaymentAllocation.bill_id == bill.id
            )
        ).one()
        outstanding_doc = D(str(bill.total)) - D(str(alloc_total))
        if outstanding_doc <= ZERO:
            continue
        try:
            closing_rate = rate_to_base(
                session, user.tenant_id, bill.currency, revaluation_date
            )
        except LookupError:
            continue
        from_rate = doc_carrying_rate(bill)
        original_base = money(outstanding_doc * from_rate)
        closing_base = money(outstanding_doc * closing_rate)
        diff = closing_base - original_base
        if abs(diff) < D("0.01"):
            if bill.carrying_rate is None or D(bill.carrying_rate) != closing_rate:
                touched_bills.append((bill, closing_rate))
            continue

        ap_acc = session.get(Account, bill.ap_account_id) if bill.ap_account_id else default_ap
        if not ap_acc:
            continue

        # AP liability: rate up → increase liability (Cr AP, Dr FX loss)
        if diff > ZERO:
            all_entries += [
                EntryInput(account_id=fx_acc.id, debit=diff),
                EntryInput(account_id=ap_acc.id, credit=diff),
            ]
        else:
            all_entries += [
                EntryInput(account_id=ap_acc.id, debit=-diff),
                EntryInput(account_id=fx_acc.id, credit=-diff),
            ]
        positions.append({
            "doc_type": "bill",
            "id": bill.id,
            "number": bill.number,
            "currency": bill.currency,
            "outstanding_doc": float(outstanding_doc),
            "from_rate": float(from_rate),
            "to_rate": float(closing_rate),
            "base_before": float(original_base),
            "base_after": float(closing_base),
            "diff": float(diff),
        })
        touched_bills.append((bill, closing_rate))

    if not all_entries and not positions:
        # Still persist carrying_rate stamps when rates already match
        for inv, rate in touched_invoices:
            inv.carrying_rate = rate
            session.add(inv)
        for bill, rate in touched_bills:
            bill.carrying_rate = rate
            session.add(bill)
        if touched_invoices or touched_bills:
            session.commit()
        return {
            "message": "No foreign-currency AR/AP positions to revalue",
            "entries_count": 0,
            "positions": [],
        }

    if not all_entries:
        for inv, rate in touched_invoices:
            inv.carrying_rate = rate
            session.add(inv)
        for bill, rate in touched_bills:
            bill.carrying_rate = rate
            session.add(bill)
        session.commit()
        return {
            "message": "No foreign-currency AR/AP positions to revalue",
            "entries_count": 0,
            "positions": [],
        }

    txn = post_transaction(
        session,
        user,
        date=revaluation_date,
        description=f"FX Revaluation as at {revaluation_date}",
        entries=all_entries,
        audit_entity_type="fx_revaluation",
        audit_detail={"revaluation_date": revaluation_date, "positions": len(positions)},
    )
    for inv, rate in touched_invoices:
        inv.carrying_rate = rate
        session.add(inv)
    for bill, rate in touched_bills:
        bill.carrying_rate = rate
        session.add(bill)
    session.commit()
    return {
        "jv_number": txn.jv_number,
        "entries_count": len(all_entries),
        "positions": positions,
    }
