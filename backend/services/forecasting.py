"""Lightweight forecasting / churn heuristics (#125) — no heavy ML deps required."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean, pstdev
from typing import Optional

from sqlmodel import Session, select

from models import Bill, Budget, Customer, Invoice, PaymentReceived


def _month_key(iso: str) -> str:
    return (iso or "")[:7]


def forecast_revenue(session: Session, tenant_id: int, periods: int = 90) -> dict:
    """Simple exponential smoothing on monthly invoice totals + CI band."""
    invoices = session.exec(
        select(Invoice).where(
            Invoice.tenant_id == tenant_id,
            Invoice.status.notin_(["draft", "void", "voided"]),  # type: ignore
        )
    ).all()
    by_month: dict[str, float] = defaultdict(float)
    for inv in invoices:
        by_month[_month_key(inv.issue_date)] += float(inv.total or 0)
    months = sorted(by_month.keys())
    actuals = [{"period": m, "amount": round(by_month[m], 2)} for m in months]

    if not months:
        return {"actuals": [], "forecast": [], "lower_bound": [], "upper_bound": []}

    series = [by_month[m] for m in months]
    alpha = 0.4
    level = series[0]
    for x in series[1:]:
        level = alpha * x + (1 - alpha) * level
    residual = [abs(series[i] - level) for i in range(len(series))]
    sigma = pstdev(residual) if len(residual) > 1 else (residual[0] if residual else 0)
    # Project next ~3 months (90 days ≈ 3 periods)
    n_months = max(1, periods // 30)
    last = datetime.strptime(months[-1] + "-01", "%Y-%m-%d").date()
    forecast, lower, upper = [], [], []
    for i in range(1, n_months + 1):
        y, m = last.year, last.month + i
        while m > 12:
            m -= 12
            y += 1
        period = f"{y:04d}-{m:02d}"
        forecast.append({"period": period, "amount": round(level, 2)})
        lower.append({"period": period, "amount": round(max(0, level - 1.28 * sigma), 2)})
        upper.append({"period": period, "amount": round(level + 1.28 * sigma, 2)})
    return {
        "actuals": actuals,
        "forecast": forecast,
        "lower_bound": lower,
        "upper_bound": upper,
    }


def predict_cash_flow(session: Session, tenant_id: int, horizon_days: int = 60, floor: float = 0) -> dict:
    """Bank-ish projection from AR collections + AP due — opening = recent payments net."""
    today = date.today()
    # Opening proxy: sum of payments received last 30d − bills paid approximation
    recent_in = session.exec(
        select(PaymentReceived).where(PaymentReceived.tenant_id == tenant_id)
    ).all()
    opening = sum(float(p.amount or 0) for p in recent_in[-50:]) * 0.1  # soft proxy

    invoices = session.exec(
        select(Invoice).where(
            Invoice.tenant_id == tenant_id,
            Invoice.status.in_(["sent", "overdue", "partial", "unpaid", "posted"]),  # type: ignore
        )
    ).all()
    bills = session.exec(
        select(Bill).where(
            Bill.tenant_id == tenant_id,
            Bill.status.in_(["open", "partial", "unpaid", "posted", "approved"]),  # type: ignore
        )
    ).all()

    daily = []
    bal = opening
    alert_day = None
    for d in range(horizon_days + 1):
        day = today + timedelta(days=d)
        iso = day.isoformat()
        inflow = sum(
            float(i.total or 0)
            for i in invoices
            if (i.due_date or "")[:10] == iso
        )
        outflow = sum(
            float(b.total or 0)
            for b in bills
            if (b.due_date or "")[:10] == iso
        )
        bal = bal + inflow - outflow
        daily.append({"date": iso, "balance": round(bal, 2), "inflow": inflow, "outflow": outflow})
        if alert_day is None and bal < floor:
            alert_day = iso

    return {
        "opening": round(opening, 2),
        "horizon_days": horizon_days,
        "floor": floor,
        "alert_date": alert_day,
        "days_until_floor": (
            (date.fromisoformat(alert_day) - today).days if alert_day else None
        ),
        "series": daily,
    }


def score_customer_churn(session: Session, tenant_id: int) -> list[dict]:
    today = date.today()
    customers = session.exec(
        select(Customer).where(Customer.tenant_id == tenant_id, Customer.is_active == True)  # noqa: E712
    ).all()
    out = []
    for cust in customers:
        invs = session.exec(
            select(Invoice).where(
                Invoice.tenant_id == tenant_id, Invoice.customer_id == cust.id
            )
        ).all()
        if not invs:
            out.append({"customer_id": cust.id, "name": cust.name, "risk_score": 50, "at_risk": False})
            continue
        last = max((i.issue_date or "")[:10] for i in invs)
        try:
            days_since = (today - date.fromisoformat(last)).days
        except ValueError:
            days_since = 365
        overdue = sum(1 for i in invs if i.status == "overdue")
        freq = len(invs)
        # Heuristic 0–100
        score = min(100, int(days_since / 3) + overdue * 15 - min(freq, 20))
        score = max(0, score)
        out.append({
            "customer_id": cust.id,
            "name": cust.name,
            "risk_score": score,
            "at_risk": score >= 60,
            "days_since_last_invoice": days_since,
            "overdue_count": overdue,
        })
    out.sort(key=lambda r: -r["risk_score"])
    return out


def budget_variance_projection(session: Session, tenant_id: int, threshold: float = 1.1) -> list[dict]:
    today = date.today()
    days_elapsed = max(today.day, 1)
    days_in_month = 30
    budgets = session.exec(
        select(Budget).where(
            Budget.tenant_id == tenant_id,
            Budget.fiscal_year == today.year,
            Budget.period_month == today.month,
        )
    ).all()
    results = []
    for b in budgets:
        budget_amt = float(b.amount or 0)
        # Actual spend not joined here — expose budget target; UI can enrich
        actual = 0.0
        projected = (actual / days_elapsed) * days_in_month if days_elapsed else 0
        results.append({
            "budget_id": b.id,
            "budget_name": b.label or f"{b.fiscal_year}-{b.period_month:02d}",
            "account_id": b.account_id,
            "budget": budget_amt,
            "actual_to_date": actual,
            "projected_month_total": round(projected, 2),
            "overrun": False,
            "threshold": threshold,
        })
    return results
