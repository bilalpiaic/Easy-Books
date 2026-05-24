"""
Remaining GL-posting helpers for telecom-franchise:
  * Mobile money (deposit / withdrawal / top-up / commission / reconciliation)
  * Commission accrual + statement reconciliation
  * Postpaid billing (bill / collect / remit)
  * Device IMEI sales
  * Franchise fee capitalisation + monthly amortisation
  * Royalty accrual + payment
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlmodel import Session, select

from models import Account, Transaction, User
from models_telecom import (
    CommissionLine, CommissionStatement, FranchiseAgreement,
    MobileMoneyAccount, MobileMoneyTransaction, PostpaidBillCycle,
    PostpaidConnection, SimActivation,
)
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction
from services.tracker_posting import _acc


# ── Mobile money ──────────────────────────────────────────────────────────


def post_mm_float_top_up(
    session: Session, user: User, *,
    mm_account: MobileMoneyAccount,
    amount: Decimal, date: str,
    cash_account_code: str = "1000",
) -> Tuple[MobileMoneyTransaction, Transaction]:
    """Dr 1214 MM Float Asset / Cr Cash."""
    amt = money(D(amount))
    if amt <= ZERO:
        raise HTTPException(status_code=400, detail="Top-up must be > 0")
    float_a = _acc(session, user.tenant_id, "1214")
    cash = _acc(session, user.tenant_id, cash_account_code)
    txn = post_transaction(
        session, user, date=date,
        description=f"MM float top-up — {mm_account.account_number} ({amt})",
        entries=[
            EntryInput(account_id=float_a.id, debit=amt),
            EntryInput(account_id=cash.id, credit=amt),
        ],
        audit_entity_type="mm_float_top_up",
        audit_detail={"mm_account_id": mm_account.id, "amount": str(amt)},
    )
    mt = MobileMoneyTransaction(
        tenant_id=user.tenant_id, mm_account_id=mm_account.id,
        txn_date=date, txn_type="float_top_up", amount=amt,
        transaction_id=txn.id,
    )
    session.add(mt)
    mm_account.current_float_balance = money(D(mm_account.current_float_balance) + amt)
    session.add(mm_account)
    return mt, txn


def post_mm_customer_deposit(
    session: Session, user: User, *,
    mm_account: MobileMoneyAccount,
    amount: Decimal, date: str,
    customer_reference: Optional[str] = None,
    cash_account_code: str = "1000",
) -> Tuple[MobileMoneyTransaction, Transaction]:
    """Customer cash-in. Dr Cash / Cr 2100 MM Float Liability.
    The franchise's float at operator is debited as the customer wallet is
    credited, so mm_account.current_float_balance DECREASES."""
    amt = money(D(amount))
    cash = _acc(session, user.tenant_id, cash_account_code)
    float_l = _acc(session, user.tenant_id, "2100")
    txn = post_transaction(
        session, user, date=date,
        description=f"MM customer deposit — {mm_account.account_number} ({amt})",
        entries=[
            EntryInput(account_id=cash.id, debit=amt),
            EntryInput(account_id=float_l.id, credit=amt),
        ],
        audit_entity_type="mm_deposit",
        audit_detail={"mm_account_id": mm_account.id, "amount": str(amt),
                      "customer_reference": customer_reference},
    )
    mt = MobileMoneyTransaction(
        tenant_id=user.tenant_id, mm_account_id=mm_account.id,
        txn_date=date, txn_type="deposit", amount=amt,
        customer_reference=customer_reference,
        transaction_id=txn.id,
    )
    session.add(mt)
    mm_account.current_float_balance = money(D(mm_account.current_float_balance) - amt)
    session.add(mm_account)
    return mt, txn


def post_mm_customer_withdrawal(
    session: Session, user: User, *,
    mm_account: MobileMoneyAccount,
    amount: Decimal, date: str,
    customer_reference: Optional[str] = None,
    cash_account_code: str = "1000",
) -> Tuple[MobileMoneyTransaction, Transaction]:
    """Customer cash-out. Dr 2100 Float Liability / Cr Cash."""
    amt = money(D(amount))
    cash = _acc(session, user.tenant_id, cash_account_code)
    float_l = _acc(session, user.tenant_id, "2100")
    txn = post_transaction(
        session, user, date=date,
        description=f"MM customer withdrawal — {mm_account.account_number} ({amt})",
        entries=[
            EntryInput(account_id=float_l.id, debit=amt),
            EntryInput(account_id=cash.id, credit=amt),
        ],
        audit_entity_type="mm_withdrawal",
        audit_detail={"mm_account_id": mm_account.id, "amount": str(amt),
                      "customer_reference": customer_reference},
    )
    mt = MobileMoneyTransaction(
        tenant_id=user.tenant_id, mm_account_id=mm_account.id,
        txn_date=date, txn_type="withdrawal", amount=amt,
        customer_reference=customer_reference,
        transaction_id=txn.id,
    )
    session.add(mt)
    mm_account.current_float_balance = money(D(mm_account.current_float_balance) + amt)
    session.add(mm_account)
    return mt, txn


def post_mm_commission_credit(
    session: Session, user: User, *,
    mm_account: MobileMoneyAccount,
    amount: Decimal, date: str,
    credit_to: str = "float",   # "float" → Dr 1214; "bank" → Dr 1010
    bank_account_code: str = "1010",
) -> Tuple[MobileMoneyTransaction, Transaction]:
    """Dr 1214 (or Bank) / Cr 4022 Commission Income — Digital."""
    amt = money(D(amount))
    debit_acc = (
        _acc(session, user.tenant_id, "1214") if credit_to == "float"
        else _acc(session, user.tenant_id, bank_account_code)
    )
    commission = _acc(session, user.tenant_id, "4022")
    txn = post_transaction(
        session, user, date=date,
        description=f"MM commission credit — {mm_account.account_number} ({amt})",
        entries=[
            EntryInput(account_id=debit_acc.id, debit=amt),
            EntryInput(account_id=commission.id, credit=amt),
        ],
        audit_entity_type="mm_commission",
        audit_detail={"mm_account_id": mm_account.id, "amount": str(amt)},
    )
    mt = MobileMoneyTransaction(
        tenant_id=user.tenant_id, mm_account_id=mm_account.id,
        txn_date=date, txn_type="commission_credit", amount=amt,
        commission_earned=amt, transaction_id=txn.id,
    )
    session.add(mt)
    if credit_to == "float":
        mm_account.current_float_balance = money(D(mm_account.current_float_balance) + amt)
        session.add(mm_account)
    return mt, txn


def post_mm_reconciliation(
    session: Session, user: User, *,
    mm_account: MobileMoneyAccount,
    statement_balance: Decimal, date: str,
) -> Optional[Transaction]:
    """Reconcile system float vs operator statement. Posts difference to
    5070 (shortage) or 4900 (overage). Returns None if exactly equal."""
    sys_bal = D(mm_account.current_float_balance)
    stmt_bal = D(statement_balance)
    diff = money(stmt_bal - sys_bal)
    if diff == ZERO:
        return None
    float_a = _acc(session, user.tenant_id, "1214")
    if diff < ZERO:  # shortage — Dr expense / Cr asset
        expense = _acc(session, user.tenant_id, "5070")
        amt = -diff
        entries = [EntryInput(account_id=expense.id, debit=amt),
                   EntryInput(account_id=float_a.id, credit=amt)]
    else:  # overage — Dr asset / Cr income
        income = _acc(session, user.tenant_id, "4900")
        amt = diff
        entries = [EntryInput(account_id=float_a.id, debit=amt),
                   EntryInput(account_id=income.id, credit=amt)]
    txn = post_transaction(
        session, user, date=date,
        description=f"MM reconciliation — {mm_account.account_number} (diff {diff})",
        entries=entries,
        audit_entity_type="mm_reconciliation",
        audit_detail={"mm_account_id": mm_account.id, "diff": str(diff)},
    )
    mm_account.current_float_balance = money(stmt_bal)
    session.add(mm_account)
    return txn


# ── Commission accrual + settlement ───────────────────────────────────────


def post_commission_accrual(
    session: Session, user: User, *,
    activation: SimActivation,
    amount: Decimal,
    date: str,
    revenue_account_code: str = "4020",
) -> Transaction:
    """Dr 1110 Commission Receivable / Cr revenue account."""
    amt = money(D(amount))
    if amt <= ZERO:
        raise HTTPException(status_code=400, detail="Commission must be > 0")
    if activation.commission_status == "settled":
        raise HTTPException(status_code=400, detail="Activation commission already settled")
    receivable = _acc(session, user.tenant_id, "1110")
    revenue = _acc(session, user.tenant_id, revenue_account_code)
    txn = post_transaction(
        session, user, date=date,
        description=f"Commission accrual — SIM {activation.sim_number} ({amt})",
        entries=[
            EntryInput(account_id=receivable.id, debit=amt),
            EntryInput(account_id=revenue.id, credit=amt),
        ],
        audit_entity_type="commission_accrual",
        audit_detail={"activation_id": activation.id, "amount": str(amt)},
    )
    activation.commission_status = "accrued"
    activation.commission_transaction_id = txn.id
    session.add(activation)
    return txn


def post_commission_statement_settlement(
    session: Session, user: User, *,
    statement: CommissionStatement,
    settlement_amount: Decimal,
    date: str,
    credit_via: str = "bank",   # "bank" | "tracker"
    bank_account_code: str = "1010",
) -> Transaction:
    """Dr Bank/Tracker / Cr 1110 Commission Receivable (accrued)
    + balancing Cr 4061 Franchise Incentive Income (over-accrual)
    or  Dr 5000 General Expenses (under-accrual / dispute)."""
    settled = money(D(settlement_amount))
    accrued = money(sum(
        (D(l.accrued_amount) for l in session.exec(
            select(CommissionLine).where(CommissionLine.statement_id == statement.id)
        ).all()),
        ZERO,
    ))
    debit_acc = (
        _acc(session, user.tenant_id, bank_account_code) if credit_via == "bank"
        else _acc(session, user.tenant_id, "1210")
    )
    receivable = _acc(session, user.tenant_id, "1110")

    entries = []
    if settled > ZERO:
        entries.append(EntryInput(account_id=debit_acc.id, debit=settled))
    # Only clear the receivable when commission was actually accrued; a
    # statement recorded without line detail has nothing booked to 1110.
    if accrued > ZERO:
        entries.append(EntryInput(account_id=receivable.id, credit=accrued))
    variance = money(settled - accrued)
    if variance > ZERO:
        incentive = _acc(session, user.tenant_id, "4061")
        entries.append(EntryInput(account_id=incentive.id, credit=variance))
    elif variance < ZERO:
        # Adverse variance — book to general expense, mark statement disputed.
        expense = _acc(session, user.tenant_id, "5000")
        entries.append(EntryInput(account_id=expense.id, debit=-variance))

    txn = post_transaction(
        session, user, date=date,
        description=f"Commission statement settlement #{statement.id} "
                    f"({settled} vs accrued {accrued})",
        entries=entries,
        audit_entity_type="commission_settlement",
        audit_detail={"statement_id": statement.id, "settled": str(settled),
                      "accrued": str(accrued), "variance": str(variance)},
    )
    statement.status = "reconciled" if variance >= ZERO else "disputed"
    statement.transaction_id = txn.id
    session.add(statement)
    return txn


# ── Postpaid billing ──────────────────────────────────────────────────────


def post_postpaid_bill(
    session: Session, user: User, *,
    connection: PostpaidConnection,
    billing_month: str,
    gross_amount: Decimal,
) -> Tuple[PostpaidBillCycle, Transaction]:
    """Dr 1130 Postpaid Cust Rec / Cr 2110 Postpaid Collections Payable
    (gross). Franchise commission split happens at remittance, not bill."""
    gross = money(D(gross_amount))
    commission_rate = D(connection.franchise_commission_rate)
    commission = money(gross * commission_rate / D("100"))
    net = money(gross - commission)

    receivable = _acc(session, user.tenant_id, "1130")
    payable = _acc(session, user.tenant_id, "2110")
    txn = post_transaction(
        session, user, date=billing_month,
        description=f"Postpaid bill {connection.msisdn} ({billing_month}) — {gross}",
        entries=[
            EntryInput(account_id=receivable.id, debit=gross),
            EntryInput(account_id=payable.id, credit=gross),
        ],
        audit_entity_type="postpaid_bill",
        audit_detail={"connection_id": connection.id, "month": billing_month,
                      "gross": str(gross)},
    )
    cycle = PostpaidBillCycle(
        tenant_id=user.tenant_id, connection_id=connection.id,
        billing_month=billing_month,
        gross_amount=gross, franchise_commission=commission, net_remittance=net,
    )
    session.add(cycle); session.flush()
    connection.last_billed_date = billing_month
    session.add(connection)
    return cycle, txn


def post_postpaid_collection(
    session: Session, user: User, *,
    cycle: PostpaidBillCycle,
    amount: Decimal, date: str,
    cash_account_code: str = "1000",
) -> Transaction:
    """Dr Cash / Cr 1130 Postpaid Cust Rec."""
    amt = money(D(amount))
    cash = _acc(session, user.tenant_id, cash_account_code)
    receivable = _acc(session, user.tenant_id, "1130")
    txn = post_transaction(
        session, user, date=date,
        description=f"Postpaid collection cycle {cycle.id} ({amt})",
        entries=[
            EntryInput(account_id=cash.id, debit=amt),
            EntryInput(account_id=receivable.id, credit=amt),
        ],
        audit_entity_type="postpaid_collection",
        audit_detail={"cycle_id": cycle.id, "amount": str(amt)},
    )
    cycle.collection_status = "collected" if amt >= D(cycle.gross_amount) else "partial"
    session.add(cycle)
    return txn


def post_postpaid_remittance(
    session: Session, user: User, *,
    cycle: PostpaidBillCycle, date: str,
    bank_account_code: str = "1010",
) -> Transaction:
    """Dr 2110 Postpaid Collections Payable / Cr Bank / Cr 4040 Postpaid Revenue."""
    net = money(D(cycle.net_remittance))
    commission = money(D(cycle.franchise_commission))
    gross = money(D(cycle.gross_amount))
    payable = _acc(session, user.tenant_id, "2110")
    bank = _acc(session, user.tenant_id, bank_account_code)
    revenue = _acc(session, user.tenant_id, "4040")
    txn = post_transaction(
        session, user, date=date,
        description=f"Postpaid remittance cycle {cycle.id} "
                    f"(gross {gross} → net {net} + commission {commission})",
        entries=[
            EntryInput(account_id=payable.id, debit=gross),
            EntryInput(account_id=bank.id, credit=net),
            EntryInput(account_id=revenue.id, credit=commission),
        ],
        audit_entity_type="postpaid_remittance",
        audit_detail={"cycle_id": cycle.id, "gross": str(gross), "net": str(net)},
    )
    cycle.remittance_status = "remitted"
    cycle.remittance_transaction_id = txn.id
    session.add(cycle)
    return txn


# ── Franchise fee + royalty ───────────────────────────────────────────────


def post_franchise_fee_capitalisation(
    session: Session, user: User, *,
    agreement: FranchiseAgreement,
    fee: Decimal, date: str,
    bank_account_code: str = "1010",
) -> Transaction:
    """Dr 1300 Franchise Intangible / Cr Bank."""
    f = money(D(fee))
    intangible = _acc(session, user.tenant_id, "1300")
    bank = _acc(session, user.tenant_id, bank_account_code)
    txn = post_transaction(
        session, user, date=date,
        description=f"Franchise fee capitalised — {agreement.agreement_number} ({f})",
        entries=[
            EntryInput(account_id=intangible.id, debit=f),
            EntryInput(account_id=bank.id, credit=f),
        ],
        audit_entity_type="franchise_fee",
        audit_detail={"agreement_id": agreement.id, "fee": str(f)},
    )
    agreement.franchise_fee_paid = money(D(agreement.franchise_fee_paid) + f)
    session.add(agreement)
    return txn


def post_franchise_fee_amortisation(
    session: Session, user: User, *,
    agreement: FranchiseAgreement,
    date: str,
) -> Transaction:
    """Monthly amortisation: total fee / term months. Dr 5030 / Cr 1301."""
    months = max(1, int(agreement.amortisation_months))
    monthly = money(D(agreement.franchise_fee_paid) / D(months))
    if monthly <= ZERO:
        raise HTTPException(status_code=400, detail="Nothing to amortise")
    expense = _acc(session, user.tenant_id, "5030")
    accum = _acc(session, user.tenant_id, "1301")
    return post_transaction(
        session, user, date=date,
        description=f"Franchise fee amortisation #{agreement.id} ({monthly})",
        entries=[
            EntryInput(account_id=expense.id, debit=monthly),
            EntryInput(account_id=accum.id, credit=monthly),
        ],
        audit_entity_type="franchise_amortisation",
        audit_detail={"agreement_id": agreement.id, "monthly": str(monthly)},
    )


def post_royalty_accrual(
    session: Session, user: User, *,
    agreement: FranchiseAgreement,
    gross_revenue: Decimal, date: str,
) -> Transaction:
    """Dr 5040 Royalty Expense / Cr 2120 Royalty Payable."""
    rate = D(agreement.royalty_rate_pct)
    royalty = money(D(gross_revenue) * rate / D("100"))
    if royalty <= ZERO:
        raise HTTPException(status_code=400, detail="Royalty must be > 0")
    expense = _acc(session, user.tenant_id, "5040")
    payable = _acc(session, user.tenant_id, "2120")
    return post_transaction(
        session, user, date=date,
        description=f"Royalty accrual — agreement {agreement.id} ({royalty})",
        entries=[
            EntryInput(account_id=expense.id, debit=royalty),
            EntryInput(account_id=payable.id, credit=royalty),
        ],
        audit_entity_type="royalty_accrual",
        audit_detail={"agreement_id": agreement.id, "royalty": str(royalty)},
    )


def post_royalty_payment(
    session: Session, user: User, *,
    amount: Decimal, date: str,
    bank_account_code: str = "1010",
) -> Transaction:
    """Dr 2120 Royalty Payable / Cr Bank."""
    amt = money(D(amount))
    payable = _acc(session, user.tenant_id, "2120")
    bank = _acc(session, user.tenant_id, bank_account_code)
    return post_transaction(
        session, user, date=date,
        description=f"Royalty payment ({amt})",
        entries=[
            EntryInput(account_id=payable.id, debit=amt),
            EntryInput(account_id=bank.id, credit=amt),
        ],
        audit_entity_type="royalty_payment",
        audit_detail={"amount": str(amt)},
    )
