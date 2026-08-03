"""Tax code catalog CRUD.

Tax codes decouple the rate/account from the document. An invoice/bill cites
a TaxCode by id; the rate at posting time is resolved from TaxRateHistory
as-of the document date and snapshotted onto the line (#263).
"""
from datetime import date as DateType
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Account, TaxCode, TaxRateHistory
from services.money import D, money
from services.tax_engine import ensure_initial_rate_history, set_tax_code_rate

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from services.permissions import perm_dep

router = APIRouter(prefix="/api/tax-codes", tags=["tax-codes"], dependencies=[perm_dep("tax_codes")])


class TaxCodeCreate(BaseModel):
    code: str
    name: str
    rate: Decimal
    type: str               # output | input
    gl_account_id: int
    is_reverse_charge: bool = False
    is_exempt: bool = False
    is_zero_rated: bool = False
    is_withholding: bool = False
    effective_from: Optional[str] = None  # seed history start; default 1900-01-01


class TaxCodeUpdate(BaseModel):
    name: Optional[str] = None
    rate: Optional[Decimal] = None
    is_active: Optional[bool] = None
    is_reverse_charge: Optional[bool] = None
    is_exempt: Optional[bool] = None
    is_zero_rated: Optional[bool] = None
    is_withholding: Optional[bool] = None
    effective_from: Optional[str] = None  # required semantics when rate changes: default today
    gl_account_id: Optional[int] = None


def _serialize(tc: TaxCode) -> dict:
    return {
        "id": tc.id,
        "code": tc.code,
        "name": tc.name,
        "rate": tc.rate,
        "type": tc.type,
        "gl_account_id": tc.gl_account_id,
        "is_active": tc.is_active,
        "is_reverse_charge": bool(tc.is_reverse_charge),
        "is_exempt": bool(tc.is_exempt),
        "is_zero_rated": bool(tc.is_zero_rated),
        "is_withholding": bool(tc.is_withholding),
        "tenant_id": tc.tenant_id,
    }


@router.get("")
def list_tax_codes(
    session: SessionDep, user: CurrentUserDep,
    skip: int = 0, limit: int = 100,
):
    q = select(TaxCode).where(TaxCode.tenant_id == user.tenant_id)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(TaxCode.code).offset(skip).limit(limit)).all()
    return {"total": total, "items": [_serialize(tc) for tc in items]}


@router.post("", status_code=201)
def create_tax_code(
    session: SessionDep, user: WriteUserDep, body: TaxCodeCreate
):
    if body.type not in ("output", "input"):
        raise HTTPException(400, "type must be 'output' or 'input'")
    if body.is_exempt and body.is_reverse_charge:
        raise HTTPException(400, "A code cannot be both exempt and reverse-charge")
    # Verify GL account belongs to tenant
    acc = session.exec(
        select(Account).where(
            Account.id == body.gl_account_id, Account.tenant_id == user.tenant_id
        )
    ).first()
    if not acc:
        raise HTTPException(400, "gl_account_id not found for tenant")
    data = body.model_dump(exclude={"effective_from"})
    if body.is_exempt:
        data["rate"] = money(D("0"))
    tc = TaxCode(**data, tenant_id=user.tenant_id)
    session.add(tc)
    session.flush()
    ensure_initial_rate_history(session, tc)
    log_audit(session, user, "CREATE", "tax_code", tc.id, {"code": tc.code})
    session.commit()
    session.refresh(tc)
    return _serialize(tc)


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

    payload = body.model_dump(exclude_none=True)
    effective_from = payload.pop("effective_from", None)
    new_rate = payload.pop("rate", None)

    if "gl_account_id" in payload:
        acc = session.exec(
            select(Account).where(
                Account.id == payload["gl_account_id"],
                Account.tenant_id == user.tenant_id,
            )
        ).first()
        if not acc:
            raise HTTPException(400, "gl_account_id not found for tenant")

    for k, v in payload.items():
        setattr(tc, k, v)

    rc = bool(tc.is_reverse_charge)
    ex = bool(tc.is_exempt)
    if rc and ex:
        raise HTTPException(400, "A code cannot be both exempt and reverse-charge")

    if new_rate is not None:
        if ex:
            new_rate = D("0")
        ef = effective_from or str(DateType.today())
        set_tax_code_rate(session, tc, D(new_rate), effective_from=ef)
    else:
        session.add(tc)

    log_audit(session, user, "UPDATE", "tax_code", tc.id, {"code": tc.code})
    session.commit()
    session.refresh(tc)
    return _serialize(tc)


@router.get("/{tax_code_id}/rates")
def list_rate_history(
    session: SessionDep, user: CurrentUserDep, tax_code_id: int,
):
    tc = session.exec(
        select(TaxCode).where(
            TaxCode.id == tax_code_id, TaxCode.tenant_id == user.tenant_id
        )
    ).first()
    if not tc:
        raise HTTPException(404, "Tax code not found")
    rows = session.exec(
        select(TaxRateHistory)
        .where(TaxRateHistory.tax_code_id == tc.id)
        .order_by(TaxRateHistory.effective_from.desc())
    ).all()
    return {
        "tax_code_id": tc.id,
        "items": [
            {
                "id": r.id,
                "rate": r.rate,
                "effective_from": r.effective_from,
                "effective_to": r.effective_to,
            }
            for r in rows
        ],
    }
