"""Tracker Account — the franchisee's Tracker wallet per telecom operator.

Covers:
  - CRUD for tracker accounts
  - Tracker deposit (Dr 1210 / Cr Bank)
  - Load order (Dr 1211×103% / Cr 1210×100% / Cr 4020×3%)
  - SIM/IMSI stock debit (Dr 1200 Inventory / Cr 1210)
  - FCA commission credit (Dr 1210 or Bank / Cr 4060)
  - Penalty debit (Dr 5090 / Cr 1210)
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import Account, JournalEntry, TrackerAccount, TrackerTransaction
from services.money import D, ZERO
from services.posting import EntryInput, post_transaction

from ..common import (
    CurrentUserDep, SessionDep, WriteUserDep,
    get_or_create_account, log_audit, next_number,
)

router = APIRouter(prefix="/api/telecom", tags=["telecom"])

COMMISSION_RATE = Decimal("0.03")


# ── helpers ──────────────────────────────────────────────────────────────────

def _gl_balance(session, tenant_id: int, code: str) -> Decimal:
    """Sum debit-credit for the first account matching `code` in this tenant."""
    acc = session.exec(
        select(Account).where(Account.tenant_id == tenant_id, Account.code == code)
    ).first()
    if not acc:
        return ZERO
    entries = session.exec(
        select(JournalEntry).where(
            JournalEntry.account_id == acc.id,
            JournalEntry.tenant_id == tenant_id,
        )
    ).all()
    if acc.type in ("Asset", "Expense"):
        return sum((D(e.debit) - D(e.credit) for e in entries), ZERO)
    return sum((D(e.credit) - D(e.debit) for e in entries), ZERO)


def _get_tracker(session, tenant_id: int, tracker_id: int) -> TrackerAccount:
    ta = session.get(TrackerAccount, tracker_id)
    if not ta or ta.tenant_id != tenant_id:
        raise HTTPException(404, "Tracker account not found")
    return ta


# ── request / response schemas ────────────────────────────────────────────────

class TrackerAccountCreate(BaseModel):
    operator_name: str
    operator_code: str
    account_reference: str


class TrackerAccountUpdate(BaseModel):
    operator_name: Optional[str] = None
    operator_code: Optional[str] = None
    account_reference: Optional[str] = None
    is_active: Optional[bool] = None


class DepositIn(BaseModel):
    txn_date: str
    amount: Decimal
    bank_account_code: str = "1010"   # default bank account code
    tracker_reference: Optional[str] = None
    notes: Optional[str] = None


class LoadOrderIn(BaseModel):
    txn_date: str
    amount_paid: Decimal              # cash debited from Tracker
    tracker_reference: Optional[str] = None
    notes: Optional[str] = None


class StockDebitIn(BaseModel):
    txn_date: str
    amount: Decimal
    inventory_account_code: str = "1200"  # SIM Card Inventory by default
    tracker_reference: Optional[str] = None
    notes: Optional[str] = None


class CommissionIn(BaseModel):
    txn_date: str
    amount: Decimal
    credit_method: str = "tracker"    # "tracker" (Dr 1210) or "bank" (Dr 1010)
    tracker_reference: Optional[str] = None
    notes: Optional[str] = None


class PenaltyIn(BaseModel):
    txn_date: str
    amount: Decimal
    tracker_reference: Optional[str] = None
    notes: Optional[str] = None


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("/tracker-accounts")
def list_tracker_accounts(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(TrackerAccount).where(TrackerAccount.tenant_id == user.tenant_id)
    ).all()
    return {"items": [
        {
            **r.model_dump(),
            "gl_deposit_balance": _gl_balance(session, user.tenant_id, "1210"),
            "gl_load_balance":    _gl_balance(session, user.tenant_id, "1211"),
        }
        for r in rows
    ]}


@router.post("/tracker-accounts", status_code=201)
def create_tracker_account(
    body: TrackerAccountCreate,
    session: SessionDep,
    user: WriteUserDep,
):
    # Ensure CoA accounts exist
    deposit_acc = get_or_create_account(session, user.tenant_id, "1210",
                                        "Tracker Deposit Balance", "Asset")
    load_acc    = get_or_create_account(session, user.tenant_id, "1211",
                                        "Load Float Asset (MSR SIM)", "Asset")
    ta = TrackerAccount(
        tenant_id=user.tenant_id,
        operator_name=body.operator_name,
        operator_code=body.operator_code,
        account_reference=body.account_reference,
        deposit_account_id=deposit_acc.id,
        load_account_id=load_acc.id,
    )
    session.add(ta)
    session.flush()
    log_audit(session, user, "CREATE", "tracker_account", ta.id,
              {"operator_code": body.operator_code})
    session.commit()
    session.refresh(ta)
    return ta


@router.get("/tracker-accounts/{tracker_id}")
def get_tracker_account(tracker_id: int, session: SessionDep, user: CurrentUserDep):
    ta = _get_tracker(session, user.tenant_id, tracker_id)
    txns = session.exec(
        select(TrackerTransaction).where(
            TrackerTransaction.tenant_id == user.tenant_id,
            TrackerTransaction.tracker_account_id == tracker_id,
        ).order_by(TrackerTransaction.txn_date.desc())
    ).all()
    return {
        **ta.model_dump(),
        "gl_deposit_balance": _gl_balance(session, user.tenant_id, "1210"),
        "gl_load_balance":    _gl_balance(session, user.tenant_id, "1211"),
        "transactions": [t.model_dump() for t in txns],
    }


@router.patch("/tracker-accounts/{tracker_id}")
def update_tracker_account(
    tracker_id: int,
    body: TrackerAccountUpdate,
    session: SessionDep,
    user: WriteUserDep,
):
    ta = _get_tracker(session, user.tenant_id, tracker_id)
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(ta, field, val)
    session.add(ta)
    log_audit(session, user, "UPDATE", "tracker_account", ta.id)
    session.commit()
    session.refresh(ta)
    return ta


# ── GL posting endpoints ──────────────────────────────────────────────────────

@router.post("/tracker-accounts/{tracker_id}/deposit", status_code=201)
def post_deposit(
    tracker_id: int,
    body: DepositIn,
    session: SessionDep,
    user: WriteUserDep,
):
    """Franchisee transfers cash from bank to Tracker.
    Dr 1210 Tracker Deposit / Cr 1010 Bank"""
    ta = _get_tracker(session, user.tenant_id, tracker_id)
    amt = D(body.amount)

    deposit_acc = get_or_create_account(session, user.tenant_id, "1210",
                                        "Tracker Deposit Balance", "Asset")
    bank_acc    = get_or_create_account(session, user.tenant_id, body.bank_account_code,
                                        "Bank", "Asset")

    ref = next_number(session, user.tenant_id, "tracker_txn", "TRK")
    txn = post_transaction(
        session, user,
        date=body.txn_date,
        description=f"Tracker deposit – {ta.operator_name}",
        reference=ref,
        entries=[
            EntryInput(account_id=deposit_acc.id, debit=amt),
            EntryInput(account_id=bank_acc.id,    credit=amt),
        ],
        audit_entity_type="tracker_transaction",
    )

    tt = TrackerTransaction(
        tenant_id=user.tenant_id,
        tracker_account_id=tracker_id,
        txn_date=body.txn_date,
        txn_type="deposit",
        amount=amt,
        tracker_reference=body.tracker_reference,
        transaction_id=txn.id,
        notes=body.notes,
    )
    session.add(tt)

    ta.deposit_balance = D(ta.deposit_balance) + amt
    session.add(ta)

    session.commit()
    session.refresh(tt)
    return {"tracker_transaction": tt.model_dump(), "jv_number": txn.jv_number}


@router.post("/tracker-accounts/{tracker_id}/load-order", status_code=201)
def post_load_order(
    tracker_id: int,
    body: LoadOrderIn,
    session: SessionDep,
    user: WriteUserDep,
):
    """Franchisee orders load from Tracker.
    Tracker debits 100%, MSR SIM receives 103%.
    Dr 1211 Load Float (103%) / Cr 1210 Tracker Deposit (100%) / Cr 4020 Commission (3%)"""
    ta = _get_tracker(session, user.tenant_id, tracker_id)
    paid       = D(body.amount_paid)
    commission = (paid * COMMISSION_RATE).quantize(Decimal("0.0001"))
    disbursed  = paid + commission

    if D(ta.deposit_balance) < paid:
        raise HTTPException(400, "Insufficient Tracker deposit balance")

    deposit_acc    = get_or_create_account(session, user.tenant_id, "1210",
                                           "Tracker Deposit Balance", "Asset")
    load_acc       = get_or_create_account(session, user.tenant_id, "1211",
                                           "Load Float Asset (MSR SIM)", "Asset")
    commission_acc = get_or_create_account(session, user.tenant_id, "4020",
                                           "Load Uplift Commission (3%)", "Revenue")

    ref = next_number(session, user.tenant_id, "tracker_txn", "TRK")
    txn = post_transaction(
        session, user,
        date=body.txn_date,
        description=f"Load order – {ta.operator_name} (paid {paid})",
        reference=ref,
        entries=[
            EntryInput(account_id=load_acc.id,       debit=disbursed),
            EntryInput(account_id=deposit_acc.id,    credit=paid),
            EntryInput(account_id=commission_acc.id, credit=commission),
        ],
        audit_entity_type="tracker_transaction",
    )

    tt = TrackerTransaction(
        tenant_id=user.tenant_id,
        tracker_account_id=tracker_id,
        txn_date=body.txn_date,
        txn_type="load_order",
        amount=paid,
        load_disbursed=disbursed,
        commission_earned=commission,
        tracker_reference=body.tracker_reference,
        transaction_id=txn.id,
        notes=body.notes,
    )
    session.add(tt)

    ta.deposit_balance = D(ta.deposit_balance) - paid
    ta.load_balance    = D(ta.load_balance)    + disbursed
    session.add(ta)

    session.commit()
    session.refresh(tt)
    return {
        "tracker_transaction": tt.model_dump(),
        "jv_number": txn.jv_number,
        "load_disbursed": str(disbursed),
        "commission_earned": str(commission),
    }


@router.post("/tracker-accounts/{tracker_id}/stock-debit", status_code=201)
def post_stock_debit(
    tracker_id: int,
    body: StockDebitIn,
    session: SessionDep,
    user: WriteUserDep,
):
    """Telecom company issues SIM/IMSI stock; Tracker auto-debits.
    Dr Inventory (1200/1201) / Cr 1210 Tracker Deposit"""
    ta = _get_tracker(session, user.tenant_id, tracker_id)
    amt = D(body.amount)

    if D(ta.deposit_balance) < amt:
        raise HTTPException(400, "Insufficient Tracker deposit balance")

    inventory_acc = get_or_create_account(session, user.tenant_id,
                                          body.inventory_account_code,
                                          "SIM Card Inventory", "Asset")
    deposit_acc   = get_or_create_account(session, user.tenant_id, "1210",
                                          "Tracker Deposit Balance", "Asset")

    ref = next_number(session, user.tenant_id, "tracker_txn", "TRK")
    txn = post_transaction(
        session, user,
        date=body.txn_date,
        description=f"SIM/IMSI stock debit – {ta.operator_name}",
        reference=ref,
        entries=[
            EntryInput(account_id=inventory_acc.id, debit=amt),
            EntryInput(account_id=deposit_acc.id,   credit=amt),
        ],
        audit_entity_type="tracker_transaction",
    )

    tt = TrackerTransaction(
        tenant_id=user.tenant_id,
        tracker_account_id=tracker_id,
        txn_date=body.txn_date,
        txn_type="stock_debit",
        amount=amt,
        tracker_reference=body.tracker_reference,
        transaction_id=txn.id,
        notes=body.notes,
    )
    session.add(tt)

    ta.deposit_balance = D(ta.deposit_balance) - amt
    session.add(ta)

    session.commit()
    session.refresh(tt)
    return {"tracker_transaction": tt.model_dump(), "jv_number": txn.jv_number}


@router.post("/tracker-accounts/{tracker_id}/commission", status_code=201)
def post_fca_commission(
    tracker_id: int,
    body: CommissionIn,
    session: SessionDep,
    user: WriteUserDep,
):
    """Month-end FCA target commission credited by operator.
    Dr 1210 Tracker Deposit (or Dr 1010 Bank) / Cr 4060 FCA Target Commission"""
    ta = _get_tracker(session, user.tenant_id, tracker_id)
    amt = D(body.amount)

    commission_rev = get_or_create_account(session, user.tenant_id, "4060",
                                           "FCA Target Commission", "Revenue")
    if body.credit_method == "bank":
        debit_acc = get_or_create_account(session, user.tenant_id, "1010", "Bank", "Asset")
    else:
        debit_acc = get_or_create_account(session, user.tenant_id, "1210",
                                          "Tracker Deposit Balance", "Asset")

    ref = next_number(session, user.tenant_id, "tracker_txn", "TRK")
    txn = post_transaction(
        session, user,
        date=body.txn_date,
        description=f"FCA commission – {ta.operator_name}",
        reference=ref,
        entries=[
            EntryInput(account_id=debit_acc.id,      debit=amt),
            EntryInput(account_id=commission_rev.id, credit=amt),
        ],
        audit_entity_type="tracker_transaction",
    )

    tt = TrackerTransaction(
        tenant_id=user.tenant_id,
        tracker_account_id=tracker_id,
        txn_date=body.txn_date,
        txn_type="commission_credit",
        amount=amt,
        tracker_reference=body.tracker_reference,
        transaction_id=txn.id,
        notes=body.notes,
    )
    session.add(tt)

    if body.credit_method != "bank":
        ta.deposit_balance = D(ta.deposit_balance) + amt
        session.add(ta)

    session.commit()
    session.refresh(tt)
    return {"tracker_transaction": tt.model_dump(), "jv_number": txn.jv_number}


@router.post("/tracker-accounts/{tracker_id}/penalty", status_code=201)
def post_penalty(
    tracker_id: int,
    body: PenaltyIn,
    session: SessionDep,
    user: WriteUserDep,
):
    """Operator deducts penalty for missing FCA target.
    Dr 5090 Target Shortfall Penalties / Cr 1210 Tracker Deposit"""
    ta = _get_tracker(session, user.tenant_id, tracker_id)
    amt = D(body.amount)

    penalty_exp  = get_or_create_account(session, user.tenant_id, "5090",
                                         "Target Shortfall Penalties", "Expense")
    deposit_acc  = get_or_create_account(session, user.tenant_id, "1210",
                                         "Tracker Deposit Balance", "Asset")

    ref = next_number(session, user.tenant_id, "tracker_txn", "TRK")
    txn = post_transaction(
        session, user,
        date=body.txn_date,
        description=f"FCA target penalty – {ta.operator_name}",
        reference=ref,
        entries=[
            EntryInput(account_id=penalty_exp.id, debit=amt),
            EntryInput(account_id=deposit_acc.id, credit=amt),
        ],
        audit_entity_type="tracker_transaction",
    )

    tt = TrackerTransaction(
        tenant_id=user.tenant_id,
        tracker_account_id=tracker_id,
        txn_date=body.txn_date,
        txn_type="penalty_debit",
        amount=amt,
        tracker_reference=body.tracker_reference,
        transaction_id=txn.id,
        notes=body.notes,
    )
    session.add(tt)

    ta.deposit_balance = D(ta.deposit_balance) - amt
    session.add(ta)

    session.commit()
    session.refresh(tt)
    return {"tracker_transaction": tt.model_dump(), "jv_number": txn.jv_number}
