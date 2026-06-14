"""Tax code catalog CRUD.

Tax codes decouple the rate/account from the document. An invoice/bill cites
a TaxCode by id; the rate at posting time comes from the catalog so a tenant
can change its standard rate without touching historical documents.
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Account, TaxCode

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/tax-codes", tags=["tax-codes"], dependencies=[perm_dep("tax_codes")])


class TaxCodeCreate(BaseModel):
    code: str
    name: str
    rate: Decimal
    type: str               # output | input
    gl_account_id: int


class TaxCodeUpdate(BaseModel):
    name: Optional[str] = None
    rate: Optional[Decimal] = None
    is_active: Optional[bool] = None


@router.get("")
def list_tax_codes(
    session: SessionDep, user: CurrentUserDep,
    skip: int = 0, limit: int = 100,
):
    q = select(TaxCode).where(TaxCode.tenant_id == user.tenant_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(TaxCode.code).offset(skip).limit(limit)).all()
    return {"total": total, "items": items}


@router.post("", status_code=201)
def create_tax_code(
    session: SessionDep, user: WriteUserDep, body: TaxCodeCreate
):
    if body.type not in ("output", "input"):
        raise HTTPException(400, "type must be 'output' or 'input'")
    # Verify GL account belongs to tenant
    acc = session.exec(
        select(Account).where(
            Account.id == body.gl_account_id, Account.tenant_id == user.tenant_id
        )
    ).first()
    if not acc:
        raise HTTPException(400, "gl_account_id not found for tenant")
    tc = TaxCode(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(tc)
    session.flush()
    log_audit(session, user, "CREATE", "tax_code", tc.id, {"code": tc.code})
    session.commit()
    session.refresh(tc)
    return tc


@router.put("/{tax_code_id}")
def update_tax_code(
    session: SessionDep, user: WriteUserDep,
    tax_code_id: int, body: TaxCodeUpdate,
):
    tc = session.exec(
        select(TaxCode).where(
            TaxCode.id == tax_code_id, TaxCode.tenant_id == user.tenant_id
        )
    ).first()
    if not tc:
        raise HTTPException(404, "Tax code not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(tc, k, v)
    session.add(tc)
    log_audit(session, user, "UPDATE", "tax_code", tc.id, {"code": tc.code})
    session.commit()
    session.refresh(tc)
    return tc
