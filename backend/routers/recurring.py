"""Recurring journal entries.

A RecurringTemplate stores the JV skeleton and a schedule. POST /run-due
materialises a transaction for every template whose next_run <= today,
then advances next_run by the frequency.
"""
import calendar
import json as _json
from datetime import date as DateType, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Account, RecurringTemplate
from services.money import D
from services.posting import EntryInput, post_transaction

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/recurring", tags=["recurring"])


class RecurringEntry(BaseModel):
    account_id: int
    debit: float = 0
    credit: float = 0


class RecurringCreate(BaseModel):
    name: str
    description: Optional[str] = None
    frequency: str           # daily | weekly | monthly | quarterly | yearly
    next_run: str            # ISO yyyy-mm-dd
    entries: List[RecurringEntry]


_FREQ_DELTAS = {
    "daily": ("days", 1),
    "weekly": ("days", 7),
    "monthly": ("months", 1),
    "quarterly": ("months", 3),
    "yearly": ("months", 12),
}


def _advance(d: DateType, frequency: str) -> DateType:
    unit, n = _FREQ_DELTAS[frequency]
    if unit == "days":
        return d + timedelta(days=n)
    # months — clamp day-of-month to last valid day of target month
    y, m = d.year, d.month + n
    while m > 12:
        m -= 12
        y += 1
    last = calendar.monthrange(y, m)[1]
    return d.replace(year=y, month=m, day=min(d.day, last))


@router.get("")
def list_recurring(session: SessionDep, user: CurrentUserDep):
    q = select(RecurringTemplate).where(RecurringTemplate.tenant_id == user.tenant_id)
    items = session.exec(q.order_by(RecurringTemplate.next_run)).all()
    return [
        {
            **t.model_dump(),
            "entries": _json.loads(t.entries_json),
        }
        for t in items
    ]


@router.post("", status_code=201)
def create_recurring(
    session: SessionDep, user: WriteUserDep, body: RecurringCreate
):
    if body.frequency not in _FREQ_DELTAS:
        raise HTTPException(400, "Invalid frequency")
    # Verify all accounts belong to tenant
    acc_ids = {e.account_id for e in body.entries}
    rows = session.exec(
        select(Account.id).where(
            Account.id.in_(acc_ids), Account.tenant_id == user.tenant_id
        )
    ).all()
    if len(set(rows)) != len(acc_ids):
        raise HTTPException(400, "One or more accounts not found for tenant")

    t = RecurringTemplate(
        tenant_id=user.tenant_id,
        name=body.name,
        description=body.description,
        frequency=body.frequency,
        next_run=body.next_run,
        entries_json=_json.dumps([e.model_dump() for e in body.entries]),
    )
    session.add(t)
    session.flush()
    log_audit(session, user, "CREATE", "recurring", t.id, {"name": t.name})
    session.commit()
    session.refresh(t)
    return t


@router.patch("/{template_id}")
def toggle_recurring(session: SessionDep, user: WriteUserDep, template_id: int, is_active: bool):
    """Activate or deactivate a recurring template."""
    t = session.exec(
        select(RecurringTemplate).where(
            RecurringTemplate.id == template_id,
            RecurringTemplate.tenant_id == user.tenant_id,
        )
    ).first()
    if not t:
        raise HTTPException(404, "Template not found")
    t.is_active = is_active
    session.add(t)
    session.commit()
    session.refresh(t)
    return {**t.model_dump(), "entries": _json.loads(t.entries_json)}


@router.delete("/{template_id}", status_code=204)
def delete_recurring(session: SessionDep, user: WriteUserDep, template_id: int):
    """Delete a recurring template."""
    t = session.exec(
        select(RecurringTemplate).where(
            RecurringTemplate.id == template_id,
            RecurringTemplate.tenant_id == user.tenant_id,
        )
    ).first()
    if not t:
        raise HTTPException(404, "Template not found")
    session.delete(t)
    session.commit()


@router.post("/run-due")
def run_due_recurring(session: SessionDep, user: WriteUserDep):
    """Materialise all templates whose next_run <= today. Returns the count
    of transactions posted. Safe to call repeatedly: each call only catches
    templates that have not yet fired for their current next_run.
    """
    today = DateType.today().isoformat()
    due = session.exec(
        select(RecurringTemplate).where(
            RecurringTemplate.tenant_id == user.tenant_id,
            RecurringTemplate.is_active == True,  # noqa: E712
            RecurringTemplate.next_run <= today,
        )
    ).all()

    posted = 0
    for t in due:
        entries = _json.loads(t.entries_json)
        post_transaction(
            session, user,
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
            audit_detail={"template_id": t.id, "name": t.name},
        )
        next_d = _advance(DateType.fromisoformat(t.next_run), t.frequency)
        t.last_run = t.next_run
        t.next_run = next_d.isoformat()
        session.add(t)
        posted += 1

    session.commit()
    return {"posted": posted}
