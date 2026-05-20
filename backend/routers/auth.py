"""Signup, login, and current-user endpoints."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import select

from auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    verify_password,
)
from db import seed_data
from models import Tenant, User

from .common import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/auth", tags=["auth"])


class UserSignup(BaseModel):
    email: str
    password: str
    full_name: str
    company_name: str


@router.post("/signup")
def signup(data: UserSignup, session: SessionDep):
    existing = session.exec(select(User).where(User.email == data.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    tenant = Tenant(name=data.company_name)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    seed_data(tenant.id, session=session)

    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        tenant_id=tenant.id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"success": True, "tenant_id": tenant.id}


@router.post("/login")
def login(session: SessionDep, form_data: OAuth2PasswordRequestForm = Depends()):
    user = session.exec(select(User).where(User.email == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        data={"sub": user.email, "tenant_id": user.tenant_id, "full_name": user.full_name},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def get_me(user: CurrentUserDep):
    return {"email": user.email, "full_name": user.full_name}
