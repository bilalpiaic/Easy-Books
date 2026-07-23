"""Dunning rule scan (#120) — complements services/overdue.py."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlmodel import select

from models import Customer, DunningRule, Invoice, Settings
from services.email import send_email


async def run_dunning_rules_task(ctx) -> dict:
    import db as _db
    from sqlmodel import Session
    import hashlib
    import secrets as _sec
    from models import PortalToken

    sent = 0
    today = date.today()
    with Session(_db.engine) as session:
        rules = session.exec(
            select(DunningRule).where(DunningRule.is_active == True)  # noqa: E712
        ).all()
        for rule in rules:
            settings = {
                s.key: s.value
                for s in session.exec(
                    select(Settings).where(Settings.tenant_id == rule.tenant_id)
                ).all()
            }
            if settings.get("email_notifications") != "true":
                continue
            invoices = session.exec(
                select(Invoice).where(
                    Invoice.tenant_id == rule.tenant_id,
                    Invoice.status.in_(["sent", "overdue", "partial", "unpaid"]),  # type: ignore
                )
            ).all()
            for inv in invoices:
                if not inv.customer_id or not inv.due_date:
                    continue
                cust = session.get(Customer, inv.customer_id)
                if not cust or not cust.email or getattr(cust, "dunning_opt_out", False):
                    continue
                try:
                    due = date.fromisoformat(inv.due_date[:10])
                except ValueError:
                    continue
                if (today - due).days < rule.days_overdue:
                    continue
                # Mint / reuse portal link
                raw = _sec.token_urlsafe(24)
                session.add(PortalToken(
                    tenant_id=rule.tenant_id,
                    entity_type="customer",
                    entity_id=cust.id,
                    token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                    expires_at=datetime.utcnow() + timedelta(days=90),
                ))
                front = settings.get("portal_base_url") or "http://localhost:3000"
                portal_link = f"{front.rstrip('/')}/portal/{raw}"
                subject = (
                    rule.subject_template
                    .replace("{{ number }}", inv.number)
                    .replace("{{ customer_name }}", cust.name)
                    .replace("{{ amount }}", f"{float(inv.total):,.2f}")
                )
                body = (
                    rule.body_template
                    .replace("{{ number }}", inv.number)
                    .replace("{{ customer_name }}", cust.name)
                    .replace("{{ amount }}", f"{float(inv.total):,.2f}")
                    .replace("{{ due_date }}", inv.due_date)
                    .replace("{{ portal_link }}", portal_link)
                )
                send_email(cust.email, subject, f"<p>{body}</p><p><a href='{portal_link}'>Pay / view</a></p>")
                sent += 1
        session.commit()
    return {"sent": sent}
