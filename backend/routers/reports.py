"""All read-only reports computed live from the GL: journal, ledger, trial
balance, P&L, balance sheet, cash flow, tax summary, dashboards.

These queries scan JournalEntry directly so figures are always real-time.
P4 will introduce materialised period balances for scale.
"""
import datetime as _dt
from datetime import date as DateType, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query
from sqlmodel import func, select

from models import (
    Account, Bill, Customer, Invoice, JournalEntry, Product, Transaction,
)
from services.money import D, ZERO, money

from .common import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/reports", tags=["reports"])


# ── Journal ──────────────────────────────────────────────────────────────────


@router.get("/journal")
def get_journal_report(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    skip: int = 0, limit: int = 100,
):
    q = (
        select(Transaction, JournalEntry, Account)
        .join(JournalEntry, JournalEntry.transaction_id == Transaction.id)
        .join(Account, JournalEntry.account_id == Account.id)
        .where(Transaction.tenant_id == user.tenant_id)
    )
    if start:
        q = q.where(Transaction.date >= start)
    if end:
        q = q.where(Transaction.date <= end)
    q = q.order_by(Transaction.date.desc(), Transaction.id.desc())
    rows = session.exec(q).all()
    return {
        "total": len(rows),
        "items": [
            {
                "id": tx.id,
                "transaction_id": tx.id,
                "jv_number": tx.jv_number,
                "date": tx.date,
                "description": tx.description,
                "account_name": acc.name,
                "debit": je.debit,
                "credit": je.credit,
                "is_reversed": tx.is_reversed,
            }
            for tx, je, acc in rows[skip : skip + limit]
        ],
    }


# ── Trial balance ────────────────────────────────────────────────────────────


