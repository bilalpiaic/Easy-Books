"""All read-only reports computed live from the GL: journal, ledger, trial
balance, P&L, balance sheet, cash flow, tax summary, dashboards.

These queries scan JournalEntry directly so figures are always real-time.
P4 will introduce materialised period balances for scale.
"""
import datetime as _dt
from datetime import date as DateType, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import func, select

from pydantic import BaseModel

from models import (
    Account, Bill, BillLine, BillPayment, Budget, CitAdjustment, Customer,
    Invoice, InvoiceLine, JournalEntry, PaymentAllocation, PaymentReceived,
    Product, ProductCategory, TaxCode, Transaction, Vendor,
)
from services.account_tree import build_account_tree
from services.export_utils import stream_csv, stream_xlsx
from services.money import D, ZERO, money

from services.permissions import perm_dep, apply_own_filter
from .common import CurrentUserDep, SessionDep, WriteUserDep

router = APIRouter(prefix="/api/reports", tags=["reports"])


# ── Journal ──────────────────────────────────────────────────────────────────


@router.get("/journal", dependencies=[perm_dep("report.general_ledger")])
def get_journal_report(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    voucher_type: Optional[str] = None,
    voucher_number: Optional[str] = None,
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
    if voucher_type:
        q = q.where(Transaction.voucher_type == voucher_type)
    if voucher_number:
        q = q.where(Transaction.jv_number.ilike(f"%{voucher_number}%"))
    q = q.order_by(Transaction.date.desc(), Transaction.id.desc())
    rows = session.exec(q).all()
    return {
        "total": len(rows),
        "items": [
            {
                "id": tx.id,
                "transaction_id": tx.id,
                "jv_number": tx.jv_number,
                "voucher_type": tx.voucher_type,
                "legacy_jv_number": tx.legacy_jv_number,
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


@router.get("/trial-balance", dependencies=[perm_dep("report.trial_balance")])
def get_trial_balance(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    date: Optional[str] = None,
):
    q = (
        select(
            Account.id,
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
    rows = session.exec(q.group_by(Account.id)).all()

    values = {
        r.id: {"debit": D(r.total_debit or 0), "credit": D(r.total_credit or 0)}
        for r in rows
    }
    accounts = session.exec(
        select(Account).where(Account.tenant_id == user.tenant_id)
    ).all()
    tree = build_account_tree(accounts, values, ["debit", "credit"])
    total_debit = sum((v["debit"] for v in values.values()), ZERO)
    total_credit = sum((v["credit"] for v in values.values()), ZERO)
    return {"tree": tree, "totals": {"debit": total_debit, "credit": total_credit}}


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
        .limit(10)
    ).all()
    top_cust = [{"name": n, "total": money(D(t or 0))} for n, t in top_customers]

    return {
        "monthly": monthly,
        "expense_breakdown": expense_breakdown,
        "top_customers": top_cust,
    }


@router.get("/dashboard/net-worth")
def get_net_worth_trend(
    session: SessionDep, user: CurrentUserDep, months: int = 36,
):
    """Monthly Assets / Liabilities / Net Worth series for the dashboard trend
    widget (#130). One grouped query fetches per-month deltas by account type;
    cumulative sums in Python turn them into month-end balances, carrying
    values forward through months with no activity."""
    months = max(1, min(months, 60))
    month_expr = func.substr(Transaction.date, 1, 7)
    rows = session.exec(
        select(
            month_expr.label("month"),
            Account.type,
            func.sum(JournalEntry.debit),
            func.sum(JournalEntry.credit),
        )
        .join(Account, Account.id == JournalEntry.account_id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(
            Transaction.tenant_id == user.tenant_id,
            Account.type.in_(["Asset", "Liability"]),
        )
        .group_by(month_expr, Account.type)
        .order_by(month_expr)
    ).all()

    today = DateType.today()
    if not rows:
        return {"series": [], "as_of": today.isoformat()}

    deltas: dict[str, dict[str, Decimal]] = {}
    for month, acc_type, debit, credit in rows:
        d = deltas.setdefault(month, {})
        # Asset balances grow with debits; Liability balances grow with credits
        signed = D(debit or 0) - D(credit or 0) if acc_type == "Asset" else D(credit or 0) - D(debit or 0)
        d[acc_type] = d.get(acc_type, ZERO) + signed

    first_y, first_m = (int(p) for p in min(deltas).split("-"))
    assets = liabilities = ZERO
    series = []
    y, m = first_y, first_m
    while (y, m) <= (today.year, today.month):
        key = f"{y:04d}-{m:02d}"
        d = deltas.get(key)
        if d:
            assets += d.get("Asset", ZERO)
            liabilities += d.get("Liability", ZERO)
        series.append({
            "month": key,
            "assets": money(assets),
            "liabilities": money(liabilities),
            "net_worth": money(assets - liabilities),
        })
        m += 1
        if m > 12:
            m, y = 1, y + 1

    return {"series": series[-months:], "as_of": today.isoformat()}


@router.get("/dashboard/trends")
def get_dashboard_trends(
    session: SessionDep, user: CurrentUserDep, months: int = 12,
):
    """One-call payload for the dashboard trend widgets: monthly cash flow,
    cumulative cash balance, sales vs purchases, collections, top-5 expense
    trend, YTD revenue breakdown, top vendors, invoice pipeline by status and
    AP aging buckets. Every series is aligned to the same `months` spine so
    widgets can index arrays directly."""
    months = max(1, min(months, 36))
    today = DateType.today()

    spine: list[str] = []
    y, m = today.year, today.month - (months - 1)
    while m <= 0:
        m += 12
        y -= 1
    for _ in range(months):
        spine.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    window_start = f"{spine[0]}-01"
    spine_idx = {mo: i for i, mo in enumerate(spine)}

    month_expr = func.substr(Transaction.date, 1, 7)

    # Cash flow (all 10xx Cash & Bank accounts) — full history so the
    # cumulative balance line starts from the true opening position.
    cash_rows = session.exec(
        select(
            month_expr.label("month"),
            func.sum(JournalEntry.debit),
            func.sum(JournalEntry.credit),
        )
        .join(Account, Account.id == JournalEntry.account_id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(
            Transaction.tenant_id == user.tenant_id,
            Account.code.like("10%"),
        )
        .group_by(month_expr)
        .order_by(month_expr)
    ).all()
    inflow = [ZERO] * months
    outflow = [ZERO] * months
    opening_cash = ZERO
    for month, debit, credit in cash_rows:
        d, c = D(debit or 0), D(credit or 0)
        if month < spine[0]:
            opening_cash += d - c
        elif month in spine_idx:
            i = spine_idx[month]
            inflow[i] += d
            outflow[i] += c
    cash_balance = []
    running = opening_cash
    for i in range(months):
        running += inflow[i] - outflow[i]
        cash_balance.append(money(running))

    # Sales (invoices issued) vs Purchases (bills received), void excluded
    def _doc_monthly(model, date_col):
        rows = session.exec(
            select(
                func.substr(date_col, 1, 7).label("month"),
                func.sum(model.total),
            )
            .where(
                model.tenant_id == user.tenant_id,
                model.status != "void",
                date_col >= window_start,
            )
            .group_by(func.substr(date_col, 1, 7))
        ).all()
        out = [ZERO] * months
        for month, total in rows:
            if month in spine_idx:
                out[spine_idx[month]] = D(total or 0)
        return out

    sales = _doc_monthly(Invoice, Invoice.issue_date)
    purchases = _doc_monthly(Bill, Bill.bill_date)

    # Collections: customer payments actually received per month
    coll_rows = session.exec(
        select(
            func.substr(PaymentReceived.payment_date, 1, 7).label("month"),
            func.sum(PaymentReceived.amount),
        )
        .where(
            PaymentReceived.tenant_id == user.tenant_id,
            PaymentReceived.payment_date >= window_start,
        )
        .group_by(func.substr(PaymentReceived.payment_date, 1, 7))
    ).all()
    collected = [ZERO] * months
    for month, total in coll_rows:
        if month in spine_idx:
            collected[spine_idx[month]] = D(total or 0)

    # Top-5 expense accounts in the window, then their monthly series
    top_exp = session.exec(
        select(Account.id, Account.name)
        .join(JournalEntry, JournalEntry.account_id == Account.id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(
            Transaction.tenant_id == user.tenant_id,
            Account.type == "Expense",
            Transaction.date >= window_start,
        )
        .group_by(Account.id)
        .order_by(func.sum(JournalEntry.debit - JournalEntry.credit).desc())
        .limit(5)
    ).all()
    exp_accounts = [name for _id, name in top_exp]
    exp_series = [[ZERO] * months for _ in top_exp]
    if top_exp:
        exp_pos = {acc_id: i for i, (acc_id, _name) in enumerate(top_exp)}
        exp_rows = session.exec(
            select(
                month_expr.label("month"),
                JournalEntry.account_id,
                func.sum(JournalEntry.debit - JournalEntry.credit),
            )
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(
                Transaction.tenant_id == user.tenant_id,
                JournalEntry.account_id.in_(list(exp_pos)),
                Transaction.date >= window_start,
            )
            .group_by(month_expr, JournalEntry.account_id)
        ).all()
        for month, acc_id, total in exp_rows:
            if month in spine_idx:
                exp_series[exp_pos[acc_id]][spine_idx[month]] = D(total or 0)

    # YTD revenue breakdown by account (mirror of the expense doughnut)
    rev_rows = session.exec(
        select(Account.name, func.sum(JournalEntry.credit - JournalEntry.debit).label("total"))
        .join(JournalEntry, Account.id == JournalEntry.account_id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(
            Transaction.tenant_id == user.tenant_id,
            Account.type == "Revenue",
            Transaction.date >= f"{today.year:04d}-01-01",
        )
        .group_by(Account.id)
        .order_by(func.sum(JournalEntry.credit - JournalEntry.debit).desc())
        .limit(8)
    ).all()
    revenue_breakdown = [
        {"account": name, "amount": money(D(total or 0))}
        for name, total in rev_rows
        if D(total or 0) > 0
    ]

    # Top vendors by billed spend (all-time, mirror of top customers)
    vend_rows = session.exec(
        select(Vendor.name, func.sum(Bill.total).label("total"))
        .join(Bill, Bill.vendor_id == Vendor.id)
        .where(Vendor.tenant_id == user.tenant_id, Bill.status != "void")
        .group_by(Vendor.id)
        .order_by(func.sum(Bill.total).desc())
        .limit(10)
    ).all()
    top_vendors = [{"name": n, "total": money(D(t or 0))} for n, t in vend_rows]

    # Invoice pipeline: count + amount by status
    status_rows = session.exec(
        select(Invoice.status, func.count(Invoice.id), func.sum(Invoice.total))
        .where(Invoice.tenant_id == user.tenant_id)
        .group_by(Invoice.status)
    ).all()
    invoice_status = [
        {"status": st, "count": cnt, "amount": money(D(total or 0))}
        for st, cnt, total in status_rows
    ]

    # AP aging buckets (mirror of the dashboard's AR aging)
    open_statuses_ap = ["draft", "received", "overdue", "partial"]
    ap_rows = session.exec(
        select(
            Bill.id, Bill.due_date, Bill.total,
            func.coalesce(
                select(func.sum(PaymentAllocation.amount))
                .where(PaymentAllocation.bill_id == Bill.id)
                .correlate(Bill).scalar_subquery(),
                0,
            ).label("allocated"),
        ).where(
            Bill.tenant_id == user.tenant_id,
            Bill.status.in_(open_statuses_ap),
        )
    ).all()
    ap_aging = {"current": ZERO, "1_30": ZERO, "31_60": ZERO, "61_90": ZERO, "over_90": ZERO}
    for row in ap_rows:
        outstanding = D(row.total) - D(row.allocated)
        if outstanding <= 0:
            continue
        days_past = (today - DateType.fromisoformat(str(row.due_date))).days
        if days_past <= 0:
            ap_aging["current"] += outstanding
        elif days_past <= 30:
            ap_aging["1_30"] += outstanding
        elif days_past <= 60:
            ap_aging["31_60"] += outstanding
        elif days_past <= 90:
            ap_aging["61_90"] += outstanding
        else:
            ap_aging["over_90"] += outstanding

    # AR total vs AP total, month-end balances over up to 36 months. Uses the
    # seeded control accounts (1100 AR / 2000 AP, incl. children) — same codes
    # the default_ar_account / default_ap_account settings point at. Own spine
    # (fixed 36 mo) so the widget's timeline selector can slice client-side.
    arap_rows = session.exec(
        select(
            month_expr.label("month"),
            Account.code,
            func.sum(JournalEntry.debit),
            func.sum(JournalEntry.credit),
        )
        .join(Account, Account.id == JournalEntry.account_id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(
            Transaction.tenant_id == user.tenant_id,
            (Account.code.like("1100%")) | (Account.code.like("2000%")),
        )
        .group_by(month_expr, Account.code)
        .order_by(month_expr)
    ).all()
    ARAP_MONTHS = 36
    arap_spine: list[str] = []
    ay, am = today.year, today.month - (ARAP_MONTHS - 1)
    while am <= 0:
        am += 12
        ay -= 1
    for _ in range(ARAP_MONTHS):
        arap_spine.append(f"{ay:04d}-{am:02d}")
        am += 1
        if am > 12:
            am, ay = 1, ay + 1
    arap_deltas: dict[str, dict[str, Decimal]] = {}
    for month, code, debit, credit in arap_rows:
        d = arap_deltas.setdefault(month, {"ar": ZERO, "ap": ZERO})
        if code.startswith("1100"):
            d["ar"] += D(debit or 0) - D(credit or 0)   # AR is debit-normal
        else:
            d["ap"] += D(credit or 0) - D(debit or 0)   # AP is credit-normal
    ar_bal = ap_bal = ZERO
    for month in sorted(arap_deltas):
        if month < arap_spine[0]:
            ar_bal += arap_deltas[month]["ar"]
            ap_bal += arap_deltas[month]["ap"]
    ar_series, ap_series = [], []
    for month in arap_spine:
        d = arap_deltas.get(month)
        if d:
            ar_bal += d["ar"]
            ap_bal += d["ap"]
        ar_series.append(money(ar_bal))
        ap_series.append(money(ap_bal))

    return {
        "months": spine,
        "ar_ap_trend": {"months": arap_spine, "ar": ar_series, "ap": ap_series},
        "cashflow": {
            "inflow": [money(v) for v in inflow],
            "outflow": [money(v) for v in outflow],
            "net": [money(i - o) for i, o in zip(inflow, outflow)],
        },
        "cash_balance": cash_balance,
        "sales_purchases": {
            "sales": [money(v) for v in sales],
            "purchases": [money(v) for v in purchases],
        },
        "collections": [money(v) for v in collected],
        "expense_trend": {
            "accounts": exp_accounts,
            "series": [[money(v) for v in row] for row in exp_series],
        },
        "revenue_breakdown": revenue_breakdown,
        "top_vendors": top_vendors,
        "invoice_status": invoice_status,
        "ap_aging": {k: money(v) for k, v in ap_aging.items()},
    }


@router.get("/dashboard/day-book")
def get_day_book(
    session: SessionDep, user: CurrentUserDep, date: Optional[str] = None,
):
    """One day's activity under main headings for the Day Book widget:
    vouchers grouped by type, source documents, and an audit-log category
    view covering financial and non-financial activity alike."""
    from models import AuditLog, BillPayment

    try:
        day = DateType.fromisoformat(date) if date else DateType.today()
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")
    day_str = day.isoformat()

    voucher_rows = session.exec(
        select(
            Transaction.voucher_type,
            func.count(func.distinct(Transaction.id)),
            func.sum(JournalEntry.debit),
        )
        .join(JournalEntry, JournalEntry.transaction_id == Transaction.id)
        .where(
            Transaction.tenant_id == user.tenant_id,
            Transaction.date == day_str,
        )
        .group_by(Transaction.voucher_type)
    ).all()
    vouchers = [
        {"type": vt or "JV", "count": cnt, "total": money(D(total or 0))}
        for vt, cnt, total in voucher_rows
    ]
    vouchers.sort(key=lambda v: v["type"])

    def _doc_summary(model, date_col, amount_col, extra=()):
        row = session.exec(
            select(func.count(model.id), func.sum(amount_col)).where(
                model.tenant_id == user.tenant_id, date_col == day_str, *extra
            )
        ).one()
        return {"count": row[0] or 0, "total": money(D(row[1] or 0))}

    documents = {
        "invoices": _doc_summary(Invoice, Invoice.issue_date, Invoice.total, (Invoice.status != "void",)),
        "bills": _doc_summary(Bill, Bill.bill_date, Bill.total, (Bill.status != "void",)),
        "payments_received": _doc_summary(PaymentReceived, PaymentReceived.payment_date, PaymentReceived.amount),
        "payments_made": _doc_summary(BillPayment, BillPayment.payment_date, BillPayment.amount),
    }

    # Category view: everything the audit trail saw that day — covers
    # non-financial entities (customers, products, users, …) too.
    day_start = _dt.datetime(day.year, day.month, day.day)
    day_end = day_start + timedelta(days=1)
    activity_rows = session.exec(
        select(AuditLog.entity_type, func.count(AuditLog.id))
        .where(
            AuditLog.tenant_id == user.tenant_id,
            AuditLog.timestamp >= day_start,
            AuditLog.timestamp < day_end,
        )
        .group_by(AuditLog.entity_type)
        .order_by(func.count(AuditLog.id).desc())
    ).all()
    activity = [{"category": et, "count": cnt} for et, cnt in activity_rows]

    return {
        "date": day_str,
        "vouchers": vouchers,
        "voucher_totals": {
            "count": sum(v["count"] for v in vouchers),
            "total": money(sum((D(v["total"]) for v in vouchers), ZERO)),
        },
        "documents": documents,
        "activity": activity,
    }


# ── Income statement ─────────────────────────────────────────────────────────


@router.get("/income-statement", dependencies=[perm_dep("report.income_statement")])
def get_income_statement(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    compare_start: Optional[str] = None, compare_end: Optional[str] = None,
    analytic_id: Optional[int] = None,
):
    def _leaf_rows(s, e):
        q = (
            select(
                Account.id, Account.code, Account.name, Account.type,
                func.sum(JournalEntry.debit).label("total_debit"),
                func.sum(JournalEntry.credit).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.account_id == Account.id)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(Account.type.in_(["Revenue", "Expense"]))
            .where(Transaction.tenant_id == user.tenant_id)
        )
        if analytic_id is not None:
            q = q.where(
                (JournalEntry.analytic_account_id == analytic_id)
                | (JournalEntry.analytic_2_id == analytic_id)
                | (JournalEntry.analytic_3_id == analytic_id)
            )
        if s and e:
            q = q.where(Transaction.date >= s, Transaction.date <= e)
        return session.exec(q.group_by(Account.id)).all()

    def _flat(s, e):
        # Existing flat shape (comparison mode) — unchanged.
        out = []
        for r in _leaf_rows(s, e):
            out.append({"name": r.name, "type": r.type, "code": r.code,
                        "total_debit": r.total_debit, "total_credit": r.total_credit})
        return out

    if compare_start and compare_end:
        return {"current": _flat(start, end), "comparison": _flat(compare_start, compare_end)}

    rows = _leaf_rows(start, end)
    values = {}
    for r in rows:
        debit, credit = D(r.total_debit or 0), D(r.total_credit or 0)
        amount = (credit - debit) if r.type == "Revenue" else (debit - credit)
        values[r.id] = {"amount": amount}

    accounts = session.exec(
        select(Account).where(
            Account.tenant_id == user.tenant_id,
            Account.type.in_(["Revenue", "Expense"]),
        )
    ).all()
    rev_accts = [a for a in accounts if a.type == "Revenue"]
    exp_accts = [a for a in accounts if a.type == "Expense"]
    revenue = build_account_tree(rev_accts, values, ["amount"])
    expenses = build_account_tree(exp_accts, values, ["amount"])

    def _tot(nodes):
        return sum((D(n["amount"]) for n in nodes), ZERO)

    total_rev, total_exp = _tot(revenue), _tot(expenses)
    return {
        "revenue": revenue, "expenses": expenses,
        "totals": {"revenue": total_rev, "expenses": total_exp,
                   "net_profit": total_rev - total_exp},
    }


# ── General ledger (per-account with running balance) ────────────────────────


@router.get("/ledger", dependencies=[perm_dep("report.general_ledger")])
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
            "voucher_type": tx.voucher_type,
            "description": tx.description or "", "debit": je.debit,
            "credit": je.credit, "balance": rec["running_balance"],
        })

    items = []
    for rec in accounts.values():
        rec["closing_balance"] = rec["running_balance"]
        items.append(rec)
    items.sort(key=lambda r: r["code"])
    return {"total": len(items), "items": items[skip: skip + limit]}


# ── Sub-ledger GL view ────────────────────────────────────────────────────────


def _account_gl_movement(session, tenant_id: int, account: Account, start: Optional[str], end: Optional[str]) -> dict:
    """Return {opening, debit, credit, closing} for one GL account over the window.

    Uses the same signed-balance convention as get_ledger:
      signed = (Dr - Cr) for Asset/Expense accounts (debit-normal)
             = (Cr - Dr) for Liability/Equity/Revenue accounts (credit-normal)
    """
    def _signed(atype, dr, cr):
        d, c = D(dr), D(cr)
        return (d - c) if atype in ("Asset", "Expense") else (c - d)

    # Opening: all entries before start
    opening = ZERO
    if start:
        rows = (
            session.query(JournalEntry.debit, JournalEntry.credit)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .filter(
                Transaction.tenant_id == tenant_id,
                JournalEntry.account_id == account.id,
                Transaction.date < start,
            )
            .all()
        )
        for dr, cr in rows:
            opening += _signed(account.type, dr, cr)

    # Period entries
    q = (
        session.query(JournalEntry.debit, JournalEntry.credit)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .filter(
            Transaction.tenant_id == tenant_id,
            JournalEntry.account_id == account.id,
        )
    )
    if start:
        q = q.filter(Transaction.date >= start)
    if end:
        q = q.filter(Transaction.date <= end)

    period_dr = ZERO
    period_cr = ZERO
    for dr, cr in q.all():
        period_dr += D(dr)
        period_cr += D(cr)

    if account.type in ("Asset", "Expense"):
        period_net = period_dr - period_cr
    else:
        period_net = period_cr - period_dr

    closing = opening + period_net
    return {
        "opening": money(opening),
        "debit": money(period_dr),
        "credit": money(period_cr),
        "closing": money(closing),
    }


@router.get("/ledger/subledger", dependencies=[perm_dep("report.general_ledger")])
def ledger_subledger(
    session: SessionDep, user: CurrentUserDep,
    control: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """Sub-ledger summary for a control account.

    Returns per-entity breakdowns (customers / vendors / GL accounts) that
    reconcile to the control account's GL closing balance.

    ?control=ar   → per-customer AR (control = default_ar_account / 1100)
    ?control=ap   → per-vendor AP (control = default_ap_account / 2000)
    ?control=bank → per cash/bank GL account (Asset codes starting with "10")

    Response shape:
      {
        "control": {id, code, name},
        "items": [{id, name, link, opening, debit, credit, closing}, ...],
        "control_balance": Decimal,
        "sub_total": Decimal,
        "reconciles": bool,
      }

    Reconciliation note (AR/AP): Customer.opening_balance and
    Vendor.opening_balance are setup-time snapshots NOT automatically journalised
    to the control account. If a party has a non-zero opening_balance that was
    never posted as a JE (Dr 1100 / Cr Opening Balance Equity), then sub_total
    will differ from control_balance by that amount, and reconciles == False.
    The documented fix is to post a matching JE at tenant setup.
    """
    from routers.common import get_default_account
    from routers.subledger import ar_party_movement, ap_party_movement
    from models import BankAccount, Customer, Vendor

    if control == "ar":
        # Resolve control account
        ctrl_acc = get_default_account(
            session, user.tenant_id,
            "default_ar_account", "1100", "Accounts Receivable", "Asset",
        )

        # All customers with any AR activity: invoices, payments, or opening_balance
        customers = session.exec(
            select(Customer).where(Customer.tenant_id == user.tenant_id)
        ).all()

        items = []
        for cust in customers:
            mv = ar_party_movement(session, user.tenant_id, cust, start, end)
            # Include if there's any balance or activity
            if mv["opening"] == ZERO and mv["debit"] == ZERO and mv["credit"] == ZERO:
                continue
            items.append({
                "id": cust.id,
                "name": cust.name,
                "link": f"/customers/{cust.id}/ledger",
                "opening": float(mv["opening"]),
                "debit": float(mv["debit"]),
                "credit": float(mv["credit"]),
                "closing": float(mv["closing"]),
            })

        ctrl_mv = _account_gl_movement(session, user.tenant_id, ctrl_acc, start, end)
        # ctrl_mv["closing"] uses signed convention: Asset = Dr-Cr (debit-normal)
        control_balance = float(ctrl_mv["closing"])
        sub_total = sum(i["closing"] for i in items)
        return {
            "control": {"id": ctrl_acc.id, "code": ctrl_acc.code, "name": ctrl_acc.name},
            "items": sorted(items, key=lambda r: r["name"]),
            "control_balance": control_balance,
            "sub_total": sub_total,
            "reconciles": abs(sub_total - control_balance) < 0.01,
        }

    elif control == "ap":
        # Resolve control account
        ctrl_acc = get_default_account(
            session, user.tenant_id,
            "default_ap_account", "2000", "Accounts Payable", "Liability",
        )

        vendors = session.exec(
            select(Vendor).where(Vendor.tenant_id == user.tenant_id)
        ).all()

        items = []
        for v in vendors:
            mv = ap_party_movement(session, user.tenant_id, v, start, end)
            if mv["opening"] == ZERO and mv["debit"] == ZERO and mv["credit"] == ZERO:
                continue
            items.append({
                "id": v.id,
                "name": v.name,
                "link": f"/vendors/{v.id}/ledger",
                "opening": float(mv["opening"]),
                "debit": float(mv["debit"]),
                "credit": float(mv["credit"]),
                "closing": float(mv["closing"]),
            })

        ctrl_mv = _account_gl_movement(session, user.tenant_id, ctrl_acc, start, end)
        # AP is Liability (credit-normal): closing = opening + credit - debit
        # _account_gl_movement already handles sign convention, so:
        # opening is (Cr - Dr) before start; closing = opening + (Cr - Dr) in period
        # But we stored period_dr and period_cr raw. For Liability:
        # net in period = period_cr - period_dr
        # closing = opening + net
        # Use ctrl_mv["closing"] directly since _account_gl_movement handles sign
        control_balance = float(ctrl_mv["closing"])
        sub_total = sum(i["closing"] for i in items)
        return {
            "control": {"id": ctrl_acc.id, "code": ctrl_acc.code, "name": ctrl_acc.name},
            "items": sorted(items, key=lambda r: r["name"]),
            "control_balance": control_balance,
            "sub_total": sub_total,
            "reconciles": abs(sub_total - control_balance) < 0.01,
        }

    elif control == "bank":
        # Identify cash/bank GL accounts: Asset accounts with code starting "10",
        # UNION any BankAccount.coa_account_id for the tenant.
        # This matches the "Cash & Bank balance" logic at reports.py:214 which uses
        # Account.code.like("10%") to sum all 10xx accounts.
        bank_accounts_by_id: dict = {}
        for acc in session.exec(
            select(Account).where(
                Account.tenant_id == user.tenant_id,
                Account.type == "Asset",
                Account.code.like("10%"),
            )
        ).all():
            bank_accounts_by_id[acc.id] = acc

        # Also include any explicit BankAccount.coa_account_id links
        for ba in session.exec(
            select(BankAccount).where(BankAccount.tenant_id == user.tenant_id)
        ).all():
            if ba.coa_account_id and ba.coa_account_id not in bank_accounts_by_id:
                acc = session.get(Account, ba.coa_account_id)
                if acc and acc.tenant_id == user.tenant_id:
                    bank_accounts_by_id[acc.id] = acc

        items = []
        for acc in bank_accounts_by_id.values():
            mv = _account_gl_movement(session, user.tenant_id, acc, start, end)
            if mv["opening"] == ZERO and mv["debit"] == ZERO and mv["credit"] == ZERO:
                continue
            items.append({
                "id": acc.id,
                "name": acc.name,
                "link": f"/ledger?account_id={acc.id}",
                "opening": float(mv["opening"]),
                "debit": float(mv["debit"]),
                "credit": float(mv["credit"]),
                "closing": float(mv["closing"]),
            })

        sub_total = sum(i["closing"] for i in items)
        # For bank, control_balance = Σ of the individual accounts' closings
        # (they ARE the control group — no single aggregating control account)
        control_balance = sub_total
        return {
            "control": {"id": None, "code": "10xx", "name": "Cash & Bank"},
            "items": sorted(items, key=lambda r: r["name"]),
            "control_balance": control_balance,
            "sub_total": sub_total,
            "reconciles": True,  # by construction: sub_total == control_balance
        }

    else:
        from fastapi import HTTPException
        raise HTTPException(400, f"Unknown control type: {control!r}. Use ar, ap, or bank.")


# ── Balance sheet ────────────────────────────────────────────────────────────


@router.get("/balance-sheet", dependencies=[perm_dep("report.balance_sheet")])
def get_balance_sheet(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    date: Optional[str] = None,
    compare_end: Optional[str] = None,
):
    def _leaf_rows(s, e, as_of):
        q = (
            select(
                Account.id, Account.code, Account.name, Account.type,
                func.sum(JournalEntry.debit).label("total_debit"),
                func.sum(JournalEntry.credit).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.account_id == Account.id)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(Transaction.tenant_id == user.tenant_id)
        )
        if s:
            q = q.where(Transaction.date >= s)
        if e:
            q = q.where(Transaction.date <= e)
        elif as_of:
            q = q.where(Transaction.date <= as_of)
        return session.exec(q.group_by(Account.id)).all()

    def _flat(s, e, as_of):
        # Existing flat shape (used for comparison mode) — unchanged behaviour.
        items, net_income = [], ZERO
        for r in _leaf_rows(s, e, as_of):
            debit, credit = D(r.total_debit or 0), D(r.total_credit or 0)
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
        if net_income != ZERO:
            items.append({"code": "RE-CUR", "name": "Retained Earnings (Current Period)",
                          "type": "Equity", "balance": net_income})
        return items

    # Comparison mode: keep the existing flat {current, comparison} shape.
    if compare_end:
        return {"current": _flat(start, end, date), "comparison": _flat(None, compare_end, None)}

    # Single period: hierarchical tree per section.
    rows = _leaf_rows(start, end, date)
    values, net_income = {}, ZERO
    for r in rows:
        debit, credit = D(r.total_debit or 0), D(r.total_credit or 0)
        if r.type == "Asset":
            values[r.id] = {"balance": debit - credit}
        elif r.type in ("Liability", "Equity"):
            values[r.id] = {"balance": credit - debit}
        elif r.type == "Revenue":
            net_income += credit - debit
        elif r.type == "Expense":
            net_income -= debit - credit

    accounts = session.exec(
        select(Account).where(Account.tenant_id == user.tenant_id)
    ).all()
    by_type = {t: [a for a in accounts if a.type == t] for t in ("Asset", "Liability", "Equity")}

    def _section(type_name):
        return build_account_tree(by_type[type_name], values, ["balance"])

    assets = _section("Asset")
    liabilities = _section("Liability")
    equity = _section("Equity")
    if net_income != ZERO:
        equity.append({
            "id": None, "code": "RE-CUR", "name": "Retained Earnings (Current Period)",
            "type": "Equity", "is_group": False, "level": 0,
            "balance": net_income, "children": [],
        })

    def _tot(nodes):
        return sum((D(n["balance"]) for n in nodes), ZERO)

    return {
        "assets": assets, "liabilities": liabilities, "equity": equity,
        "totals": {"assets": _tot(assets), "liabilities": _tot(liabilities), "equity": _tot(equity)},
    }


# ── Cash flow (indirect) ─────────────────────────────────────────────────────


@router.get("/cash-flow", dependencies=[perm_dep("report.cash_flow")])
def cash_flow_statement(
    session: SessionDep, user: CurrentUserDep,
    start: str = Query(default=""), end: str = Query(default=""),
    compare_start: Optional[str] = None, compare_end: Optional[str] = None,
):
    if not start:
        start = f"{DateType.today().year}-01-01"
    if not end:
        end = str(DateType.today())

    def _compute(s: str, e: str) -> dict:
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
                    Transaction.date >= s,
                    Transaction.date <= e,
                )
            ).all()
            if acct.type in ("Asset", "Expense"):
                return sum((D(entry.debit) - D(entry.credit) for entry in entries), ZERO)
            return sum((D(entry.credit) - D(entry.debit) for entry in entries), ZERO)

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
                return sum((D(entry.debit) - D(entry.credit) for entry in entries), ZERO)
            return sum((D(entry.credit) - D(entry.debit) for entry in entries), ZERO)

        try:
            start_dt = DateType.fromisoformat(s)
            day_before = str(start_dt - timedelta(days=1))
        except Exception:
            day_before = s

        beginning_balance = sum((balance_at(a, day_before) for a in cash_accounts), ZERO)
        ending_balance = sum((balance_at(a, e) for a in cash_accounts), ZERO)
        net_cash_change = operating_cash + investing_cash + financing_cash
        # Reconciling difference: any actual cash movement the classifier didn't
        # bucket. By construction net_cash_change + unclassified == ending - beginning,
        # so the statement always ties out to real cash.
        unclassified = (ending_balance - beginning_balance) - net_cash_change

        return {
            "period": {"start": s, "end": e},
            "net_income": net_income,
            "operating_adjustments": {"ar_change": ar_change, "ap_change": ap_change},
            "operating_cash": operating_cash,
            "investing_items": investing_items,
            "investing_cash": investing_cash,
            "financing_items": financing_items,
            "financing_cash": financing_cash,
            "net_cash_change": net_cash_change,
            "unclassified": unclassified,
            "beginning_balance": beginning_balance,
            "ending_balance": ending_balance,
        }

    current = _compute(start, end)
    if compare_start and compare_end:
        return {"current": current, "comparison": _compute(compare_start, compare_end)}
    return current


# ── Tax summary ──────────────────────────────────────────────────────────────


@router.get("/tax-summary", dependencies=[perm_dep("report.tax")])
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


# ── Tax return by code (#263) ────────────────────────────────────────────────


@router.get("/tax-return", dependencies=[perm_dep("report.tax")])
def tax_return_by_code(
    session: SessionDep, user: CurrentUserDep,
    start: str = Query(default=""), end: str = Query(default=""),
):
    """Period tax return from line snapshots (output − input by tax code).

    Reverse-charge tax is reported but excluded from net payable (no GL leg).
    """
    if not start:
        start = f"{DateType.today().year}-07-01"
    if not end:
        end = str(DateType.today())

    tid = user.tenant_id
    # Accumulate per tax_code_id
    buckets: dict[int, dict] = {}

    def _bucket(tc: TaxCode) -> dict:
        b = buckets.get(tc.id)
        if b is None:
            b = {
                "tax_code_id": tc.id,
                "code": tc.code,
                "name": tc.name,
                "type": tc.type,
                "rate": float(tc.rate),
                "is_reverse_charge": bool(tc.is_reverse_charge),
                "is_exempt": bool(tc.is_exempt),
                "is_zero_rated": bool(tc.is_zero_rated),
                "taxable_base": ZERO,
                "output_tax": ZERO,
                "input_tax": ZERO,
                "reverse_charge_tax": ZERO,
            }
            buckets[tc.id] = b
        return b

    inv_rows = session.exec(
        select(InvoiceLine, TaxCode)
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .join(TaxCode, TaxCode.id == InvoiceLine.tax_code_id)
        .where(
            Invoice.tenant_id == tid,
            Invoice.issue_date >= start,
            Invoice.issue_date <= end,
            InvoiceLine.tax_code_id.is_not(None),  # type: ignore[union-attr]
        )
    ).all()
    for ln, tc in inv_rows:
        b = _bucket(tc)
        b["taxable_base"] = money(b["taxable_base"] + D(ln.amount))
        tax_amt = D(ln.tax_amount or 0)
        if ln.tax_rate is not None:
            b["rate"] = float(ln.tax_rate)
        if tc.is_reverse_charge:
            b["reverse_charge_tax"] = money(b["reverse_charge_tax"] + tax_amt)
        elif tc.type == "output":
            b["output_tax"] = money(b["output_tax"] + tax_amt)
        elif tc.type == "input":
            b["input_tax"] = money(b["input_tax"] + tax_amt)

    bill_rows = session.exec(
        select(BillLine, TaxCode)
        .join(Bill, Bill.id == BillLine.bill_id)
        .join(TaxCode, TaxCode.id == BillLine.tax_code_id)
        .where(
            Bill.tenant_id == tid,
            Bill.bill_date >= start,
            Bill.bill_date <= end,
            BillLine.tax_code_id.is_not(None),  # type: ignore[union-attr]
        )
    ).all()
    for ln, tc in bill_rows:
        b = _bucket(tc)
        b["taxable_base"] = money(b["taxable_base"] + D(ln.amount))
        tax_amt = D(ln.tax_amount or 0)
        if ln.tax_rate is not None:
            b["rate"] = float(ln.tax_rate)
        if tc.is_reverse_charge:
            b["reverse_charge_tax"] = money(b["reverse_charge_tax"] + tax_amt)
        elif tc.type == "input":
            b["input_tax"] = money(b["input_tax"] + tax_amt)
        elif tc.type == "output":
            b["output_tax"] = money(b["output_tax"] + tax_amt)

    rows = []
    tot_base = tot_out = tot_in = tot_rc = ZERO
    for b in sorted(buckets.values(), key=lambda x: x["code"]):
        net = money(b["output_tax"] - b["input_tax"])
        rows.append({
            **b,
            "taxable_base": b["taxable_base"],
            "output_tax": b["output_tax"],
            "input_tax": b["input_tax"],
            "reverse_charge_tax": b["reverse_charge_tax"],
            "net": net,
        })
        tot_base = money(tot_base + b["taxable_base"])
        tot_out = money(tot_out + b["output_tax"])
        tot_in = money(tot_in + b["input_tax"])
        tot_rc = money(tot_rc + b["reverse_charge_tax"])

    return {
        "period": {"start": start, "end": end},
        "rows": rows,
        "totals": {
            "taxable_base": tot_base,
            "output_tax": tot_out,
            "input_tax": tot_in,
            "reverse_charge_tax": tot_rc,
            "net": money(tot_out - tot_in),
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
    """P&L filtered to a single analytic value (any dimension slot)."""
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
            (
                (JournalEntry.analytic_account_id == analytic_account_id)
                | (JournalEntry.analytic_2_id == analytic_account_id)
                | (JournalEntry.analytic_3_id == analytic_account_id)
            ),
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


@router.get("/dimensional-pl", dependencies=[perm_dep("report.income_statement")])
def get_dimensional_pl(
    session: SessionDep,
    user: CurrentUserDep,
    dimension_id: Optional[int] = None,
    analytic_id: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """Dimensional P&L (#260).

    - With `analytic_id`: P&L lines tagged with that analytic on any slot.
    - With `dimension_id` only: breakdown by each analytic value of that dimension.
    - With neither: one row-group per active analytic value (legacy flat).
    """
    from models import AnalyticAccount, AnalyticDimension

    def _pl_for_analytic(aid: int) -> list[dict]:
        q = (
            select(
                Account.name, Account.type, Account.code,
                func.sum(JournalEntry.debit).label("dr"),
                func.sum(JournalEntry.credit).label("cr"),
            )
            .join(JournalEntry, JournalEntry.account_id == Account.id)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(
                Transaction.tenant_id == user.tenant_id,
                (
                    (JournalEntry.analytic_account_id == aid)
                    | (JournalEntry.analytic_2_id == aid)
                    | (JournalEntry.analytic_3_id == aid)
                ),
                Account.type.in_(["Revenue", "Expense"]),
            )
        )
        if start and end:
            q = q.where(Transaction.date >= start, Transaction.date <= end)
        rows = session.exec(q.group_by(Account.id).order_by(Account.type.desc(), Account.code)).all()
        out = []
        for r in rows:
            debit, credit = D(r.dr or 0), D(r.cr or 0)
            amount = (credit - debit) if r.type == "Revenue" else (debit - credit)
            out.append({
                "name": r.name, "code": r.code, "type": r.type,
                "total_debit": debit, "total_credit": credit, "amount": amount,
            })
        return out

    if analytic_id is not None:
        aa = session.exec(
            select(AnalyticAccount).where(
                AnalyticAccount.id == analytic_id,
                AnalyticAccount.tenant_id == user.tenant_id,
            )
        ).first()
        if not aa:
            raise HTTPException(404, "Analytic account not found")
        lines = _pl_for_analytic(analytic_id)
        rev = sum((D(r["amount"]) for r in lines if r["type"] == "Revenue"), ZERO)
        exp = sum((D(r["amount"]) for r in lines if r["type"] == "Expense"), ZERO)
        return {
            "mode": "analytic",
            "analytic": {"id": aa.id, "code": aa.code, "name": aa.name},
            "lines": lines,
            "totals": {"revenue": rev, "expenses": exp, "net_profit": rev - exp},
        }

    aa_q = select(AnalyticAccount).where(
        AnalyticAccount.tenant_id == user.tenant_id,
        AnalyticAccount.is_active == True,  # noqa: E712
    )
    dim = None
    if dimension_id is not None:
        dim = session.exec(
            select(AnalyticDimension).where(
                AnalyticDimension.id == dimension_id,
                AnalyticDimension.tenant_id == user.tenant_id,
            )
        ).first()
        if not dim:
            raise HTTPException(404, "Dimension not found")
        aa_q = aa_q.where(AnalyticAccount.dimension_id == dimension_id)

    accounts = session.exec(aa_q.order_by(AnalyticAccount.code)).all()
    segments = []
    for aa in accounts:
        lines = _pl_for_analytic(aa.id)
        if not lines:
            continue
        rev = sum((D(r["amount"]) for r in lines if r["type"] == "Revenue"), ZERO)
        exp = sum((D(r["amount"]) for r in lines if r["type"] == "Expense"), ZERO)
        segments.append({
            "analytic": {"id": aa.id, "code": aa.code, "name": aa.name},
            "lines": lines,
            "totals": {"revenue": rev, "expenses": exp, "net_profit": rev - exp},
        })
    return {
        "mode": "breakdown",
        "dimension": (
            {"id": dim.id, "code": dim.code, "name": dim.name} if dim else None
        ),
        "segments": segments,
    }


# ── Budget vs Actual ──────────────────────────────────────────────────────────


@router.get("/budget-vs-actual", dependencies=[perm_dep("report.budget_vs_actual")])
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
def run_fx_revaluation_endpoint(
    session: SessionDep, user: CurrentUserDep,
    revaluation_date: str,
):
    """Revalue open foreign-currency AR and AP to closing rate. IAS 21.23."""
    from services.fx_revaluation import run_fx_revaluation
    return run_fx_revaluation(session, user, revaluation_date)


# ── Product Ledger (by store or consolidated) ────────────────────────────────

_IN_DIRECTIONS = {"RECEIPT", "CUSTODIAL_RECEIPT", "COMPLETION", "CUSTODIAL_COMPLETION"}


@router.get("/product-ledger", dependencies=[perm_dep("report.product_ledger")])
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
    # First pass: collect filtered rows and their source_doc_ids for batch lookup.
    running = ZERO
    filtered_rows: list[tuple] = []   # (movement, date_str, sign)
    inv_ids: set[int] = set()
    bill_ids: set[int] = set()
    for m in rows:
        d = m.occurred_at.date().isoformat() if hasattr(m.occurred_at, "date") else str(m.occurred_at)[:10]
        if start and d < start:
            continue
        if end and d > end:
            continue
        sign = 1 if m.direction in _IN_DIRECTIONS else -1
        running += sign * D(m.qty)
        filtered_rows.append((m, d, sign, running))
        if m.source_doc_type == "invoice" and m.source_doc_id:
            inv_ids.add(m.source_doc_id)
        elif m.source_doc_type == "bill" and m.source_doc_id:
            bill_ids.add(m.source_doc_id)

    # Batch-fetch reference numbers (one query per doc type).
    inv_refs: dict[int, str] = {}
    if inv_ids:
        for inv in session.exec(select(Invoice.id, Invoice.number).where(Invoice.id.in_(inv_ids))).all():  # type: ignore[attr-defined]
            inv_refs[inv[0]] = inv[1]
    bill_refs: dict[int, str] = {}
    if bill_ids:
        for bill in session.exec(select(Bill.id, Bill.number).where(Bill.id.in_(bill_ids))).all():  # type: ignore[attr-defined]
            bill_refs[bill[0]] = bill[1]

    # Second pass: build response items.
    items = []
    for m, d, sign, running_qty in filtered_rows:
        loc_id = m.to_location_id if sign > 0 else m.from_location_id
        doc_type = m.source_doc_type or ""
        if doc_type == "invoice" and m.source_doc_id:
            source_ref = inv_refs.get(m.source_doc_id, doc_type)
        elif doc_type == "bill" and m.source_doc_id:
            source_ref = bill_refs.get(m.source_doc_id, doc_type)
        else:
            source_ref = doc_type
        items.append({
            "date": d, "direction": m.direction,
            "qty_in": D(m.qty) if sign > 0 else ZERO,
            "qty_out": D(m.qty) if sign < 0 else ZERO,
            "running_qty": running_qty, "unit_cost": m.unit_cost,
            "source": doc_type,
            "source_ref": source_ref,
            "location": loc_names.get(loc_id, "") if loc_id else "",
        })
    return {"product_id": product_id, "location_id": location_id, "items": items}


# ── Inventory Performance ─────────────────────────────────────────────────────


@router.get("/inventory-performance", dependencies=[perm_dep("report.inventory_performance")])
def inventory_performance(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    from models import StockMovement

    prods = session.exec(
        select(Product).where(Product.tenant_id == user.tenant_id,
                              Product.product_type == "stock")
    ).all()

    # Pre-load all tenant categories for name resolution (avoids N+1)
    cats = {c.id: c for c in session.exec(
        select(ProductCategory).where(ProductCategory.tenant_id == user.tenant_id)
    ).all()}

    # Batch-load invoice lines for all products in one query, filtering by period
    inv_q = (
        select(InvoiceLine.product_id, InvoiceLine.amount)
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.status.in_(["posted", "partial", "paid"]),
        )
    )
    if start:
        inv_q = inv_q.where(Invoice.issue_date >= start)
    if end:
        inv_q = inv_q.where(Invoice.issue_date <= end)
    sales_by_product: dict[int, Decimal] = {}
    for pid, amt in session.exec(inv_q).all():
        if pid is not None:
            sales_by_product[pid] = sales_by_product.get(pid, ZERO) + D(amt)

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
        cogs_val = money(units_sold * D(p.avg_cost))
        sales_val = money(sales_by_product.get(p.id, ZERO))
        # Resolve category name
        cat = cats.get(p.category_id) if p.category_id else None
        if cat:
            parent = cats.get(cat.parent_id) if cat.parent_id else None
            cat_name = f"{parent.name} › {cat.name}" if parent else cat.name
        else:
            cat_name = None

        sv = D(sales_val)
        margin_pct = float(round((sv - D(cogs_val)) / sv * 100, 1)) if sv > 0 else None
        out.append({
            "id": p.id, "name": p.name, "code": p.code,
            "on_hand": D(p.stock_qty), "avg_cost": D(p.avg_cost),
            "stock_value": money(D(p.stock_qty) * D(p.avg_cost)),
            "reorder_level": D(p.reorder_level),
            "low_stock": D(p.stock_qty) <= D(p.reorder_level),
            "last_movement": last, "units_sold": units_sold,
            "cogs": cogs_val, "sales_value": sales_val,
            "margin_pct": margin_pct,
            "category_id": p.category_id, "category_name": cat_name,
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


@router.get("/customer-performance", dependencies=[perm_dep("report.customer_performance")])
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


# ── Product Performance shared helpers ────────────────────────────────────────
# Direction classification for product-performance and its export endpoint.
# Keeping these at module level avoids redefining them inside every request.
_PP_ADD_DIRS = ("RECEIPT", "COMPLETION")
_PP_OUT_DIRS = ("SHIPMENT", "DELIVERY", "ISSUE")
_PP_RETURN_DIRS = ("ADJUSTMENT",)

# Export column headers — single source of truth used by both the JSON and
# export endpoints so they never drift.
_PP_EXPORT_HEADERS = [
    "Product", "Code",
    "Opening Qty", "Opening Value",
    "Purchased Qty", "Sold Qty",
    "Closing Qty", "Closing Value",
    "Revenue", "GP",
]


def _pp_signed_effect(direction, qty):
    """Return the signed qty effect of a stock movement direction."""
    if direction in _PP_ADD_DIRS:
        return qty
    if direction in _PP_OUT_DIRS or direction in _PP_RETURN_DIRS:
        return -qty
    return ZERO


def _pp_compute_rows(session, tenant_id: int, start: Optional[str], end: Optional[str]) -> list[dict]:
    """Shared per-product computation used by both the JSON and export endpoints.

    Returns a list of row dicts (sorted by closing_value desc).
    """
    from models import StockMovement, InvoiceLine

    prods = session.exec(
        select(Product).where(Product.tenant_id == tenant_id,
                              Product.product_type == "stock")
    ).all()
    out = []
    for p in prods:
        mv = session.exec(
            select(StockMovement).where(
                StockMovement.tenant_id == tenant_id,
                StockMovement.product_id == p.id,
            )
        ).all()
        opening = purchased = sold = ZERO
        for m in mv:
            d = m.occurred_at.date().isoformat()
            qty = D(m.qty)
            if start and d < start:
                opening += _pp_signed_effect(m.direction, qty)
            elif (not start or d >= start) and (not end or d <= end):
                if m.direction in _PP_ADD_DIRS:
                    purchased += qty
                elif m.direction in _PP_RETURN_DIRS:
                    purchased -= qty          # purchase return → net purchases
                elif m.direction in _PP_OUT_DIRS:
                    sold += qty
        avg = D(p.avg_cost)
        closing = opening + purchased - sold
        # sales revenue for the product in window
        rq = (select(func.coalesce(func.sum(InvoiceLine.amount), 0))
              .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
              .where(Invoice.tenant_id == tenant_id,
                     InvoiceLine.product_id == p.id))
        if start:
            rq = rq.where(Invoice.issue_date >= start)
        if end:
            rq = rq.where(Invoice.issue_date <= end)
        revenue = D(session.exec(rq).first() or 0)
        cogs = sold * avg
        out.append({
            "product_id": p.id, "name": p.name, "code": p.code,
            "category_id": p.category_id,
            "opening_qty": float(opening), "opening_value": money(opening * avg),
            "purchased_qty": float(purchased),
            "sold_qty": float(sold),
            "closing_qty": float(closing), "closing_value": money(closing * avg),
            "gp": money(revenue - cogs), "revenue": money(revenue),
        })
    out.sort(key=lambda r: r["closing_value"], reverse=True)
    return out


def _cat_label(cats: dict, cat_id) -> str:
    """Resolve a category_id to a 'Parent › Child' (or 'Parent') label.

    Shared by customer_performance, product-coa and product-performance
    category grouping.  Returns 'Uncategorized' when no match.
    """
    c = cats.get(cat_id)
    if not c:
        return "Uncategorized"
    if c.parent_id is None:
        return c.name
    par = cats.get(c.parent_id)
    return f"{par.name} › {c.name}" if par else c.name


@router.get("/product-performance")
def product_performance(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
    group_by: Optional[str] = None,
):
    """Per-product period movement: opening/purchased/sold(net)/closing with
    values at avg_cost, plus GP (sales revenue - COGS) for the window.

    Pass ``group_by=category`` to receive rows grouped by product category
    with per-category subtotals.  The flat list remains the default.
    """
    rows = _pp_compute_rows(session, user.tenant_id, start, end)

    if group_by == "category":
        from models import ProductCategory
        cats = {c.id: c for c in session.exec(
            select(ProductCategory).where(ProductCategory.tenant_id == user.tenant_id)
        ).all()}

        # Accumulate with Decimal arithmetic then convert to float for JSON
        _acc: dict = {}
        for row in rows:
            label = _cat_label(cats, row["category_id"])
            if label not in _acc:
                _acc[label] = {
                    "total_closing_qty": ZERO,
                    "total_closing_value": ZERO,
                    "total_gp": ZERO,
                    "total_revenue": ZERO,
                    "items": [],
                }
            _acc[label]["total_closing_qty"] += D(str(row["closing_qty"]))
            _acc[label]["total_closing_value"] += D(str(row["closing_value"]))
            _acc[label]["total_gp"] += D(str(row["gp"]))
            _acc[label]["total_revenue"] += D(str(row["revenue"]))
            # strip internal category_id from the item rows
            _acc[label]["items"].append({k: v for k, v in row.items() if k != "category_id"})

        group_list = []
        for label, g in sorted(_acc.items(), key=lambda kv: kv[1]["total_closing_value"], reverse=True):
            group_list.append({
                "name": label,
                "total_closing_qty": float(g["total_closing_qty"]),
                "total_closing_value": float(g["total_closing_value"]),
                "total_gp": float(g["total_gp"]),
                "total_revenue": float(g["total_revenue"]),
                "items": g["items"],
            })
        return {"groups": group_list}

    # flat (default) — strip internal category_id
    flat = [{k: v for k, v in r.items() if k != "category_id"} for r in rows]
    return {"items": flat}


# ── Product Performance Export ────────────────────────────────────────────────

@router.get("/product-performance/export")
def product_performance_export(
    session: SessionDep, user: CurrentUserDep,
    format: str = Query("csv"),
    start: Optional[str] = None, end: Optional[str] = None,
):
    """Stream a CSV or XLSX download of the product-performance report.

    Uses the same per-product row computation as the JSON endpoint (DRY via
    ``_pp_compute_rows``).  Cell values are formula-injection-safe via
    ``services.export_utils.safe_cell``.
    """
    if format not in ("csv", "xlsx"):
        raise HTTPException(400, f"unknown format {format!r} — use csv or xlsx")

    rows = _pp_compute_rows(session, user.tenant_id, start, end)

    # Map internal row keys → export column order
    def _to_export(r: dict) -> dict:
        return {
            "Product": r["name"],
            "Code": r["code"] or "",
            "Opening Qty": r["opening_qty"],
            "Opening Value": r["opening_value"],
            "Purchased Qty": r["purchased_qty"],
            "Sold Qty": r["sold_qty"],
            "Closing Qty": r["closing_qty"],
            "Closing Value": r["closing_value"],
            "Revenue": r["revenue"],
            "GP": r["gp"],
        }

    export_rows = [_to_export(r) for r in rows]
    fname_base = f"product-performance-{start or 'all'}-{end or 'all'}"

    if format == "csv":
        return stream_csv(export_rows, _PP_EXPORT_HEADERS, f"{fname_base}.csv")
    return stream_xlsx(export_rows, _PP_EXPORT_HEADERS, f"{fname_base}.xlsx")


# ── Withholding tax period report (#267) ─────────────────────────────────────


@router.get("/wht", dependencies=[perm_dep("report.tax")])
def wht_report(
    session: SessionDep, user: CurrentUserDep,
    start: str = Query(default=""), end: str = Query(default=""),
):
    """WHT deducted on bill payments, grouped by vendor."""
    if not start:
        start = f"{DateType.today().year}-01-01"
    if not end:
        end = str(DateType.today())

    pays = session.exec(
        select(BillPayment).where(
            BillPayment.tenant_id == user.tenant_id,
            BillPayment.payment_date >= start,
            BillPayment.payment_date <= end,
            BillPayment.wht_amount > 0,
        )
    ).all()

    buckets: dict[tuple, dict] = {}
    for p in pays:
        key = (p.vendor_id, p.vendor_name or "—")
        b = buckets.get(key)
        if b is None:
            b = {
                "vendor_id": p.vendor_id,
                "vendor": p.vendor_name or "—",
                "base": ZERO,
                "wht": ZERO,
                "payments": 0,
            }
            buckets[key] = b
        b["base"] = money(b["base"] + D(p.amount))
        b["wht"] = money(b["wht"] + D(p.wht_amount))
        b["payments"] += 1

    items = sorted(buckets.values(), key=lambda r: r["vendor"].lower())
    tot_base = money(sum((D(i["base"]) for i in items), ZERO))
    tot_wht = money(sum((D(i["wht"]) for i in items), ZERO))
    tot_pays = sum(i["payments"] for i in items)

    return {
        "period": {"start": start, "end": end},
        "items": items,
        "totals": {"base": tot_base, "wht": tot_wht, "payments": tot_pays},
    }


# ── Corporate tax worksheet (#267) ───────────────────────────────────────────


class CitAdjustmentCreate(BaseModel):
    fiscal_year: str
    kind: str  # addback | deduction
    description: str
    amount: Decimal


class CitAdjustmentUpdate(BaseModel):
    fiscal_year: Optional[str] = None
    kind: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = None


def _cit_adj_serialize(row: CitAdjustment) -> dict:
    return {
        "id": row.id,
        "fiscal_year": row.fiscal_year,
        "kind": row.kind,
        "description": row.description,
        "amount": row.amount,
    }


@router.get("/cit-adjustments", dependencies=[perm_dep("report.tax")])
def list_cit_adjustments(
    session: SessionDep, user: CurrentUserDep,
    fiscal_year: Optional[str] = None,
):
    q = select(CitAdjustment).where(CitAdjustment.tenant_id == user.tenant_id)
    if fiscal_year:
        q = q.where(CitAdjustment.fiscal_year == fiscal_year)
    rows = session.exec(q.order_by(CitAdjustment.id)).all()
    return {"items": [_cit_adj_serialize(r) for r in rows]}


@router.post("/cit-adjustments", status_code=201, dependencies=[perm_dep("report.tax", "edit")])
def create_cit_adjustment(
    session: SessionDep, user: WriteUserDep, body: CitAdjustmentCreate
):
    if body.kind not in ("addback", "deduction"):
        raise HTTPException(400, "kind must be 'addback' or 'deduction'")
    if not body.fiscal_year.strip():
        raise HTTPException(400, "fiscal_year is required")
    row = CitAdjustment(
        tenant_id=user.tenant_id,
        fiscal_year=body.fiscal_year.strip(),
        kind=body.kind,
        description=body.description.strip(),
        amount=money(body.amount),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _cit_adj_serialize(row)


@router.put("/cit-adjustments/{adj_id}", dependencies=[perm_dep("report.tax", "edit")])
def update_cit_adjustment(
    session: SessionDep, user: WriteUserDep, adj_id: int, body: CitAdjustmentUpdate
):
    row = session.exec(
        select(CitAdjustment).where(
            CitAdjustment.id == adj_id,
            CitAdjustment.tenant_id == user.tenant_id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Adjustment not found")
    payload = body.model_dump(exclude_unset=True)
    if "kind" in payload and payload["kind"] not in ("addback", "deduction"):
        raise HTTPException(400, "kind must be 'addback' or 'deduction'")
    if "amount" in payload:
        payload["amount"] = money(payload["amount"])
    for k, v in payload.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _cit_adj_serialize(row)


@router.delete("/cit-adjustments/{adj_id}", status_code=204, dependencies=[perm_dep("report.tax", "edit")])
def delete_cit_adjustment(
    session: SessionDep, user: WriteUserDep, adj_id: int
):
    row = session.exec(
        select(CitAdjustment).where(
            CitAdjustment.id == adj_id,
            CitAdjustment.tenant_id == user.tenant_id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Adjustment not found")
    session.delete(row)
    session.commit()
    return None


@router.get("/cit-worksheet", dependencies=[perm_dep("report.tax")])
def cit_worksheet(
    session: SessionDep, user: CurrentUserDep,
    start: str = Query(default=""),
    end: str = Query(default=""),
    fiscal_year: Optional[str] = None,
    tax_rate: Decimal = Query(default=Decimal("29")),
):
    """Management CIT worksheet: accounting profit + manual adjustments.

    Not a filing return — estimated tax uses a flat ``tax_rate`` (default 29%).
    """
    if not start:
        start = f"{DateType.today().year}-01-01"
    if not end:
        end = str(DateType.today())
    fy = (fiscal_year or str(DateType.fromisoformat(start).year)).strip()

    # Accounting profit from P&L (same basis as income-statement totals)
    accounts = session.exec(
        select(Account).where(Account.tenant_id == user.tenant_id)
    ).all()

    def period_net(acct: Account) -> Decimal:
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
        debit = sum((D(e.debit) for e in entries), ZERO)
        credit = sum((D(e.credit) for e in entries), ZERO)
        if acct.type == "Revenue":
            return credit - debit
        if acct.type == "Expense":
            return debit - credit
        return ZERO

    revenue = money(sum((period_net(a) for a in accounts if a.type == "Revenue"), ZERO))
    expenses = money(sum((period_net(a) for a in accounts if a.type == "Expense"), ZERO))
    accounting_profit = money(revenue - expenses)

    adjs = session.exec(
        select(CitAdjustment).where(
            CitAdjustment.tenant_id == user.tenant_id,
            CitAdjustment.fiscal_year == fy,
        )
    ).all()
    addbacks = [_cit_adj_serialize(a) for a in adjs if a.kind == "addback"]
    deductions = [_cit_adj_serialize(a) for a in adjs if a.kind == "deduction"]
    total_addbacks = money(sum((D(a.amount) for a in adjs if a.kind == "addback"), ZERO))
    total_deductions = money(sum((D(a.amount) for a in adjs if a.kind == "deduction"), ZERO))
    taxable_income = money(accounting_profit + total_addbacks - total_deductions)
    rate = D(tax_rate)
    estimated_tax = money(max(ZERO, taxable_income) * rate / D("100"))

    return {
        "period": {"start": start, "end": end},
        "fiscal_year": fy,
        "tax_rate": rate,
        "accounting_profit": accounting_profit,
        "revenue": revenue,
        "expenses": expenses,
        "addbacks": addbacks,
        "deductions": deductions,
        "total_addbacks": total_addbacks,
        "total_deductions": total_deductions,
        "taxable_income": taxable_income,
        "estimated_tax": estimated_tax,
        "note": "Management worksheet — not a statutory tax return.",
    }
