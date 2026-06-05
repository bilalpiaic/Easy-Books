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
    Account, Bill, Budget, Customer, Invoice, JournalEntry, PaymentAllocation,
    Product, Transaction,
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
        select(
            Account.code,
            Account.name,
            Account.type,
            func.sum(JournalEntry.debit).label("total_debit"),
            func.sum(JournalEntry.credit).label("total_credit"),
        )
        .join(JournalEntry, JournalEntry.account_id == Account.id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(Transaction.tenant_id == user.tenant_id)
    )
    if start:
        q = q.where(Transaction.date >= start)
    if end:
        q = q.where(Transaction.date <= end)
    elif date:
        q = q.where(Transaction.date <= date)

    rows = session.exec(
        q.group_by(Account.id)
        .having((func.sum(JournalEntry.debit) > 0) | (func.sum(JournalEntry.credit) > 0))
        .order_by(Account.code)
    ).all()
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

    # Outstanding = gross total MINUS sum(PaymentAllocation.amount) per doc,
    # then sum across docs that aren't fully paid. Includes 'partial' so a
    # partially-paid invoice still contributes its remaining balance.
    open_statuses_ar = ["draft", "sent", "overdue", "partial"]
    open_statuses_ap = ["draft", "received", "overdue", "partial"]

    ar_outstanding = session.exec(
        select(
            func.coalesce(
                func.sum(
                    Invoice.total
                    - func.coalesce(
                        select(func.sum(PaymentAllocation.amount))
                        .where(PaymentAllocation.invoice_id == Invoice.id)
                        .correlate(Invoice).scalar_subquery(),
                        0,
                    )
                ),
                0,
            )
        ).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.status.in_(open_statuses_ar),
        )
    ).one() or ZERO
    ap_outstanding = session.exec(
        select(
            func.coalesce(
                func.sum(
                    Bill.total
                    - func.coalesce(
                        select(func.sum(PaymentAllocation.amount))
                        .where(PaymentAllocation.bill_id == Bill.id)
                        .correlate(Bill).scalar_subquery(),
                        0,
                    )
                ),
                0,
            )
        ).where(
            Bill.tenant_id == user.tenant_id,
            Bill.status.in_(open_statuses_ap),
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
            Bill.status.in_(open_statuses_ap),
        )
    ).one() or 0
    low_stock = session.exec(
        select(func.count(Product.id)).where(
            Product.tenant_id == user.tenant_id,
            Product.product_type == "stock",
            Product.stock_qty <= Product.reorder_level,
        )
    ).one() or 0

    # Cash & Bank balance: sum of all 10xx GL accounts (debit normal)
    cash_balance = session.exec(
        select(
            func.coalesce(
                func.sum(JournalEntry.debit - JournalEntry.credit),
                0,
            )
        )
        .join(Account, Account.id == JournalEntry.account_id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(
            Transaction.tenant_id == user.tenant_id,
            Account.code.like("10%"),
        )
    ).one() or ZERO

    # AR aging buckets (all-time outstanding, same logic as /api/invoices/aging)
    from datetime import date as _today_date
    _today = _today_date.today()
    aging_rows = session.exec(
        select(
            Invoice.id, Invoice.due_date, Invoice.total,
            func.coalesce(
                select(func.sum(PaymentAllocation.amount))
                .where(PaymentAllocation.invoice_id == Invoice.id)
                .correlate(Invoice).scalar_subquery(),
                0,
            ).label("allocated"),
        ).where(Invoice.tenant_id == user.tenant_id)
    ).all()
    ar_aging = {"current": ZERO, "1_30": ZERO, "31_60": ZERO, "61_90": ZERO, "over_90": ZERO}
    for row in aging_rows:
        outstanding = D(row.total) - D(row.allocated)
        if outstanding <= 0:
            continue
        due = _today_date.fromisoformat(str(row.due_date))
        days_past = (_today - due).days
        if days_past <= 0:
            ar_aging["current"] += outstanding
        elif days_past <= 30:
            ar_aging["1_30"] += outstanding
        elif days_past <= 60:
            ar_aging["31_60"] += outstanding
        elif days_past <= 90:
            ar_aging["61_90"] += outstanding
        else:
            ar_aging["over_90"] += outstanding

    # AP due this week
    week_end = str(_today + timedelta(days=7))
    ap_due_week = session.exec(
        select(
            func.coalesce(
                func.sum(
                    Bill.total
                    - func.coalesce(
                        select(func.sum(PaymentAllocation.amount))
                        .where(PaymentAllocation.bill_id == Bill.id)
                        .correlate(Bill).scalar_subquery(),
                        0,
                    )
                ),
                0,
            )
        ).where(
            Bill.tenant_id == user.tenant_id,
            Bill.status.in_(open_statuses_ap),
            Bill.due_date <= week_end,
        )
    ).one() or ZERO

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
            "cash_balance": cash_balance,
            "ar_aging": ar_aging,
            "ap_due_week": ap_due_week,
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
    compare_start: Optional[str] = None, compare_end: Optional[str] = None,
):
    def _query(s, e):
        q = (
            session.query(
                Account.name,
                Account.type,
                Account.code,
                func.sum(JournalEntry.debit).label("total_debit"),
                func.sum(JournalEntry.credit).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.account_id == Account.id)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .filter(Account.type.in_(["Revenue", "Expense"]))
            .filter(Transaction.tenant_id == user.tenant_id)
        )
        if s and e:
            q = q.filter(Transaction.date >= s, Transaction.date <= e)
        rows = q.group_by(Account.id).order_by(Account.type.desc(), Account.code).all()
        return [
            {
                "name": r.name,
                "type": r.type,
                "code": r.code,
                "total_debit": r.total_debit,
                "total_credit": r.total_credit,
            }
            for r in rows
        ]

    current = _query(start, end)
    if compare_start and compare_end:
        return {"current": current, "comparison": _query(compare_start, compare_end)}
    return current  # backward-compatible flat list


