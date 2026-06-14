"""Sales staff commission plans and ledger (Issue #71)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from models import (
    Account, CommissionLedger, CommissionPlan, Invoice, PaymentReceived, User,
)
from routers.common import CurrentUserDep, SessionDep
from services.permissions import perm_dep
from services.posting import EntryInput, post_transaction

router = APIRouter(
    prefix="/api/commissions",
    tags=["commissions"],
    dependencies=[perm_dep("commissions")],
)


# ── Schemas ──────────────────────────────────────────────────────────────────

class PlanCreate(BaseModel):
    user_id: int
    rate: Decimal
    sales_target: Optional[Decimal] = None
    recovery_target: Optional[Decimal] = None
    target_bonus: Optional[Decimal] = None
    effective_from: str
    effective_to: Optional[str] = None


class PlanUpdate(BaseModel):
    rate: Optional[Decimal] = None
    sales_target: Optional[Decimal] = None
    recovery_target: Optional[Decimal] = None
    target_bonus: Optional[Decimal] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    active: Optional[bool] = None


class ComputeRequest(BaseModel):
    period: str                          # YYYY-MM
    user_ids: Optional[list[int]] = None # None = all users with active plans


class PostRequest(BaseModel):
    expense_account_id: int    # Dr Commission Expense
    payable_account_id: int    # Cr Commissions Payable / Accrued Salary
    date: str                  # posting date (YYYY-MM-DD)


# ── Plans CRUD ────────────────────────────────────────────────────────────────

@router.get("/plans")
def list_plans(user: CurrentUserDep, session: SessionDep):
    plans = session.exec(
        select(CommissionPlan, User)
        .join(User, CommissionPlan.user_id == User.id)  # type: ignore[arg-type]
        .where(CommissionPlan.tenant_id == user.tenant_id)
        .order_by(CommissionPlan.effective_from.desc())  # type: ignore[attr-defined]
    ).all()
    return [
        {
            "id": p.id,
            "user_id": p.user_id,
            "user_name": u.full_name or u.email,
            "rate": float(p.rate),
            "sales_target": float(p.sales_target) if p.sales_target else None,
            "recovery_target": float(p.recovery_target) if p.recovery_target else None,
            "target_bonus": float(p.target_bonus) if p.target_bonus else None,
            "effective_from": p.effective_from,
            "effective_to": p.effective_to,
            "active": p.active,
        }
        for p, u in plans
    ]


@router.post("/plans", dependencies=[perm_dep("commissions", "edit")])
def create_plan(body: PlanCreate, user: CurrentUserDep, session: SessionDep):
    target_user = session.get(User, body.user_id)
    if not target_user or target_user.tenant_id != user.tenant_id:
        raise HTTPException(404, "User not found")
    plan = CommissionPlan(tenant_id=user.tenant_id, **body.model_dump())
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return {"id": plan.id}


@router.put("/plans/{plan_id}", dependencies=[perm_dep("commissions", "edit")])
def update_plan(plan_id: int, body: PlanUpdate, user: CurrentUserDep, session: SessionDep):
    plan = session.get(CommissionPlan, plan_id)
    if not plan or plan.tenant_id != user.tenant_id:
        raise HTTPException(404, "Plan not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(plan, k, v)
    session.add(plan)
    session.commit()
    return {"ok": True}


@router.delete("/plans/{plan_id}", dependencies=[perm_dep("commissions", "edit")])
def deactivate_plan(plan_id: int, user: CurrentUserDep, session: SessionDep):
    plan = session.get(CommissionPlan, plan_id)
    if not plan or plan.tenant_id != user.tenant_id:
        raise HTTPException(404, "Plan not found")
    plan.active = False
    session.add(plan)
    session.commit()
    return {"ok": True}


# ── Sales staff list ──────────────────────────────────────────────────────────

@router.get("/staff")
def list_staff(user: CurrentUserDep, session: SessionDep):
    """All users in the tenant eligible to be assigned as sales persons."""
    users = session.exec(
        select(User).where(User.tenant_id == user.tenant_id)
    ).all()
    return [{"id": u.id, "name": u.full_name or u.email, "email": u.email} for u in users]


# ── Commission Ledger ─────────────────────────────────────────────────────────

@router.get("/ledger")
def list_ledger(
    user: CurrentUserDep,
    session: SessionDep,
    period: Optional[str] = None,
    user_id: Optional[int] = None,
):
    q = select(CommissionLedger, User).join(
        User, CommissionLedger.user_id == User.id  # type: ignore[arg-type]
    ).where(CommissionLedger.tenant_id == user.tenant_id)
    if period:
        q = q.where(CommissionLedger.period == period)
    if user_id:
        q = q.where(CommissionLedger.user_id == user_id)
    rows = session.exec(q.order_by(CommissionLedger.period.desc())).all()  # type: ignore[attr-defined]
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "user_name": u.full_name or u.email,
            "period": r.period,
            "total_invoiced": float(r.total_invoiced),
            "total_recovered": float(r.total_recovered),
            "rate": float(r.rate),
            "commission_amount": float(r.commission_amount),
            "bonus_amount": float(r.bonus_amount),
            "total_payable": float(r.total_payable),
            "status": r.status,
            "transaction_id": r.transaction_id,
        }
        for r, u in rows
    ]


@router.post("/compute", dependencies=[perm_dep("commissions", "edit")])
def compute_commissions(body: ComputeRequest, user: CurrentUserDep, session: SessionDep):
    """Compute (or re-compute) commission for a period. Only drafts are re-computed."""
    period = body.period  # YYYY-MM
    period_start = period + "-01"
    # last day: find next month first day then subtract one day
    year, month = int(period[:4]), int(period[5:7])
    if month == 12:
        period_end = f"{year + 1}-01-01"
    else:
        period_end = f"{year}-{month + 1:02d}-01"

    # Fetch active plans for this tenant in this period
    plan_q = select(CommissionPlan).where(
        CommissionPlan.tenant_id == user.tenant_id,
        CommissionPlan.active == True,  # noqa: E712
        CommissionPlan.effective_from <= period_end,
    )
    # Filter by optional user list
    if body.user_ids:
        plan_q = plan_q.where(CommissionPlan.user_id.in_(body.user_ids))  # type: ignore[attr-defined]
    plans = session.exec(plan_q).all()

    created = 0
    updated = 0
    for plan in plans:
        # Skip if plan expired before period start
        if plan.effective_to and plan.effective_to < period_start:
            continue

        uid = plan.user_id

        # Invoiced in period (by assigned_to_id)
        invoiced_rows = session.exec(
            select(Invoice.total).where(  # type: ignore[arg-type]
                Invoice.tenant_id == user.tenant_id,
                Invoice.assigned_to_id == uid,
                Invoice.issue_date >= period_start,
                Invoice.issue_date < period_end,
                Invoice.status != "cancelled",
            )
        ).all()
        total_invoiced = sum(invoiced_rows) or Decimal("0")

        # Recovered in period: payments received on invoices assigned to this user
        recovered_rows = session.exec(
            select(PaymentReceived.amount).join(  # type: ignore[arg-type]
                Invoice, PaymentReceived.invoice_id == Invoice.id
            ).where(
                PaymentReceived.tenant_id == user.tenant_id,
                Invoice.assigned_to_id == uid,
                PaymentReceived.payment_date >= period_start,
                PaymentReceived.payment_date < period_end,
            )
        ).all()
        total_recovered = sum(recovered_rows) or Decimal("0")

        rate = plan.rate
        commission = (total_recovered * rate / Decimal("100")).quantize(Decimal("0.01"))

        # Bonus: awarded if BOTH targets are met (when configured)
        bonus = Decimal("0")
        if plan.target_bonus:
            sales_ok = (not plan.sales_target) or (total_invoiced >= plan.sales_target)
            recovery_ok = (not plan.recovery_target) or (total_recovered >= plan.recovery_target)
            if sales_ok and recovery_ok:
                bonus = plan.target_bonus

        total_payable = commission + bonus

        # Upsert: only update draft entries, never overwrite approved/posted
        existing = session.exec(
            select(CommissionLedger).where(
                CommissionLedger.tenant_id == user.tenant_id,
                CommissionLedger.user_id == uid,
                CommissionLedger.period == period,
            )
        ).first()

        if existing:
            if existing.status != "draft":
                continue   # don't overwrite approved/posted
            existing.total_invoiced = total_invoiced
            existing.total_recovered = total_recovered
            existing.rate = rate
            existing.commission_amount = commission
            existing.bonus_amount = bonus
            existing.total_payable = total_payable
            session.add(existing)
            updated += 1
        else:
            entry = CommissionLedger(
                tenant_id=user.tenant_id,
                user_id=uid,
                period=period,
                total_invoiced=total_invoiced,
                total_recovered=total_recovered,
                rate=rate,
                commission_amount=commission,
                bonus_amount=bonus,
                total_payable=total_payable,
                status="draft",
            )
            session.add(entry)
            created += 1

    session.commit()
    return {"created": created, "updated": updated, "period": period}


@router.post("/ledger/{entry_id}/approve", dependencies=[perm_dep("commissions", "edit")])
def approve_entry(entry_id: int, user: CurrentUserDep, session: SessionDep):
    entry = session.get(CommissionLedger, entry_id)
    if not entry or entry.tenant_id != user.tenant_id:
        raise HTTPException(404, "Entry not found")
    if entry.status != "draft":
        raise HTTPException(400, f"Entry is already {entry.status}")
    entry.status = "approved"
    session.add(entry)
    session.commit()
    return {"ok": True}


@router.post("/ledger/{entry_id}/post", dependencies=[perm_dep("commissions", "edit")])
def post_commission_entry(
    entry_id: int,
    body: PostRequest,
    user: CurrentUserDep,
    session: SessionDep,
):
    """Post an approved commission entry to the GL as a JV (Dr Expense / Cr Payable)."""
    entry = session.get(CommissionLedger, entry_id)
    if not entry or entry.tenant_id != user.tenant_id:
        raise HTTPException(404, "Entry not found")
    if entry.status != "approved":
        raise HTTPException(400, "Entry must be approved before posting")
    if entry.transaction_id:
        raise HTTPException(400, "Entry is already posted")
    if entry.total_payable <= 0:
        raise HTTPException(400, "Total payable is zero — nothing to post")

    # Validate both accounts belong to tenant
    for acct_id in (body.expense_account_id, body.payable_account_id):
        acct = session.get(Account, acct_id)
        if not acct or acct.tenant_id != user.tenant_id:
            raise HTTPException(404, f"Account {acct_id} not found")

    staff = session.get(User, entry.user_id)
    staff_name = (staff.full_name or staff.email) if staff else f"user#{entry.user_id}"

    txn = post_transaction(
        session,
        user,
        date=body.date,
        description=f"Commission — {staff_name} — {entry.period}",
        voucher_type="JV",
        entries=[
            EntryInput(account_id=body.expense_account_id, debit=float(entry.total_payable), credit=0),
            EntryInput(account_id=body.payable_account_id, debit=0, credit=float(entry.total_payable)),
        ],
        audit_detail={"commission_ledger_id": entry_id, "period": entry.period},
    )
    entry.transaction_id = txn.id
    entry.status = "posted"
    session.add(entry)
    session.commit()
    return {"ok": True, "jv_number": txn.jv_number, "transaction_id": txn.id}
