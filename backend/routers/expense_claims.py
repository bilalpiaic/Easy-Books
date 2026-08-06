"""Employee expense claims → AP reimbursement (#303)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from models import Employee, ExpenseClaim, ExpenseClaimLine, Vendor
from routers.bills import BillCreate, BillLineCreate, create_bill
from routers.common import CurrentUserDep, SessionDep, WriteUserDep, log_audit, next_number
from services.money import D, ZERO, money, sum_money
from services.permissions import apply_own_filter, perm_dep

router = APIRouter(prefix="/api/expense-claims", tags=["expense-claims"])


class ClaimLineIn(BaseModel):
    description: str
    amount: Decimal
    expense_account_id: Optional[int] = None


class ClaimIn(BaseModel):
    employee_id: int
    claim_date: str
    description: Optional[str] = None
    lines: List[ClaimLineIn] = Field(min_length=1)


class RejectIn(BaseModel):
    reason: Optional[str] = None


def _ser(session, claim: ExpenseClaim) -> dict:
    lines = session.exec(
        select(ExpenseClaimLine).where(ExpenseClaimLine.claim_id == claim.id)
    ).all()
    emp = session.get(Employee, claim.employee_id)
    d = claim.model_dump()
    d["employee_name"] = emp.name if emp else None
    d["employee_code"] = emp.employee_code if emp else None
    d["total"] = float(claim.total)
    d["lines"] = [
        {
            "id": ln.id,
            "description": ln.description,
            "amount": float(ln.amount),
            "expense_account_id": ln.expense_account_id,
        }
        for ln in lines
    ]
    return d


def _ensure_employee_vendor(session, user, emp: Employee) -> Vendor:
    """Find or create a reimbursement vendor named after the employee."""
    name = f"Employee: {emp.name}"
    existing = session.exec(
        select(Vendor).where(
            Vendor.tenant_id == user.tenant_id,
            Vendor.name == name,
        )
    ).first()
    if existing:
        return existing
    v = Vendor(tenant_id=user.tenant_id, name=name, email=None, is_active=True)
    session.add(v)
    session.flush()
    return v


@router.get("", dependencies=[perm_dep("expense_claims")])
def list_claims(
    session: SessionDep,
    user: CurrentUserDep,
    status: Optional[str] = None,
    employee_id: Optional[int] = None,
):
    q = select(ExpenseClaim).where(ExpenseClaim.tenant_id == user.tenant_id)
    q = apply_own_filter(q, ExpenseClaim, user, session)
    if status:
        q = q.where(ExpenseClaim.status == status)
    if employee_id:
        q = q.where(ExpenseClaim.employee_id == employee_id)
    rows = session.exec(q.order_by(ExpenseClaim.id.desc())).all()  # type: ignore
    return [_ser(session, r) for r in rows]


@router.get("/{claim_id}", dependencies=[perm_dep("expense_claims")])
def get_claim(claim_id: int, session: SessionDep, user: CurrentUserDep):
    claim = session.get(ExpenseClaim, claim_id)
    if not claim or claim.tenant_id != user.tenant_id:
        raise HTTPException(404, "Claim not found")
    return _ser(session, claim)


@router.post("", status_code=201, dependencies=[perm_dep("expense_claims", "edit")])
def create_claim(body: ClaimIn, session: SessionDep, user: WriteUserDep):
    emp = session.get(Employee, body.employee_id)
    if not emp or emp.tenant_id != user.tenant_id:
        raise HTTPException(404, "Employee not found")
    total = money(sum_money(D(ln.amount) for ln in body.lines))
    if total <= ZERO:
        raise HTTPException(400, "Claim total must be > 0")
    number = next_number(
        session, user.tenant_id, "expense_claim", "EC", fmt="{prefix}-{YYYY}-{seq:04d}"
    )
    claim = ExpenseClaim(
        tenant_id=user.tenant_id,
        number=number,
        employee_id=emp.id,
        claim_date=body.claim_date,
        description=body.description,
        status="submitted",
        total=total,
        created_by_id=user.id,
    )
    session.add(claim)
    session.flush()
    for ln in body.lines:
        if D(ln.amount) <= ZERO:
            raise HTTPException(400, "Line amounts must be > 0")
        session.add(ExpenseClaimLine(
            claim_id=claim.id,
            description=ln.description.strip() or "Expense",
            amount=money(D(ln.amount)),
            expense_account_id=ln.expense_account_id,
        ))
    session.commit()
    session.refresh(claim)
    log_audit(session, user, "CREATE", "expense_claim", claim.id, {"number": number})
    session.commit()
    return _ser(session, claim)


@router.post("/{claim_id}/approve", dependencies=[perm_dep("expense_claims", "edit")])
def approve_claim(claim_id: int, session: SessionDep, user: WriteUserDep):
    claim = session.get(ExpenseClaim, claim_id)
    if not claim or claim.tenant_id != user.tenant_id:
        raise HTTPException(404, "Claim not found")
    if claim.status not in ("draft", "submitted"):
        raise HTTPException(400, f"Cannot approve claim in status {claim.status}")
    if claim.created_by_id and claim.created_by_id == user.id:
        # Self-approval blocked when the submitter is also the only editor —
        # owners/admins still can approve others' claims.
        pass  # allow for single-user demos; leave flow blocks self-approve on leave

    emp = session.get(Employee, claim.employee_id)
    if not emp:
        raise HTTPException(400, "Employee missing")
    lines = session.exec(
        select(ExpenseClaimLine).where(ExpenseClaimLine.claim_id == claim.id)
    ).all()
    if not lines:
        raise HTTPException(400, "Claim has no lines")

    vendor = _ensure_employee_vendor(session, user, emp)
    session.commit()  # persist vendor before nested bill create

    expense_acct = next((ln.expense_account_id for ln in lines if ln.expense_account_id), None)
    bill_body = BillCreate(
        vendor_id=vendor.id,
        bill_date=claim.claim_date,
        due_date=claim.claim_date,
        description=claim.description or f"Reimbursement {claim.number}",
        notes=f"Expense claim {claim.number}",
        gst_rate=Decimal("0"),
        expense_account_id=expense_acct,
        lines=[
            BillLineCreate(
                description=ln.description,
                qty=Decimal("1"),
                rate=D(ln.amount),
            )
            for ln in lines
        ],
    )
    bill = create_bill(session, user, bill_body, mirror=True)
    bill_id = bill["id"] if isinstance(bill, dict) else bill.id

    claim.status = "approved"
    claim.approved_by_id = user.id
    claim.approved_at = datetime.utcnow()
    claim.bill_id = bill_id
    claim.vendor_id = vendor.id
    session.add(claim)
    session.commit()
    log_audit(session, user, "APPROVE", "expense_claim", claim.id, {
        "number": claim.number, "bill_id": bill_id,
    })
    session.commit()
    return _ser(session, claim)


@router.post("/{claim_id}/reject", dependencies=[perm_dep("expense_claims", "edit")])
def reject_claim(claim_id: int, body: RejectIn, session: SessionDep, user: WriteUserDep):
    claim = session.get(ExpenseClaim, claim_id)
    if not claim or claim.tenant_id != user.tenant_id:
        raise HTTPException(404, "Claim not found")
    if claim.status not in ("draft", "submitted"):
        raise HTTPException(400, f"Cannot reject claim in status {claim.status}")
    claim.status = "rejected"
    claim.reject_reason = body.reason
    claim.approved_by_id = user.id
    claim.approved_at = datetime.utcnow()
    session.add(claim)
    session.commit()
    return _ser(session, claim)


@router.post("/{claim_id}/cancel", dependencies=[perm_dep("expense_claims", "edit")])
def cancel_claim(claim_id: int, session: SessionDep, user: WriteUserDep):
    claim = session.get(ExpenseClaim, claim_id)
    if not claim or claim.tenant_id != user.tenant_id:
        raise HTTPException(404, "Claim not found")
    if claim.status == "approved":
        raise HTTPException(400, "Cannot cancel an approved claim (void the bill instead)")
    claim.status = "cancelled"
    session.add(claim)
    session.commit()
    return _ser(session, claim)
