"""IAS 21 settlement math for customer receipts and bill payments.

Payment amounts and allocations are in document currency. Settlement rate
converts to tenant base. AR/AP is cleared at each document's carrying rate
(post-revaluation) or issue exchange_rate.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Literal, Optional, Sequence

from fastapi import HTTPException
from sqlmodel import Session, select

from models import Account, Bill, Invoice, Tenant
from services.fx import rate_to_base
from services.money import D, ONE, ZERO, money
from services.posting import EntryInput


Side = Literal["receipt", "bill_payment"]


@dataclass(frozen=True)
class AllocDoc:
    """One allocation line resolved against its source document."""
    doc_id: int
    amount: Decimal  # document currency
    currency: str
    carrying_rate: Decimal
    clear_account_id: int  # AR or AP account id


@dataclass(frozen=True)
class SettlementPlan:
    currency: str
    settlement_rate: Decimal
    is_fx: bool
    entries: list[EntryInput]
    cash_base: Decimal
    cleared_base: Decimal
    realised: Decimal  # >0 gain for receipts / gain for AP when cash < carrying


def doc_carrying_rate(doc: Invoice | Bill) -> Decimal:
    if doc.carrying_rate is not None:
        return D(doc.carrying_rate)
    return D(doc.exchange_rate)


def resolve_settlement_rate(
    session: Session,
    tenant_id: int,
    currency: str,
    payment_date: str,
    explicit: Optional[Decimal],
) -> Decimal:
    tenant = session.get(Tenant, tenant_id)
    base = tenant.base_currency if tenant else "USD"
    if explicit is not None:
        rate = D(explicit)
        if rate <= ZERO:
            raise HTTPException(400, "exchange_rate must be > 0")
        return rate
    if currency == base:
        return ONE
    try:
        return rate_to_base(session, tenant_id, currency, payment_date)
    except LookupError as exc:
        raise HTTPException(400, str(exc)) from exc


def _default_clear_account(
    session: Session, tenant_id: int, code: str, name: str, acc_type: str
) -> Account:
    from routers.common import get_or_create_account
    return get_or_create_account(session, tenant_id, code, name, acc_type)


def resolve_invoice_allocs(
    session: Session,
    tenant_id: int,
    allocations: Sequence[tuple[int, Decimal]],
) -> list[AllocDoc]:
    """allocations: (invoice_id, amount_doc)."""
    out: list[AllocDoc] = []
    default_ar: Optional[Account] = None
    for inv_id, amt in allocations:
        inv = session.get(Invoice, inv_id)
        if not inv or inv.tenant_id != tenant_id:
            raise HTTPException(400, f"Invoice {inv_id} not found for tenant")
        if inv.ar_account_id:
            ar_id = inv.ar_account_id
        else:
            if default_ar is None:
                default_ar = _default_clear_account(
                    session, tenant_id, "1100", "Accounts Receivable", "Asset"
                )
            ar_id = default_ar.id
        out.append(
            AllocDoc(
                doc_id=inv.id,
                amount=money(amt),
                currency=inv.currency,
                carrying_rate=doc_carrying_rate(inv),
                clear_account_id=ar_id,
            )
        )
    return out


def resolve_bill_allocs(
    session: Session,
    tenant_id: int,
    allocations: Sequence[tuple[int, Decimal]],
) -> list[AllocDoc]:
    out: list[AllocDoc] = []
    default_ap: Optional[Account] = None
    for bill_id, amt in allocations:
        bill = session.get(Bill, bill_id)
        if not bill or bill.tenant_id != tenant_id:
            raise HTTPException(400, f"Bill {bill_id} not found for tenant")
        if bill.ap_account_id:
            ap_id = bill.ap_account_id
        else:
            if default_ap is None:
                default_ap = _default_clear_account(
                    session, tenant_id, "2000", "Accounts Payable", "Liability"
                )
            ap_id = default_ap.id
        out.append(
            AllocDoc(
                doc_id=bill.id,
                amount=money(amt),
                currency=bill.currency,
                carrying_rate=doc_carrying_rate(bill),
                clear_account_id=ap_id,
            )
        )
    return out


def _require_single_currency(docs: Iterable[AllocDoc]) -> str:
    currencies = {d.currency for d in docs}
    if len(currencies) > 1:
        raise HTTPException(
            400,
            "Cannot allocate one payment across mixed document currencies",
        )
    return next(iter(currencies))


def build_settlement(
    session: Session,
    *,
    tenant_id: int,
    side: Side,
    payment_amount: Decimal,
    payment_date: str,
    cash_account_id: int,
    currency: Optional[str],
    exchange_rate: Optional[Decimal],
    allocs: list[AllocDoc],
    analytic_account_id: Optional[int] = None,
    party_customer_id: Optional[int] = None,
    party_vendor_id: Optional[int] = None,
) -> SettlementPlan:
    """Build balanced GL entries for a payment.

    Base-currency path (no FX): single Dr/Cr of payment_amount (legacy).
    FX path: require full allocation; clear at carrying; cash at settle rate;
    plug realised FX on 4903.
    """
    from routers.common import get_or_create_account

    tenant = session.get(Tenant, tenant_id)
    base = tenant.base_currency if tenant else "USD"
    amount = money(payment_amount)
    alloc_total = money(sum((d.amount for d in allocs), start=ZERO))

    if allocs:
        doc_currency = _require_single_currency(allocs)
    else:
        doc_currency = currency or base

    pay_currency = currency or doc_currency
    if allocs and pay_currency != doc_currency:
        raise HTTPException(
            400,
            f"Payment currency {pay_currency} must match allocated documents ({doc_currency})",
        )

    settle_rate = resolve_settlement_rate(
        session, tenant_id, pay_currency, payment_date, exchange_rate
    )
    is_fx = pay_currency != base

    if is_fx:
        if not allocs:
            raise HTTPException(400, "FX payments require full allocation to open documents")
        if abs(alloc_total - amount) >= D("0.01"):
            raise HTTPException(
                400,
                "FX payment amount must equal the sum of allocations (no unallocated remainder)",
            )

        cash_base = money(amount * settle_rate)
        # Aggregate clear amounts by AR/AP account
        by_acc: dict[int, Decimal] = {}
        for d in allocs:
            by_acc[d.clear_account_id] = by_acc.get(d.clear_account_id, ZERO) + money(
                d.amount * d.carrying_rate
            )
        cleared_base = money(sum(by_acc.values(), start=ZERO))
        realised = money(cash_base - cleared_base)

        fx_acc = get_or_create_account(
            session, tenant_id, "4903", "Realised FX Gain/Loss", "Revenue"
        )
        entries: list[EntryInput] = []

        if side == "receipt":
            entries.append(
                EntryInput(
                    account_id=cash_account_id,
                    debit=cash_base,
                    analytic_account_id=analytic_account_id,
                )
            )
            for acc_id, base_amt in by_acc.items():
                entries.append(
                    EntryInput(
                        account_id=acc_id,
                        credit=base_amt,
                        analytic_account_id=analytic_account_id,
                        customer_id=party_customer_id,
                    )
                )
            if realised > ZERO:
                # Gain: cash > carrying AR → Cr Realised FX
                entries.append(
                    EntryInput(account_id=fx_acc.id, credit=realised, analytic_account_id=analytic_account_id)
                )
            elif realised < ZERO:
                entries.append(
                    EntryInput(account_id=fx_acc.id, debit=-realised, analytic_account_id=analytic_account_id)
                )
        else:
            for acc_id, base_amt in by_acc.items():
                entries.append(
                    EntryInput(
                        account_id=acc_id,
                        debit=base_amt,
                        analytic_account_id=analytic_account_id,
                        vendor_id=party_vendor_id,
                    )
                )
            entries.append(
                EntryInput(
                    account_id=cash_account_id,
                    credit=cash_base,
                    analytic_account_id=analytic_account_id,
                )
            )
            # AP: cash_base > cleared → loss (Dr FX); cash < cleared → gain (Cr FX)
            if realised > ZERO:
                entries.append(
                    EntryInput(account_id=fx_acc.id, debit=realised, analytic_account_id=analytic_account_id)
                )
            elif realised < ZERO:
                entries.append(
                    EntryInput(account_id=fx_acc.id, credit=-realised, analytic_account_id=analytic_account_id)
                )

        return SettlementPlan(
            currency=pay_currency,
            settlement_rate=settle_rate,
            is_fx=True,
            entries=entries,
            cash_base=cash_base,
            cleared_base=cleared_base,
            realised=realised if side == "receipt" else money(-realised),
        )

    # Base-currency / legacy path — single two-line JV for payment amount
    ar_or_ap = _default_clear_account(
        session,
        tenant_id,
        "1100" if side == "receipt" else "2000",
        "Accounts Receivable" if side == "receipt" else "Accounts Payable",
        "Asset" if side == "receipt" else "Liability",
    )
    if side == "receipt":
        entries = [
            EntryInput(
                account_id=cash_account_id,
                debit=amount,
                analytic_account_id=analytic_account_id,
            ),
            EntryInput(
                account_id=ar_or_ap.id,
                credit=amount,
                analytic_account_id=analytic_account_id,
                customer_id=party_customer_id,
            ),
        ]
    else:
        entries = [
            EntryInput(
                account_id=ar_or_ap.id,
                debit=amount,
                analytic_account_id=analytic_account_id,
                vendor_id=party_vendor_id,
            ),
            EntryInput(
                account_id=cash_account_id,
                credit=amount,
                analytic_account_id=analytic_account_id,
            ),
        ]
    return SettlementPlan(
        currency=pay_currency,
        settlement_rate=settle_rate,
        is_fx=False,
        entries=entries,
        cash_base=amount,
        cleared_base=amount,
        realised=ZERO,
    )
