"""Company settings (single key/value table per tenant)."""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import select

from models import Settings

from .common import CurrentUserDep, SessionDep, WriteUserDep

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    tax_id: Optional[str] = None
    fiscal_year_start: Optional[str] = None
    currency: Optional[str] = None
    email_notifications: Optional[str] = None
    invoice_prefix: Optional[str] = None
    bill_prefix: Optional[str] = None
    financial_statement_date: Optional[str] = None


@router.get("")
def get_settings(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(select(Settings).where(Settings.tenant_id == user.tenant_id)).all()
    return {s.key: s.value for s in rows}


@router.patch("")
def update_settings(session: SessionDep, user: WriteUserDep, body: SettingsUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    for key, value in updates.items():
        row = session.exec(
            select(Settings).where(Settings.tenant_id == user.tenant_id, Settings.key == key)
        ).first()
        if row:
            row.value = value
        else:
            row = Settings(key=key, value=value, tenant_id=user.tenant_id)
        session.add(row)
    session.commit()
    return {"success": True}
