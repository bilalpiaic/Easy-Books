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
