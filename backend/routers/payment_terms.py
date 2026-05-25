"""Payment terms CRUD — tenant-scoped."""
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import PaymentTerm

from .common import AdminUserDep, CurrentUserDep, SessionDep, WriteUserDep, mark_onboarding_step

router = APIRouter(prefix="/api/payment-terms", tags=["payment-terms"])


class PaymentTermCreate(BaseModel):
    code: str
    name: str
    days: int


class PaymentTermUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    days: Optional[int] = None


@router.get("", response_model=List[PaymentTerm])
def list_payment_terms(session: SessionDep, user: CurrentUserDep):
    return session.exec(
        select(PaymentTerm)
        .where(PaymentTerm.tenant_id == user.tenant_id)
        .order_by(PaymentTerm.days)
    ).all()


@router.post("", response_model=PaymentTerm)
def create_payment_term(session: SessionDep, user: AdminUserDep, body: PaymentTermCreate):
    existing = session.exec(
        select(PaymentTerm).where(
            PaymentTerm.tenant_id == user.tenant_id,
            PaymentTerm.code == body.code,
        )
    ).first()
    if existing:
        raise HTTPException(400, f"Payment term with code '{body.code}' already exists")
    term = PaymentTerm(
        tenant_id=user.tenant_id,
        code=body.code.upper(),
        name=body.name,
        days=body.days,
    )
    session.add(term)
    mark_onboarding_step(session, user.tenant_id, "payment_terms")
    session.commit()
    session.refresh(term)
    return term


@router.patch("/{term_id}", response_model=PaymentTerm)
def update_payment_term(
    term_id: int, session: SessionDep, user: AdminUserDep, body: PaymentTermUpdate
):
    term = session.exec(
        select(PaymentTerm).where(
            PaymentTerm.id == term_id, PaymentTerm.tenant_id == user.tenant_id
        )
    ).first()
    if not term:
        raise HTTPException(404, "Payment term not found")
    updates = body.model_dump(exclude_none=True)
    for k, v in updates.items():
        setattr(term, k, v)
    session.add(term)
    session.commit()
    session.refresh(term)
    return term


@router.delete("/{term_id}")
def delete_payment_term(term_id: int, session: SessionDep, user: AdminUserDep):
    term = session.exec(
        select(PaymentTerm).where(
            PaymentTerm.id == term_id, PaymentTerm.tenant_id == user.tenant_id
        )
    ).first()
    if not term:
        raise HTTPException(404, "Payment term not found")
    session.delete(term)
    session.commit()
    return {"success": True}
