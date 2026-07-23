"""Recurring journal auto-post task (#115) — daily ARQ cron."""
from __future__ import annotations

from datetime import date as DateType
import json as _json


async def post_recurring_entries_task(ctx) -> dict:
    """Scan all tenants for due RecurringTemplate rows and post them."""
    import db as _db
    from sqlmodel import Session, select
    from models import RecurringTemplate, User
    from services.money import D
    from services.posting import EntryInput, post_transaction
    from routers.recurring import _advance

    today = DateType.today().isoformat()
    posted = 0
    errors: list[str] = []

    with Session(_db.engine) as session:
        due = session.exec(
            select(RecurringTemplate).where(
                RecurringTemplate.is_active == True,  # noqa: E712
                RecurringTemplate.next_run <= today,
            )
        ).all()
        for t in due:
            try:
                actor = session.exec(
                    select(User).where(User.tenant_id == t.tenant_id)
                    .order_by(User.id)  # type: ignore[arg-type]
                ).first()
                if actor is None:
                    errors.append(f"template {t.id}: no user for tenant {t.tenant_id}")
                    continue

                entries = _json.loads(t.entries_json)
                post_transaction(
                    session,
                    actor,
                    date=t.next_run,
                    description=f"Recurring: {t.name}",
                    entries=[
                        EntryInput(
                            account_id=e["account_id"],
                            debit=D(e.get("debit", 0)),
                            credit=D(e.get("credit", 0)),
                        )
                        for e in entries
                    ],
                    audit_entity_type="recurring",
                    audit_detail={"template_id": t.id, "name": t.name, "source": "arq"},
                )
                next_d = _advance(DateType.fromisoformat(t.next_run), t.frequency)
                t.last_run = t.next_run
                t.next_run = next_d.isoformat()
                session.add(t)
                posted += 1
            except Exception as exc:
                errors.append(f"template {t.id}: {type(exc).__name__}: {exc}")
        session.commit()

    return {"posted": posted, "errors": errors}
