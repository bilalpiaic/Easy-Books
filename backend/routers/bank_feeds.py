"""Plaid bank feeds (#121) — graceful 503 when PLAID_* unset."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import CategorizationRule, PlaidConnection
from services.crypto_secrets import decrypt_secret, encrypt_secret
from .common import CurrentUserDep, SessionDep, WriteUserDep

router = APIRouter(prefix="/api/banking/plaid", tags=["bank-feeds"])

PLAID_BASE = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}


def _plaid_configured() -> bool:
    return bool(os.environ.get("PLAID_CLIENT_ID") and os.environ.get("PLAID_SECRET"))


def _plaid_url(path: str) -> str:
    env = os.environ.get("PLAID_ENV", "sandbox")
    return f"{PLAID_BASE.get(env, PLAID_BASE['sandbox'])}{path}"


def _require_plaid():
    if not _plaid_configured():
        raise HTTPException(503, "Plaid is not configured (set PLAID_CLIENT_ID / PLAID_SECRET)")


@router.get("/connections")
def list_connections(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(PlaidConnection).where(
            PlaidConnection.tenant_id == user.tenant_id,
            PlaidConnection.is_active == True,  # noqa: E712
        )
    ).all()
    return [
        {
            "id": r.id, "institution_name": r.institution_name,
            "item_id": r.item_id, "last_sync": r.last_sync,
            "bank_account_id": r.bank_account_id,
        }
        for r in rows
    ]


@router.post("/link-token")
def create_link_token(session: SessionDep, user: WriteUserDep):
    _require_plaid()
    payload = {
        "client_id": os.environ["PLAID_CLIENT_ID"],
        "secret": os.environ["PLAID_SECRET"],
        "user": {"client_user_id": f"tenant-{user.tenant_id}-user-{user.id}"},
        "client_name": "Easy-Books",
        "products": ["transactions"],
        "country_codes": ["US"],
        "language": "en",
    }
    r = httpx.post(_plaid_url("/link/token/create"), json=payload, timeout=20.0)
    if r.status_code >= 400:
        raise HTTPException(502, f"Plaid error: {r.text[:300]}")
    return r.json()


class ExchangeBody(BaseModel):
    public_token: str
    institution_name: str = ""
    bank_account_id: Optional[int] = None


@router.post("/exchange")
def exchange_token(body: ExchangeBody, session: SessionDep, user: WriteUserDep):
    _require_plaid()
    payload = {
        "client_id": os.environ["PLAID_CLIENT_ID"],
        "secret": os.environ["PLAID_SECRET"],
        "public_token": body.public_token,
    }
    r = httpx.post(_plaid_url("/item/public_token/exchange"), json=payload, timeout=20.0)
    if r.status_code >= 400:
        raise HTTPException(502, f"Plaid error: {r.text[:300]}")
    data = r.json()
    conn = PlaidConnection(
        tenant_id=user.tenant_id,
        bank_account_id=body.bank_account_id,
        access_token=encrypt_secret(data["access_token"]),
        item_id=data["item_id"],
        institution_name=body.institution_name or "Bank",
    )
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return {"id": conn.id, "item_id": conn.item_id}


@router.post("/sync/{connection_id}")
def sync_connection(connection_id: int, session: SessionDep, user: WriteUserDep):
    _require_plaid()
    conn = session.get(PlaidConnection, connection_id)
    if not conn or conn.tenant_id != user.tenant_id:
        raise HTTPException(404, "Connection not found")
    # Minimal sync stub — records last_sync; full transaction upsert lands with #115 queue
    access = decrypt_secret(conn.access_token)
    payload = {
        "client_id": os.environ["PLAID_CLIENT_ID"],
        "secret": os.environ["PLAID_SECRET"],
        "access_token": access,
    }
    r = httpx.post(_plaid_url("/transactions/sync"), json=payload, timeout=30.0)
    added = 0
    if r.status_code < 400:
        body = r.json()
        added = len(body.get("added") or [])
        # Auto-categorize descriptions against rules
        rules = session.exec(
            select(CategorizationRule).where(
                CategorizationRule.tenant_id == user.tenant_id,
                CategorizationRule.is_active == True,  # noqa: E712
            )
        ).all()
        for txn in body.get("added") or []:
            desc = (txn.get("name") or txn.get("merchant_name") or "").lower()
            for rule in rules:
                if rule.pattern.lower() in desc:
                    break  # matched — StatementLine write deferred to bank_imports shape
    conn.last_sync = datetime.utcnow()
    session.add(conn)
    session.commit()
    return {"ok": True, "added": added, "last_sync": conn.last_sync}


@router.delete("/connections/{connection_id}", status_code=204)
def disconnect(connection_id: int, session: SessionDep, user: WriteUserDep):
    conn = session.get(PlaidConnection, connection_id)
    if not conn or conn.tenant_id != user.tenant_id:
        raise HTTPException(404)
    conn.is_active = False
    session.add(conn)
    session.commit()


@router.post("/webhook")
async def plaid_webhook():
    return {"received": True}


class RuleIn(BaseModel):
    pattern: str
    account_id: int
    is_active: bool = True


@router.get("/rules")
def list_rules(session: SessionDep, user: CurrentUserDep):
    return [
        r.model_dump()
        for r in session.exec(
            select(CategorizationRule).where(CategorizationRule.tenant_id == user.tenant_id)
        ).all()
    ]


@router.post("/rules", status_code=201)
def create_rule(body: RuleIn, session: SessionDep, user: WriteUserDep):
    row = CategorizationRule(tenant_id=user.tenant_id, **body.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return row.model_dump()
