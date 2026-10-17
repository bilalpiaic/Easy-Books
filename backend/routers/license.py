"""Standalone install license — status + activate (allowed while trial-locked)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from models import User
from routers.common import SessionDep
from services.standalone_license import (
    LicenseError,
    activate_token,
    emails_from_users,
    license_status,
)

router = APIRouter(prefix="/api/license", tags=["license"])


class ActivateIn(BaseModel):
    token: str = Field(min_length=8, max_length=4000)
    plan: str = Field(min_length=3, max_length=32)


@router.get("/status")
def get_license_status():
    return license_status()


@router.post("/activate")
def activate_license(body: ActivateIn, session: SessionDep):
    users = session.exec(select(User)).all()
    try:
        status = activate_token(
            body.token,
            emails=emails_from_users(list(users)),
            selected_plan=body.plan,
        )
    except LicenseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    from services.entitlements import apply_licensed_commercial

    commercial = apply_licensed_commercial(session)
    session.commit()
    return {**status, "commercial": commercial}