@router.get("/trial-balance")
def get_trial_balance(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    date: Optional[str] = None,
):
    q = (
        session.query(
            Account.code,
            Account.name,
            Account.type,
            func.sum(JournalEntry.debit).label("total_debit"),
            func.sum(JournalEntry.credit).label("total_credit"),
        )
        .join(JournalEntry, JournalEntry.account_id == Account.id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .filter(Transaction.tenant_id == user.tenant_id)
    )
    if start:
        q = q.filter(Transaction.date >= start)
    if end:
        q = q.filter(Transaction.date <= end)
    elif date:
        q = q.filter(Transaction.date <= date)

    rows = (
        q.group_by(Account.id)
        .having((func.sum(JournalEntry.debit) > 0) | (func.sum(JournalEntry.credit) > 0))
        .order_by(Account.code)
        .all()
    )
    return [
        {
            "code": r.code,
            "name": r.name,
            "type": r.type,
            "total_debit": r.total_debit,
            "total_credit": r.total_credit,
        }
        for r in rows
    ]


# ── Dashboard ────────────────────────────────────────────────────────────────


@router.get("/dashboard")
def get_dashboard_data(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    tx_base = select(Transaction).where(Transaction.tenant_id == user.tenant_id)
    if start:
        tx_base = tx_base.where(Transaction.date >= start)
    if end:
        tx_base = tx_base.where(Transaction.date <= end)

    recent_txs = session.exec(
        tx_base.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(10)
    ).all()
    transaction_count = session.exec(
        select(func.count()).select_from(tx_base.subquery())
    ).one()

    je_q = (
        select(JournalEntry, Account)
        .join(Account, Account.id == JournalEntry.account_id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(Transaction.tenant_id == user.tenant_id)
    )
    if start:
        je_q = je_q.where(Transaction.date >= start)
    if end:
        je_q = je_q.where(Transaction.date <= end)

    total_revenue = ZERO
    total_expense = ZERO
    for entry, account in session.exec(je_q).all():
        if account.type == "Revenue":
            total_revenue += D(entry.credit) - D(entry.debit)
        elif account.type == "Expense":
            total_expense += D(entry.debit) - D(entry.credit)

    ar_outstanding = session.exec(
        select(func.sum(Invoice.total)).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.status.in_(["draft", "sent", "overdue"]),
        )
    ).one() or ZERO
    ap_outstanding = session.exec(
        select(func.sum(Bill.total)).where(
            Bill.tenant_id == user.tenant_id,
            Bill.status.in_(["draft", "received", "overdue"]),
        )
    ).one() or ZERO
    overdue_invoices = session.exec(
        select(func.count(Invoice.id)).where(
            Invoice.tenant_id == user.tenant_id, Invoice.status == "overdue"
        )
    ).one() or 0
    unpaid_bills = session.exec(
        select(func.count(Bill.id)).where(
            Bill.tenant_id == user.tenant_id,
            Bill.status.in_(["draft", "received", "overdue"]),
        )
    ).one() or 0
    low_stock = session.exec(
        select(func.count(Product.id)).where(
            Product.tenant_id == user.tenant_id,
            Product.product_type == "stock",
            Product.stock_qty <= Product.reorder_level,
        )
    ).one() or 0

    return {
        "summary": {
            "total_revenue": total_revenue,
            "total_expense": total_expense,
            "transaction_count": transaction_count,
            "ar_outstanding": ar_outstanding,
            "ap_outstanding": ap_outstanding,
            "overdue_invoices": overdue_invoices,
            "unpaid_bills": unpaid_bills,
            "low_stock_items": low_stock,
        },
        "recent": [
            {
                "id": tx.id,
                "jv_number": tx.jv_number,
                "date": tx.date,
                "description": tx.description or "",
            }
            for tx in recent_txs
        ],
    }


@router.get("/dashboard/charts")
def get_dashboard_charts(
    session: SessionDep, user: CurrentUserDep, months: int = 12,
):
    today = DateType.today()
    result_months = []
    for i in range(months - 1, -1, -1):
        d = DateType(today.year, today.month, 1)
        m = d.month - i
        y = d.year
        while m <= 0:
            m += 12
            y -= 1
        result_months.append((y, m))

    monthly = []
    for y, m in result_months:
        start = f"{y:04d}-{m:02d}-01"
        end = f"{y+1:04d}-01-01" if m == 12 else f"{y:04d}-{m+1:02d}-01"
        label = f"{y}-{m:02d}"
        rows = session.exec(
            select(JournalEntry, Account)
            .join(Account, Account.id == JournalEntry.account_id)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(
                Transaction.tenant_id == user.tenant_id,
                Transaction.date >= start,
                Transaction.date < end,
            )
        ).all()
        rev = sum((D(e.credit) - D(e.debit) for e, a in rows if a.type == "Revenue"), ZERO)
        exp = sum((D(e.debit) - D(e.credit) for e, a in rows if a.type == "Expense"), ZERO)
        monthly.append(
            {"month": label, "revenue": money(rev), "expenses": money(exp), "profit": money(rev - exp)}
        )

    exp_q = session.exec(
        select(Account.name, func.sum(JournalEntry.debit - JournalEntry.credit).label("total"))
        .join(JournalEntry, Account.id == JournalEntry.account_id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(
            Transaction.tenant_id == user.tenant_id,
            Account.type == "Expense",
            Transaction.date >= f"{today.year:04d}-01-01",
        )
        .group_by(Account.id)
        .order_by(func.sum(JournalEntry.debit - JournalEntry.credit).desc())
        .limit(8)
    ).all()
    expense_breakdown = [
        {"account": name, "amount": money(D(total or 0))}
        for name, total in exp_q
        if D(total or 0) > 0
    ]

    top_customers = session.exec(
        select(Customer.name, func.sum(Invoice.total).label("total"))
        .join(Invoice, Invoice.customer_id == Customer.id)
        .where(Customer.tenant_id == user.tenant_id)
        .group_by(Customer.id)
        .order_by(func.sum(Invoice.total).desc())
        .limit(5)
    ).all()
    top_cust = [{"name": n, "total": money(D(t or 0))} for n, t in top_customers]

    return {
        "monthly": monthly,
        "expense_breakdown": expense_breakdown,
        "top_customers": top_cust,
    }


# ── Income statement ─────────────────────────────────────────────────────────


@router.get("/income-statement")
def get_income_statement(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    q = (
        session.query(
            Account.name,
            Account.type,
            func.sum(JournalEntry.debit).label("total_debit"),
            func.sum(JournalEntry.credit).label("total_credit"),
        )
        .join(JournalEntry, JournalEntry.account_id == Account.id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .filter(Account.type.in_(["Revenue", "Expense"]))
        .filter(Transaction.tenant_id == user.tenant_id)
    )
    if start and end:
        q = q.filter(Transaction.date >= start, Transaction.date <= end)
    rows = q.group_by(Account.id).order_by(Account.type.desc(), Account.code).all()
    return [
        {
            "name": r.name,
            "type": r.type,
            "total_debit": r.total_debit,
            "total_credit": r.total_credit,
        }
        for r in rows
    ]


# ── General ledger (per-account with running balance) ────────────────────────


@router.get("/ledger")
def get_ledger(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    search: Optional[str] = None, skip: int = 0, limit: int = 50,
):
    q = (
        session.query(Account, Transaction, JournalEntry)
        .join(JournalEntry, JournalEntry.account_id == Account.id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .filter(Transaction.tenant_id == user.tenant_id)
    )
    if start:
        q = q.filter(Transaction.date >= start)
    if end:
        q = q.filter(Transaction.date <= end)
    if search:
        q = q.filter(Account.name.ilike(f"%{search}%"))

    rows = q.order_by(Account.code, Transaction.date, Transaction.id).all()
    accounts: dict = {}
    for account, tx, je in rows:
        if account.id not in accounts:
            accounts[account.id] = {
                "code": account.code, "name": account.name, "type": account.type,
                "entries": [], "running_balance": ZERO,
            }
        running = accounts[account.id]["running_balance"]
        if account.type in ("Asset", "Expense"):
            running += D(je.debit) - D(je.credit)
        else:
            running += D(je.credit) - D(je.debit)
        accounts[account.id]["running_balance"] = running
        accounts[account.id]["entries"].append({
            "date": tx.date,
            "jv_number": tx.jv_number,
            "description": tx.description or "",
            "debit": je.debit,
            "credit": je.credit,
            "balance": running,
        })

    all_accounts = list(accounts.values())
    return {"total": len(all_accounts), "items": all_accounts[skip : skip + limit]}


# ── Balance sheet ────────────────────────────────────────────────────────────


@router.get("/balance-sheet")
def get_balance_sheet(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    date: Optional[str] = None,
):
    q = (
        session.query(
            Account.code,
            Account.name,
            Account.type,
            func.sum(JournalEntry.debit).label("total_debit"),
            func.sum(JournalEntry.credit).label("total_credit"),
        )
        .join(JournalEntry, JournalEntry.account_id == Account.id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .filter(Transaction.tenant_id == user.tenant_id)
    )
    if start:
        q = q.filter(Transaction.date >= start)
    if end:
        q = q.filter(Transaction.date <= end)
    elif date:
        q = q.filter(Transaction.date <= date)

    rows = q.group_by(Account.id).order_by(Account.code).all()
    items = []
    net_income = ZERO
    for r in rows:
        debit = D(r.total_debit or 0)
        credit = D(r.total_credit or 0)
        if r.type == "Asset":
            balance = debit - credit
        elif r.type in ("Liability", "Equity"):
            balance = credit - debit
        elif r.type == "Revenue":
            net_income += credit - debit
            continue
        elif r.type == "Expense":
            net_income -= debit - credit
            continue
        else:
            balance = debit - credit
        items.append({"code": r.code, "name": r.name, "type": r.type, "balance": balance})

    if net_income != 0:
        items.append({
            "code": "RE-CUR",
            "name": "Retained Earnings (Current Period)",
            "type": "Equity",
            "balance": net_income,
        })
    return items


# ── Cash flow (indirect) ─────────────────────────────────────────────────────


@router.get("/cash-flow")
def cash_flow_statement(
    session: SessionDep, user: CurrentUserDep,
    start: str = Query(default=""), end: str = Query(default=""),
):
    if not start:
        start = f"{DateType.today().year}-01-01"
    if not end:
        end = str(DateType.today())

    accounts = session.exec(
        select(Account).where(Account.tenant_id == user.tenant_id)
    ).all()

    def acct_net(acct: Account) -> Decimal:
        entries = session.exec(
            select(JournalEntry)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(
                JournalEntry.account_id == acct.id,
                JournalEntry.tenant_id == user.tenant_id,
                Transaction.date >= start,
                Transaction.date <= end,
            )
        ).all()
        if acct.type in ("Asset", "Expense"):
            return sum((D(e.debit) - D(e.credit) for e in entries), ZERO)
        return sum((D(e.credit) - D(e.debit) for e in entries), ZERO)

    net_income = sum((acct_net(a) for a in accounts if a.type == "Revenue"), ZERO) - sum(
        (acct_net(a) for a in accounts if a.type == "Expense"), ZERO
    )
    ar_change = sum(
        (acct_net(a) for a in accounts if "receivable" in a.name.lower() or a.code == "1100"),
        ZERO,
    )
    ap_change = sum(
        (acct_net(a) for a in accounts if "payable" in a.name.lower() or a.code == "2000"),
        ZERO,
    )
    operating_cash = net_income - ar_change + ap_change

    def is_fixed_asset(a: Account) -> bool:
        n = a.name.lower()
        return a.type == "Asset" and not any(
            x in n for x in ["cash", "bank", "receivable", "advance", "gst", "inventory"]
        )

    investing_items = []
    investing_cash = ZERO
    for a in accounts:
        if is_fixed_asset(a):
            mv = acct_net(a)
            if mv != 0:
                investing_items.append({"name": a.name, "amount": -mv})
                investing_cash -= mv

    def is_financing(a: Account) -> bool:
        if a.type == "Equity":
            return True
        if a.type == "Liability":
            n = a.name.lower()
            return not any(x in n for x in ["payable", "gst", "advance"])
        return False

    financing_items = []
    financing_cash = ZERO
    for a in accounts:
        if is_financing(a):
            mv = acct_net(a)
            if mv != 0:
                financing_items.append({"name": a.name, "amount": mv})
                financing_cash += mv

    cash_accounts = [a for a in accounts if "cash" in a.name.lower() or "bank" in a.name.lower()]

    def balance_at(a: Account, as_of: str) -> Decimal:
        entries = session.exec(
            select(JournalEntry)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(
                JournalEntry.account_id == a.id,
                JournalEntry.tenant_id == user.tenant_id,
                Transaction.date <= as_of,
            )
        ).all()
        if a.type in ("Asset", "Expense"):
            return sum((D(e.debit) - D(e.credit) for e in entries), ZERO)
        return sum((D(e.credit) - D(e.debit) for e in entries), ZERO)

    try:
        start_dt = DateType.fromisoformat(start)
        day_before = str(start_dt - timedelta(days=1))
    except Exception:
        day_before = start

    beginning_balance = sum((balance_at(a, day_before) for a in cash_accounts), ZERO)
    ending_balance = sum((balance_at(a, end) for a in cash_accounts), ZERO)
    net_cash_change = operating_cash + investing_cash + financing_cash

    return {
        "period": {"start": start, "end": end},
        "net_income": net_income,
        "operating_adjustments": {"ar_change": ar_change, "ap_change": ap_change},
        "operating_cash": operating_cash,
        "investing_items": investing_items,
        "investing_cash": investing_cash,
        "financing_items": financing_items,
        "financing_cash": financing_cash,
        "net_cash_change": net_cash_change,
        "beginning_balance": beginning_balance,
        "ending_balance": ending_balance,
    }


# ── Tax summary ──────────────────────────────────────────────────────────────


@router.get("/tax-summary")
def tax_summary(
    session: SessionDep, user: CurrentUserDep,
    start: str = Query(default=""), end: str = Query(default=""),
):
    if not start:
        start = f"{DateType.today().year}-07-01"
    if not end:
        end = str(DateType.today())

    accounts = session.exec(
        select(Account).where(Account.tenant_id == user.tenant_id)
    ).all()

    def period_total(acct: Account, side: str) -> Decimal:
        entries = session.exec(
            select(JournalEntry)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(
                JournalEntry.account_id == acct.id,
                JournalEntry.tenant_id == user.tenant_id,
                Transaction.date >= start,
                Transaction.date <= end,
            )
        ).all()
        return sum((D(getattr(e, side)) for e in entries), ZERO)

    gst_payable_accts = [
        a for a in accounts if a.code == "2200" or "gst payable" in a.name.lower()
    ]
    output_gst = sum((period_total(a, "credit") for a in gst_payable_accts), ZERO)

    gst_input_accts = [
        a for a in accounts if a.code in ("1200", "1250") or "gst receivable" in a.name.lower()
    ]
    input_gst = sum((period_total(a, "debit") for a in gst_input_accts), ZERO)

    net_gst = output_gst - input_gst

    revenue = sum(
        (period_total(a, "credit") - period_total(a, "debit")
         for a in accounts if a.type == "Revenue"),
        ZERO,
    )
    expenses = sum(
        (period_total(a, "debit") - period_total(a, "credit")
         for a in accounts if a.type == "Expense"),
        ZERO,
    )
    taxable_income = revenue - expenses

    def income_tax_ito(income: Decimal) -> Decimal:
        if income <= 600000: return ZERO
        if income <= 1200000: return (income - 600000) * D("0.05")
        if income <= 2400000: return D("30000") + (income - 1200000) * D("0.15")
        if income <= 3600000: return D("210000") + (income - 2400000) * D("0.25")
        if income <= 6000000: return D("510000") + (income - 3600000) * D("0.30")
        return D("1230000") + (income - 6000000) * D("0.35")

    estimated_income_tax = income_tax_ito(max(ZERO, taxable_income))

    return {
        "period": {"start": start, "end": end},
        "gst": {
            "output_gst": output_gst,
            "input_gst": input_gst,
            "net_gst_payable": net_gst,
        },
        "income_tax": {
            "revenue": revenue,
            "expenses": expenses,
            "taxable_income": taxable_income,
            "estimated_tax": estimated_income_tax,
            "tax_basis": "ITO 2001 — Non-salaried individual slabs (FY 2024-25)",
        },
    }
