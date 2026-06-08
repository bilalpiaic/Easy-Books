"""Deferred revenue recognition. IFRS 15 — revenue recognised when performance
obligations are satisfied, not when cash is received."""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from models import Account, DeferredRevenueSchedule
from routers.common import SessionDep, WriteUserDep, get_or_create_account, log_audit
from services.deferred import _add_months
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction

router = APIRouter(prefix="/api/deferred-revenue", tags=["deferred-revenue"])


@router.get("")
def list_schedules(
    session: SessionDep, user: WriteUserDep,
    status: Optional[str] = None, skip: int = 0, limit: int = 50
):
    q = select(DeferredRevenueSchedule).where(
        DeferredRevenueSchedule.tenant_id == user.tenant_id
    )
    if status:
        q = q.where(DeferredRevenueSchedule.status == status)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(DeferredRevenueSchedule.next_recognition_date).offset(skip).limit(limit)).all()
    return {"total": total, "items": items}


@router.post("/run-recognition")
def run_recognition(session: SessionDep, user: WriteUserDep, recognition_date: str):
    """Run recognition for all active schedules due on or before recognition_date."""
    schedules = session.exec(
        select(DeferredRevenueSchedule).where(
            DeferredRevenueSchedule.tenant_id == user.tenant_id,
            DeferredRevenueSchedule.status == "active",
            DeferredRevenueSchedule.next_recognition_date <= recognition_date,
        )
    ).all()

    posted = []
    for sched in schedules:
        remaining = D(sched.total_amount) - D(sched.recognised_amount)
        if remaining <= ZERO:
            sched.status = "completed"
            session.add(sched)
            continue

        # Monthly charge = total / number of periods
        from dateutil.relativedelta import relativedelta
        start = date.fromisoformat(sched.start_date)
        end = date.fromisoformat(sched.end_date)
        months = max(1, (end.year - start.year) * 12 + (end.month - start.month))
        charge = min(remaining, money(D(sched.total_amount) / months))
        if charge <= ZERO:
            continue

        txn = post_transaction(
            session,
            user,
            date=recognition_date,
            description=f"Deferred Revenue Recognition — Schedule {sched.id}",
            entries=[
                EntryInput(account_id=sched.deferred_revenue_account_id, debit=charge),
                EntryInput(account_id=sched.revenue_account_id, credit=charge),
            ],
            audit_entity_type="deferred_revenue",
            audit_detail={"schedule_id": sched.id, "charge": str(charge)},
        )

        sched.recognised_amount = money(D(sched.recognised_amount) + charge)
        if D(sched.recognised_amount) >= D(sched.total_amount):
            sched.status = "completed"
        else:
            sched.next_recognition_date = _add_months(recognition_date, 1)
        session.add(sched)
        log_audit(session, user, "UPDATE", "deferred_revenue", sched.id,
                  {"charge": str(charge), "jv": txn.jv_number})
        posted.append({"schedule_id": sched.id, "charge": str(charge), "jv": txn.jv_number})

    session.commit()
    return {"recognised_count": len(posted), "details": posted}