# ── General ledger (per-account with running balance) ────────────────────────


@router.get("/ledger")
def get_ledger(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    search: Optional[str] = None,
    account_id: Optional[int] = None, account_code: Optional[str] = None,
    skip: int = 0, limit: int = 50,
):
    from collections import defaultdict
    acc_q = select(Account).where(Account.tenant_id == user.tenant_id)
    if account_id:
        acc_q = acc_q.where(Account.id == account_id)
    elif account_code:
        acc_q = acc_q.where(Account.code == account_code)
    elif search:
        acc_q = acc_q.where(Account.name.ilike(f"%{search}%"))
    scope = {a.id: a for a in session.exec(acc_q).all()}
    if not scope:
        return {"total": 0, "items": []}

    def signed(atype, debit, credit):
        d, c = D(debit), D(credit)
        return (d - c) if atype in ("Asset", "Expense") else (c - d)

    opening: dict = defaultdict(lambda: ZERO)
    if start:
        for acc_id, debit, credit in (
            session.query(JournalEntry.account_id, JournalEntry.debit, JournalEntry.credit)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .filter(Transaction.tenant_id == user.tenant_id,
                    Transaction.date < start,
                    JournalEntry.account_id.in_(list(scope.keys())))
            .all()
        ):
            opening[acc_id] += signed(scope[acc_id].type, debit, credit)

    q = (
        session.query(Transaction, JournalEntry)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .filter(Transaction.tenant_id == user.tenant_id,
                JournalEntry.account_id.in_(list(scope.keys())))
    )
    if start:
        q = q.filter(Transaction.date >= start)
    if end:
        q = q.filter(Transaction.date <= end)
    inrange = q.order_by(JournalEntry.account_id, Transaction.date, Transaction.id).all()

    accounts: dict = {}

    def ensure(acc_id):
        if acc_id not in accounts:
            a = scope[acc_id]
            accounts[acc_id] = {
                "id": a.id, "code": a.code, "name": a.name, "type": a.type,
                "opening_balance": opening[acc_id], "entries": [],
                "running_balance": opening[acc_id],
            }
        return accounts[acc_id]

    for acc_id, bal in opening.items():
        if bal != ZERO:
            ensure(acc_id)
    for tx, je in inrange:
        rec = ensure(je.account_id)
        rec["running_balance"] += signed(rec["type"], je.debit, je.credit)
        rec["entries"].append({
            "date": tx.date, "transaction_id": tx.id, "jv_number": tx.jv_number,
            "description": tx.description or "", "debit": je.debit,
            "credit": je.credit, "balance": rec["running_balance"],
        })

    items = []
    for rec in accounts.values():
        rec["closing_balance"] = rec["running_balance"]
        items.append(rec)
    items.sort(key=lambda r: r["code"])
    return {"total": len(items), "items": items[skip: skip + limit]}


