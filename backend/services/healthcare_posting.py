"""
GL-posting helpers for the Healthcare module.

All helpers build balanced JVs via services.posting.post_transaction and
return the created Transaction. Callers are responsible for session.commit().

Account-code lookups are centralised in _acc() so IDs are never hardcoded.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from models import Account, User
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction


def _acc(session: Session, tenant_id: int, code: str) -> Account:
    a = session.exec(
        select(Account).where(Account.tenant_id == tenant_id, Account.code == code)
    ).first()
    if a is None:
        raise HTTPException(
            status_code=400,
            detail=f"CoA is missing account {code!r}. "
                   "Re-seed the CoA or create the account manually.",
        )
    return a


def _ar(session: Session, tenant_id: int) -> Account:
    return _acc(session, tenant_id, "1100")


def _cash(session: Session, tenant_id: int) -> Account:
    return _acc(session, tenant_id, "1000")


# ── OPD Consultation ─────────────────────────────────────────────────────────


def post_opd_consultation(
    session: Session,
    user: User,
    *,
    amount: Decimal,
    date: str,
    patient_name: str,
    doctor_name: str,
    revenue_account_code: str = "4100",
    customer_id: Optional[int] = None,
    reference: Optional[str] = None,
):
    """Dr 1100 AR / Cr 4100 OPD Consultation Revenue."""
    amount = money(D(amount))
    if amount <= ZERO:
        raise HTTPException(400, "OPD fee must be > 0")

    ar = _ar(session, user.tenant_id)
    rev = _acc(session, user.tenant_id, revenue_account_code)

    return post_transaction(
        session, user, date=date,
        description=f"OPD — {patient_name} / Dr {doctor_name}",
        entries=[
            EntryInput(account_id=ar.id, debit=amount, customer_id=customer_id),
            EntryInput(account_id=rev.id, credit=amount),
        ],
        reference=reference,
        audit_entity_type="hc_opd_visit",
    )


# ── IPD Admission Deposit ─────────────────────────────────────────────────────


def post_ipd_deposit(
    session: Session,
    user: User,
    *,
    amount: Decimal,
    date: str,
    patient_name: str,
    admission_number: str,
    cash_account_code: str = "1000",
):
    """Cash deposit on admission.  Dr 1000 Cash / Cr 2310 Patient Advances."""
    amount = money(D(amount))
    if amount <= ZERO:
        raise HTTPException(400, "Deposit amount must be > 0")

    cash = _acc(session, user.tenant_id, cash_account_code)
    adv = _acc(session, user.tenant_id, "2310")

    return post_transaction(
        session, user, date=date,
        description=f"IPD deposit — {patient_name} [{admission_number}]",
        entries=[
            EntryInput(account_id=cash.id, debit=amount),
            EntryInput(account_id=adv.id, credit=amount),
        ],
        audit_entity_type="hc_admission",
    )


# ── Lab Order Billing ─────────────────────────────────────────────────────────


def post_lab_order(
    session: Session,
    user: User,
    *,
    amount: Decimal,
    date: str,
    patient_name: str,
    order_number: str,
    customer_id: Optional[int] = None,
    revenue_account_code: str = "4110",
):
    """Dr 1100 AR / Cr 4110 Laboratory Revenue."""
    amount = money(D(amount))
    if amount <= ZERO:
        raise HTTPException(400, "Lab order amount must be > 0")

    ar = _ar(session, user.tenant_id)
    rev = _acc(session, user.tenant_id, revenue_account_code)

    return post_transaction(
        session, user, date=date,
        description=f"Lab order {order_number} — {patient_name}",
        entries=[
            EntryInput(account_id=ar.id, debit=amount, customer_id=customer_id),
            EntryInput(account_id=rev.id, credit=amount),
        ],
        audit_entity_type="hc_lab_order",
    )


# ── Procedure Billing ─────────────────────────────────────────────────────────


def post_procedure(
    session: Session,
    user: User,
    *,
    amount: Decimal,
    date: str,
    patient_name: str,
    procedure_name: str,
    customer_id: Optional[int] = None,
    revenue_account_code: str = "4120",
):
    """Dr 1100 AR / Cr 4120 Surgical / Procedure Revenue."""
    amount = money(D(amount))
    if amount <= ZERO:
        raise HTTPException(400, "Procedure fee must be > 0")

    ar = _ar(session, user.tenant_id)
    rev = _acc(session, user.tenant_id, revenue_account_code)

    return post_transaction(
        session, user, date=date,
        description=f"Procedure — {procedure_name} / {patient_name}",
        entries=[
            EntryInput(account_id=ar.id, debit=amount, customer_id=customer_id),
            EntryInput(account_id=rev.id, credit=amount),
        ],
        audit_entity_type="hc_procedure_order",
    )


# ── IPD Discharge Bill ────────────────────────────────────────────────────────


def post_discharge_bill(
    session: Session,
    user: User,
    *,
    total_charges: Decimal,
    deposit_amount: Decimal,
    date: str,
    patient_name: str,
    admission_number: str,
    customer_id: Optional[int] = None,
    charge_breakdown: Optional[dict] = None,
):
    """
    Discharge billing: post the consolidated IPD bill and settle the deposit.

    If total_charges > deposit_amount:
        Dr 1100 AR (balance due)      / Cr 4121 Ward Revenue (total charges)
        Dr 2310 Patient Advances      / Cr 1100 AR (settle deposit)
    If total_charges <= deposit_amount:
        Dr 2310 Patient Advances      / Cr 4121 Ward Revenue (total charges)
        Dr 2310 Patient Advances      / Cr 1000 Cash (refund difference)
    """
    total = money(D(total_charges))
    deposit = money(D(deposit_amount))

    ar = _ar(session, user.tenant_id)
    adv = _acc(session, user.tenant_id, "2310")
    rev = _acc(session, user.tenant_id, "4121")
    cash = _cash(session, user.tenant_id)

    balance_due = total - deposit

    if balance_due > ZERO:
        entries = [
            # Full bill to AR
            EntryInput(account_id=ar.id, debit=total, customer_id=customer_id),
            EntryInput(account_id=rev.id, credit=total),
            # Settle deposit against AR
            EntryInput(account_id=adv.id, debit=deposit),
            EntryInput(account_id=ar.id, credit=deposit, customer_id=customer_id),
        ]
    elif balance_due < ZERO:
        refund = abs(balance_due)
        entries = [
            EntryInput(account_id=adv.id, debit=total),
            EntryInput(account_id=rev.id, credit=total),
            # Refund excess deposit in cash
            EntryInput(account_id=adv.id, debit=refund),
            EntryInput(account_id=cash.id, credit=refund),
        ]
    else:
        # Exact match — no AR entry needed
        entries = [
            EntryInput(account_id=adv.id, debit=total),
            EntryInput(account_id=rev.id, credit=total),
        ]

    return post_transaction(
        session, user, date=date,
        description=f"IPD discharge — {patient_name} [{admission_number}]",
        entries=entries,
        audit_entity_type="hc_admission",
        audit_detail={"admission_number": admission_number, "total": str(total),
                      "deposit": str(deposit), "breakdown": charge_breakdown},
    )


# ── Store Issue (internal department transfer or patient charge) ──────────────


def post_store_issue(
    session: Session,
    user: User,
    *,
    amount: Decimal,
    date: str,
    issue_number: str,
    purpose: str,
    charge_to_patient: bool = False,
    customer_id: Optional[int] = None,
):
    """
    Stock issue GL posting.
    - Patient charge:  Dr 1100 AR / Cr 1200 Inventory
    - Internal:        Dr 5120 Medical Supplies Expense / Cr 1200 Inventory
    """
    amount = money(D(amount))
    if amount <= ZERO:
        return None  # zero-value issues (transfers) skip GL

    inv = _acc(session, user.tenant_id, "1200")

    if charge_to_patient:
        ar = _ar(session, user.tenant_id)
        dr_acc = ar
        dr_kwargs = {"customer_id": customer_id}
    else:
        expense_code = "5130" if purpose == "lab" else "5120"
        dr_acc = _acc(session, user.tenant_id, expense_code)
        dr_kwargs = {}

    return post_transaction(
        session, user, date=date,
        description=f"Store issue {issue_number} — {purpose}",
        entries=[
            EntryInput(account_id=dr_acc.id, debit=amount, **dr_kwargs),
            EntryInput(account_id=inv.id, credit=amount),
        ],
        audit_entity_type="hc_store_issue",
    )
