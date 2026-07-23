"""Nightly insight scan (#124)."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import select

from models import AgentSuggestion, Invoice, Product, Tenant


async def scan_insights_task(ctx) -> dict:
    import db as _db
    from sqlmodel import Session

    created = 0
    with Session(_db.engine) as session:
        tenants = session.exec(select(Tenant)).all()
        expires = datetime.utcnow() + timedelta(days=7)
        for tenant in tenants:
            # Overdue invoices
            overdue = session.exec(
                select(Invoice).where(
                    Invoice.tenant_id == tenant.id,
                    Invoice.status == "overdue",
                )
            ).all()
            if overdue:
                session.add(AgentSuggestion(
                    tenant_id=tenant.id,
                    kind="overdue_invoices",
                    title=f"{len(overdue)} overdue invoice(s)",
                    body="Send reminders or follow up with customers.",
                    action_href="/aging",
                    action_label="View aging",
                    expires_at=expires,
                ))
                created += 1
            # Low stock
            low = session.exec(
                select(Product).where(
                    Product.tenant_id == tenant.id,
                    Product.reorder_level != None,  # noqa: E711
                )
            ).all()
            low = [p for p in low if (p.stock_qty or 0) < (p.reorder_level or 0)]
            if low:
                session.add(AgentSuggestion(
                    tenant_id=tenant.id,
                    kind="stock_low",
                    title=f"{len(low)} product(s) below reorder level",
                    body="Create a purchase order for low-stock items.",
                    action_href="/products",
                    action_label="View products",
                    expires_at=expires,
                ))
                created += 1
        session.commit()
    return {"created": created}
