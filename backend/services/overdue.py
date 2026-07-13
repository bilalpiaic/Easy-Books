"""Daily overdue automation: status sweep + aging reminder emails.

Both entry points are cross-tenant (they run from the scheduler in main.py,
not from a request) and are safe to call repeatedly:

- sweep_overdue: one SQL UPDATE flips past-due open/sent invoices to
  'overdue'. Narrower than routers/invoices._auto_overdue (kept for
  freshness between sweeps): draft, void, paid and partial are never touched.
- send_overdue_reminders: for each tenant with email_notifications=true,
  one email per customer listing their overdue invoices with balance due.
  Throttled per tenant via the Settings KV — overdue_reminder_interval_days
  (default 7) against overdue_last_reminder_date — so a daily scheduler tick
  doesn't spam customers daily.
"""
import html
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, select

from models import Customer, Invoice, PaymentAllocation, Settings
from services.email import send_email
from services.money import D

DEFAULT_REMINDER_INTERVAL_DAYS = 7


def sweep_overdue(session: Session) -> int:
    """Mark every past-due open/sent invoice overdue (all tenants)."""
    today = date.today().isoformat()
    result = session.execute(
        Invoice.__table__.update()
        .where(
            Invoice.__table__.c.status.in_(["open", "sent"]),
            Invoice.__table__.c.due_date < today,
        )
        .values(status="overdue")
    )
    session.commit()
    return result.rowcount or 0


def _tenant_settings(session: Session, tenant_id: int) -> dict[str, str]:
    rows = session.exec(select(Settings).where(Settings.tenant_id == tenant_id)).all()
    return {s.key: s.value for s in rows}


def _set_setting(session: Session, tenant_id: int, key: str, value: str) -> None:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    if row:
        row.value = value
        session.add(row)
    else:
        session.add(Settings(tenant_id=tenant_id, key=key, value=value))


def _balance_due(session: Session, inv: Invoice) -> Decimal:
    allocated = session.exec(
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
        .where(PaymentAllocation.invoice_id == inv.id)
    ).one()
    return D(inv.total) - D(allocated)


def _reminder_body(company: str, customer: Customer, invoices: list[dict]) -> str:
    # Escape every interpolated value — tenant/customer-controlled strings in
    # an HTML email body (same guard as _send_invoice_notification).
    rows = "".join(
        f"<tr><td>{html.escape(i['number'])}</td>"
        f"<td>{html.escape(i['due_date'])}</td>"
        f"<td style='text-align:right'>{html.escape(i['currency'])} {i['balance']:,.2f}</td></tr>"
        for i in invoices
    )
    return (
        f"<p>Dear {html.escape(customer.name or '')},</p>"
        f"<p>The following invoice(s) from {html.escape(company)} are past due:</p>"
        f"<table cellpadding='6' border='1' style='border-collapse:collapse'>"
        f"<tr><th>Invoice</th><th>Due Date</th><th style='text-align:right'>Balance Due</th></tr>"
        f"{rows}</table>"
        f"<p>Please arrange payment at your earliest convenience. If you have "
        f"already paid, kindly disregard this notice.</p>"
        f"<p><em>{html.escape(company)}</em></p>"
    )


def send_overdue_reminders(session: Session, *, today: date | None = None) -> int:
    """Send aging reminders for every opted-in tenant. Returns emails sent."""
    today = today or date.today()
    sent = 0

    tenant_ids = session.exec(
        select(Settings.tenant_id).where(
            Settings.key == "email_notifications", Settings.value == "true"
        ).distinct()
    ).all()

    for tenant_id in tenant_ids:
        settings = _tenant_settings(session, tenant_id)

        try:
            interval = int(settings.get(
                "overdue_reminder_interval_days", str(DEFAULT_REMINDER_INTERVAL_DAYS)
            ))
        except ValueError:
            interval = DEFAULT_REMINDER_INTERVAL_DAYS
        last = settings.get("overdue_last_reminder_date")
        if last:
            try:
                if (today - date.fromisoformat(last)).days < interval:
                    continue
            except ValueError:
                pass  # unparseable marker — treat as never run

        overdue = session.exec(
            select(Invoice).where(
                Invoice.tenant_id == tenant_id,
                Invoice.status == "overdue",
                Invoice.customer_id.is_not(None),
            ).order_by(Invoice.due_date)
        ).all()

        by_customer: dict[int, list[dict]] = {}
        for inv in overdue:
            balance = _balance_due(session, inv)
            if balance <= 0:
                continue
            by_customer.setdefault(inv.customer_id, []).append({
                "number": inv.number, "due_date": inv.due_date or "",
                "currency": inv.currency or "", "balance": float(balance),
            })

        company = settings.get("company_name", "Your supplier")
        for customer_id, invoices in by_customer.items():
            customer = session.get(Customer, customer_id)
            if not customer or not customer.email:
                continue
            send_email(
                to=customer.email,
                subject=f"Payment reminder — {len(invoices)} overdue invoice(s) from {company}",
                html_body=_reminder_body(company, customer, invoices),
            )
            sent += 1

        # Mark the run even when nothing was sent, so the tenant isn't
        # re-scanned every tick once it opted in.
        _set_setting(session, tenant_id, "overdue_last_reminder_date", today.isoformat())
        session.commit()

    return sent