# ── Balance sheet ────────────────────────────────────────────────────────────


@router.get("/balance-sheet")
def get_balance_sheet(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    date: Optional[str] = None,
    compare_end: Optional[str] = None,
):
    def _query(s, e, as_of):
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
        if s:
            q = q.filter(Transaction.date >= s)
        if e:
            q = q.filter(Transaction.date <= e)
        elif as_of:
            q = q.filter(Transaction.date <= as_of)
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

    current = _query(start, end, date)
    if compare_end:
        return {"current": current, "comparison": _query(None, compare_end, None)}
    return current  # backward-compatible flat list


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


# ── Analytic P&L ─────────────────────────────────────────────────────────────


@router.get("/analytic-pl")
def get_analytic_pl(
    session: SessionDep, user: CurrentUserDep,
    analytic_account_id: int,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """P&L filtered to a single analytic dimension (cost center / project)."""
    q = (
        session.query(
            Account.name,
            Account.type,
            Account.code,
            func.sum(JournalEntry.debit).label("dr"),
            func.sum(JournalEntry.credit).label("cr"),
        )
        .join(JournalEntry, JournalEntry.account_id == Account.id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .filter(
            Transaction.tenant_id == user.tenant_id,
            JournalEntry.analytic_account_id == analytic_account_id,
            Account.type.in_(["Revenue", "Expense"]),
        )
    )
    if start and end:
        q = q.filter(Transaction.date >= start, Transaction.date <= end)
    rows = q.group_by(Account.id).order_by(Account.type.desc(), Account.code).all()
    return [
        {"name": r.name, "code": r.code, "type": r.type,
         "total_debit": r.dr, "total_credit": r.cr}
        for r in rows
    ]


# ── Budget vs Actual ──────────────────────────────────────────────────────────


@router.get("/budget-vs-actual")
def get_budget_vs_actual(
    session: SessionDep, user: CurrentUserDep,
    year: int,
    month: Optional[int] = None,
):
    """Return budget, actual, and variance per account for a fiscal year / month."""
    import calendar as _cal

    budgets = session.exec(
        select(Budget).where(
            Budget.tenant_id == user.tenant_id,
            Budget.fiscal_year == year,
            *([Budget.period_month == month] if month else []),
        )
    ).all()

    result = []
    for b in budgets:
        if month:
            period_start = f"{year}-{month:02d}-01"
            last_day = _cal.monthrange(year, month)[1]
            period_end = f"{year}-{month:02d}-{last_day:02d}"
        else:
            period_start = f"{year}-01-01"
            period_end = f"{year}-12-31"

        act_row = session.exec(
            select(
                func.coalesce(func.sum(JournalEntry.debit), 0).label("dr"),
                func.coalesce(func.sum(JournalEntry.credit), 0).label("cr"),
            )
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(
                JournalEntry.account_id == b.account_id,
                Transaction.tenant_id == user.tenant_id,
                Transaction.date >= period_start,
                Transaction.date <= period_end,
            )
        ).one()

        acc = session.get(Account, b.account_id)
        if not acc:
            continue

        # Expenses are debit-normal; Revenue/Liability/Equity are credit-normal
        if acc.type == "Expense":
            actual = D(act_row.dr) - D(act_row.cr)
        else:
            actual = D(act_row.cr) - D(act_row.dr)

        budget_amt = D(str(b.amount))
        variance = budget_amt - actual  # positive = under budget (favourable)

        result.append({
            "account_id": b.account_id,
            "account_code": acc.code,
            "account_name": acc.name,
            "account_type": acc.type,
            "month": b.period_month,
            "fiscal_year": b.fiscal_year,
            "budget": budget_amt,
            "actual": actual,
            "variance": variance,
            "variance_pct": float(variance / budget_amt * 100) if budget_amt != ZERO else 0,
        })
    return result


# ── FX Revaluation ────────────────────────────────────────────────────────────


@router.post("/fx-revaluation")
def run_fx_revaluation(
    session: SessionDep, user: CurrentUserDep,
    revaluation_date: str,
):
    """Revalue open foreign-currency AR to closing rate. IAS 21.23."""
    from models import PaymentAllocation, Tenant
    from routers.common import get_or_create_account
    from services.fx import rate_to_base
    from services.posting import EntryInput, post_transaction

    tenant = session.get(Tenant, user.tenant_id)
    base_currency = tenant.base_currency if tenant else "PKR"

    # Include draft, sent, and partial — all have GL impact.
    # Exclude paid (settled) and void/cancelled.
    open_invoices = session.exec(
        select(Invoice).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.status.in_(["draft", "posted", "partial", "sent"]),
            Invoice.transaction_id.is_not(None),
            Invoice.currency != base_currency,
        )
    ).all()

    fx_gain_acc = get_or_create_account(
        session, user.tenant_id, "4901", "Unrealised FX Gain/Loss", "Revenue"
    )

    all_entries: list[EntryInput] = []
    for inv in open_invoices:
        alloc_total = session.exec(
            select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
            .where(PaymentAllocation.invoice_id == inv.id)
        ).one()
        outstanding_doc = D(str(inv.total)) - D(str(alloc_total))
        if outstanding_doc <= ZERO:
            continue

        try:
            closing_rate = rate_to_base(session, user.tenant_id, inv.currency, revaluation_date)
        except LookupError:
            continue  # no rate available for this currency on this date

        original_base = money(outstanding_doc * D(str(inv.exchange_rate)))
        closing_base = money(outstanding_doc * closing_rate)
        diff = closing_base - original_base
        if abs(diff) < D("0.01"):
            continue

        if inv.ar_account_id:
            ar_acc = session.get(Account, inv.ar_account_id)
        else:
            # Fall back to the default AR account (code 1100) for this tenant
            ar_acc = session.exec(
                select(Account).where(
                    Account.tenant_id == user.tenant_id,
                    Account.code == "1100",
                )
            ).first()
        if not ar_acc:
            continue

        if diff > ZERO:  # FX gain: Dr AR, Cr FX Gain
            all_entries += [
                EntryInput(account_id=ar_acc.id, debit=diff),
                EntryInput(account_id=fx_gain_acc.id, credit=diff),
            ]
        else:  # FX loss: Dr FX Loss, Cr AR
            all_entries += [
                EntryInput(account_id=fx_gain_acc.id, debit=-diff),
                EntryInput(account_id=ar_acc.id, credit=-diff),
            ]

    if not all_entries:
        return {"message": "No foreign-currency AR positions to revalue", "entries_count": 0}

    txn = post_transaction(
        session,
        user,
        date=revaluation_date,
        description=f"FX Revaluation as at {revaluation_date}",
        entries=all_entries,
        audit_entity_type="fx_revaluation",
        audit_detail={"revaluation_date": revaluation_date},
    )
    session.commit()
    return {"jv_number": txn.jv_number, "entries_count": len(all_entries)}


# ── Product Ledger (by store or consolidated) ────────────────────────────────

_IN_DIRECTIONS = {"RECEIPT", "CUSTODIAL_RECEIPT", "COMPLETION", "CUSTODIAL_COMPLETION"}


@router.get("/product-ledger")
def product_ledger(
    session: SessionDep, user: CurrentUserDep,
    product_id: int, location_id: Optional[int] = None,
    start: Optional[str] = None, end: Optional[str] = None,
):
    from models import StockLocation, StockMovement
    q = select(StockMovement).where(
        StockMovement.tenant_id == user.tenant_id,
        StockMovement.product_id == product_id,
    )
    if location_id is not None:
        q = q.where(
            (StockMovement.from_location_id == location_id)
            | (StockMovement.to_location_id == location_id)
        )
    rows = session.exec(q.order_by(StockMovement.occurred_at, StockMovement.id)).all()
    # Resolve location ids → names once (no N+1).
    loc_names = {
        loc.id: loc.name
        for loc in session.exec(
            select(StockLocation).where(StockLocation.tenant_id == user.tenant_id)
        ).all()
    }
    running = ZERO
    items = []
    for m in rows:
        d = m.occurred_at.date().isoformat() if hasattr(m.occurred_at, "date") else str(m.occurred_at)[:10]
        if start and d < start:
            continue
        if end and d > end:
            continue
        sign = 1 if m.direction in _IN_DIRECTIONS else -1
        running += sign * D(m.qty)
        # IN movements land at to_location; OUT movements leave from_location.
        loc_id = m.to_location_id if sign > 0 else m.from_location_id
        items.append({
            "date": d, "direction": m.direction,
            "qty_in": D(m.qty) if sign > 0 else ZERO,
            "qty_out": D(m.qty) if sign < 0 else ZERO,
            "running_qty": running, "unit_cost": m.unit_cost,
            "source": m.source_doc_type or "",
            "location": loc_names.get(loc_id, "") if loc_id else "",
        })
    return {"product_id": product_id, "location_id": location_id, "items": items}


# ── Inventory Performance ─────────────────────────────────────────────────────


@router.get("/inventory-performance")
def inventory_performance(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    from models import StockMovement
    prods = session.exec(
        select(Product).where(Product.tenant_id == user.tenant_id,
                              Product.product_type == "stock")
    ).all()
    out = []
    for p in prods:
        mv = session.exec(
            select(StockMovement).where(
                StockMovement.tenant_id == user.tenant_id,
                StockMovement.product_id == p.id,
            ).order_by(StockMovement.occurred_at.desc())
        ).all()
        last = mv[0].occurred_at.date().isoformat() if mv else None
        units_sold = sum(
            (D(m.qty) for m in mv
             if m.direction in ("SHIPMENT", "DELIVERY", "ISSUE")
             and (not start or m.occurred_at.date().isoformat() >= start)
             and (not end or m.occurred_at.date().isoformat() <= end)),
            start=ZERO,
        )
        out.append({
            "id": p.id, "name": p.name, "code": p.code,
            "on_hand": D(p.stock_qty), "avg_cost": D(p.avg_cost),
            "stock_value": money(D(p.stock_qty) * D(p.avg_cost)),
            "reorder_level": D(p.reorder_level),
            "low_stock": D(p.stock_qty) <= D(p.reorder_level),
            "last_movement": last, "units_sold": units_sold,
            "cogs": money(units_sold * D(p.avg_cost)),
        })
    out.sort(key=lambda r: r["stock_value"], reverse=True)
    return {"items": out}


# ── Product COA (category valuation tree) ─────────────────────────────────────


@router.get("/product-coa")
def product_coa(session: SessionDep, user: CurrentUserDep):
    """Products as a Main → Sub → Item valuation tree: closing qty, avg rate and
    value, grouped by ProductCategory parent → sub-category → product."""
    from models import ProductCategory

    cats = session.exec(
        select(ProductCategory).where(ProductCategory.tenant_id == user.tenant_id)
    ).all()
    cat_by_id = {c.id: c for c in cats}

    def main_sub(cat_id):
        """Resolve a product's category_id to its (Main, Sub) group names."""
        cat = cat_by_id.get(cat_id)
        if cat is None:
            return "Uncategorized", "—"
        if cat.parent_id is None:
            return cat.name, "—"          # product sits directly on a parent category
        parent = cat_by_id.get(cat.parent_id)
        return (parent.name if parent else "Uncategorized"), cat.name

    prods = session.exec(
        select(Product).where(Product.tenant_id == user.tenant_id)
    ).all()

    tree: dict = {}
    for p in prods:
        main, sub = main_sub(p.category_id)
        qty, avg = D(p.stock_qty), D(p.avg_cost)
        tree.setdefault(main, {}).setdefault(sub, []).append({
            "id": p.id, "code": p.code, "name": p.name,
            "qty": qty, "avg_rate": avg, "value": money(qty * avg),
        })

    groups, grand_qty, grand_value = [], ZERO, ZERO
    for main_name in sorted(tree):
        subs, main_qty, main_value = [], ZERO, ZERO
        for sub_name in sorted(tree[main_name]):
            items = tree[main_name][sub_name]
            sub_qty = sum((i["qty"] for i in items), start=ZERO)
            sub_value = sum((i["value"] for i in items), start=ZERO)
            subs.append({"name": sub_name, "qty": sub_qty,
                         "value": sub_value, "items": items})
            main_qty += sub_qty
            main_value += sub_value
        groups.append({"name": main_name, "qty": main_qty,
                       "value": main_value, "subs": subs})
        grand_qty += main_qty
        grand_value += main_value

    return {"groups": groups, "grand": {"qty": grand_qty, "value": grand_value}}


# ── Customer Performance ──────────────────────────────────────────────────────


@router.get("/customer-performance")
def customer_performance(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    customer_id: Optional[int] = None,
):
    from models import Invoice, PaymentAllocation, PaymentReceived
    from datetime import date as _date
    q = select(Invoice).where(Invoice.tenant_id == user.tenant_id)
    if start:
        q = q.where(Invoice.issue_date >= start)
    if end:
        q = q.where(Invoice.issue_date <= end)
    invoices = session.exec(q).all()
    agg: dict = {}
    for inv in invoices:
        a = agg.setdefault(inv.customer_name or "—", {
            "name": inv.customer_name or "—", "revenue": ZERO,
            "invoice_count": 0, "outstanding": ZERO, "_days": [],
        })
        a["revenue"] += D(inv.total)
        a["invoice_count"] += 1
        allocated = session.exec(
            select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
            .where(PaymentAllocation.invoice_id == inv.id)
        ).first()
        allocated = D(allocated if not isinstance(allocated, (tuple, list)) else allocated[0])
        a["outstanding"] += max(D(inv.total) - allocated, ZERO)
        if allocated >= D(inv.total) and D(inv.total) > 0:
            last_pay = session.exec(
                select(PaymentReceived.payment_date)
                .join(PaymentAllocation, PaymentAllocation.payment_received_id == PaymentReceived.id)
                .where(PaymentAllocation.invoice_id == inv.id)
                .order_by(PaymentReceived.payment_date.desc())
            ).first()
            if last_pay:
                a["_days"].append((_date.fromisoformat(last_pay) - _date.fromisoformat(inv.issue_date)).days)
    out = []
    for a in agg.values():
        days = a.pop("_days")
        a["avg_days_to_pay"] = round(sum(days) / len(days), 1) if days else None
        out.append(a)
    out.sort(key=lambda r: r["revenue"], reverse=True)

    detail = None
    if customer_id is not None:
        from models import InvoiceLine, Product, ProductCategory
        dq = select(Invoice).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.customer_id == customer_id,
        )
        if start:
            dq = dq.where(Invoice.issue_date >= start)
        if end:
            dq = dq.where(Invoice.issue_date <= end)
        cust_invoices = session.exec(dq).all()
        inv_ids = [i.id for i in cust_invoices]
        # avg_cost lookup
        avg_cost = {p.id: D(p.avg_cost) for p in session.exec(
            select(Product).where(Product.tenant_id == user.tenant_id)
        ).all()}
        monthly: dict = {}
        products: dict = {}
        lines = []
        if inv_ids:
            lines = session.exec(
                select(InvoiceLine).where(InvoiceLine.invoice_id.in_(inv_ids))
            ).all()
        tot_rev = tot_cogs = ZERO
        inv_date = {i.id: i.issue_date for i in cust_invoices}
        for ln in lines:
            line_rev = D(ln.amount)
            line_cogs = D(ln.qty) * avg_cost.get(ln.product_id, ZERO)
            tot_rev += line_rev
            tot_cogs += line_cogs
            mk = inv_date[ln.invoice_id][:7]
            m = monthly.setdefault(mk, {"month": mk, "revenue": ZERO, "units": ZERO})
            m["revenue"] += line_rev
            m["units"] += D(ln.qty)
            pr = products.setdefault(ln.product_id, {
                "product_id": ln.product_id, "qty": ZERO,
                "revenue": ZERO, "cogs": ZERO,
            })
            pr["qty"] += D(ln.qty)
            pr["revenue"] += line_rev
            pr["cogs"] += line_cogs
        # attach product names + category labels
        cats = {c.id: c for c in session.exec(
            select(ProductCategory).where(ProductCategory.tenant_id == user.tenant_id)
        ).all()}

        def cat_label(cid):
            c = cats.get(cid)
            if not c:
                return "Uncategorized"
            if c.parent_id is None:
                return c.name
            par = cats.get(c.parent_id)
            return f"{par.name} › {c.name}" if par else c.name

        prod_rows = []
        for pid, pr in products.items():
            p = session.get(Product, pid) if pid else None
            pr["gp"] = money(pr["revenue"] - pr["cogs"])
            pr["revenue"] = money(pr["revenue"])
            pr["cogs"] = money(pr["cogs"])
            pr["qty"] = float(pr["qty"])
            pr["name"] = p.name if p else "—"
            pr["category"] = cat_label(p.category_id) if p else "Uncategorized"
            prod_rows.append(pr)
        prod_rows.sort(key=lambda r: r["revenue"], reverse=True)
        # serialise monthly
        monthly_list = []
        for k in sorted(monthly):
            entry = monthly[k]
            monthly_list.append({
                "month": entry["month"],
                "revenue": money(entry["revenue"]),
                "units": float(entry["units"]),
            })
        transaction_count = len(cust_invoices)
        avg_invoice_value = money(tot_rev / transaction_count) if transaction_count else 0.0
        detail = {
            "monthly": monthly_list,
            "products": prod_rows,
            "totals": {
                "revenue": money(tot_rev),
                "cogs": money(tot_cogs),
                "gp": money(tot_rev - tot_cogs),
                "gp_pct": float(round((tot_rev - tot_cogs) / tot_rev * 100, 1)) if tot_rev else 0.0,
                "transaction_count": transaction_count,
                "avg_invoice_value": avg_invoice_value,
            },
        }
    return {"items": out, "detail": detail}


@router.get("/product-performance")
def product_performance(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    """Per-product period movement: opening/purchased/sold(net)/closing with
    values at avg_cost, plus GP (sales revenue - COGS) for the window."""
    from models import StockMovement, InvoiceLine

    # Stock-effect of each movement direction. ADD increases on-hand; OUT
    # decreases it via a sale/issue; RETURN (ADJUSTMENT, produced only by
    # return_to_vendor) decreases it as a purchase return and so nets against
    # purchases. Classifying every direction with the correct sign keeps the
    # identity opening + purchased - sold == closing reconciled with
    # Product.stock_qty even when vendor returns exist.
    ADD_DIRS = ("RECEIPT", "COMPLETION")
    OUT_DIRS = ("SHIPMENT", "DELIVERY", "ISSUE")
    RETURN_DIRS = ("ADJUSTMENT",)

    def signed_effect(direction, qty):
        if direction in ADD_DIRS:
            return qty
        if direction in OUT_DIRS or direction in RETURN_DIRS:
            return -qty
        return ZERO

    prods = session.exec(
        select(Product).where(Product.tenant_id == user.tenant_id,
                              Product.product_type == "stock")
    ).all()
    out = []
    for p in prods:
        mv = session.exec(
            select(StockMovement).where(
                StockMovement.tenant_id == user.tenant_id,
                StockMovement.product_id == p.id,
            )
        ).all()
        opening = purchased = sold = ZERO
        for m in mv:
            d = m.occurred_at.date().isoformat()
            qty = D(m.qty)
            if start and d < start:
                opening += signed_effect(m.direction, qty)
            elif (not start or d >= start) and (not end or d <= end):
                if m.direction in ADD_DIRS:
                    purchased += qty
                elif m.direction in RETURN_DIRS:
                    purchased -= qty          # purchase return → net purchases
                elif m.direction in OUT_DIRS:
                    sold += qty
        avg = D(p.avg_cost)
        closing = opening + purchased - sold
        # sales revenue for the product in window
        rq = (select(func.coalesce(func.sum(InvoiceLine.amount), 0))
              .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
              .where(Invoice.tenant_id == user.tenant_id,
                     InvoiceLine.product_id == p.id))
        if start:
            rq = rq.where(Invoice.issue_date >= start)
        if end:
            rq = rq.where(Invoice.issue_date <= end)
        revenue = D(session.exec(rq).first() or 0)
        cogs = sold * avg
        out.append({
            "product_id": p.id, "name": p.name, "code": p.code,
            "opening_qty": float(opening), "opening_value": money(opening * avg),
            "purchased_qty": float(purchased),
            "sold_qty": float(sold),
            "closing_qty": float(closing), "closing_value": money(closing * avg),
            "gp": money(revenue - cogs), "revenue": money(revenue),
        })
    out.sort(key=lambda r: r["closing_value"], reverse=True)
    return {"items": out}
