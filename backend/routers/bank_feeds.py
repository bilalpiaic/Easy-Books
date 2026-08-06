"""Plaid bank feeds (#121) + categorization rules (#268) + Open Banking depth (#301).

Graceful 503 when PLAID_* unset. Rules live under /api/banking/rules so they
work without Plaid credentials (CSV/OFX imports share the same rule table).

#301 adds provider-agnostic feed connections under /api/banking/feeds
(mock EU/UK-style pull today; real aggregator adapters plug into
services.bank_providers).
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from models import Account, BankAccount, CategorizationRule, PlaidConnection, StatementLine
from services.bank_rules import apply_rules_to_lines
from services.bank_sync import (
    STATUS_OK,
    connection_status_payload,
    mark_connection_error,
    mark_connection_ok,
    sync_connection,
)
from services.crypto_secrets import decrypt_secret, encrypt_secret
from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

plaid_router = APIRouter(prefix="/api/banking/plaid", tags=["bank-feeds"])
feeds_router = APIRouter(prefix="/api/banking/feeds", tags=["bank-feeds"])
rules_router = APIRouter(prefix="/api/banking/rules", tags=["bank-feeds"])

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


@plaid_router.get("/connections")
def list_connections(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(PlaidConnection).where(
            PlaidConnection.tenant_id == user.tenant_id,
            PlaidConnection.is_active == True,  # noqa: E712
        )
    ).all()
    # Enriched payload (#301) — keep legacy keys for older clients.
    return [connection_status_payload(r) for r in rows]


@plaid_router.post("/link-token")
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


@plaid_router.post("/exchange")
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


@plaid_router.post("/sync/{connection_id}")
def sync_plaid_connection(connection_id: int, session: SessionDep, user: WriteUserDep):
    conn = session.get(PlaidConnection, connection_id)
    if not conn or conn.tenant_id != user.tenant_id:
        raise HTTPException(404, "Connection not found")

    # Non-Plaid providers (mock / future OB) use the shared sync path.
    if (conn.provider or "plaid").lower() != "plaid":
        try:
            return sync_connection(session, conn)
        except ValueError as exc:
            code = str(exc)
            if code == "consent_expired":
                raise HTTPException(400, "Open Banking consent expired — reconnect the account")
            if code == "connection_missing_bank_account":
                raise HTTPException(400, "Connection has no bank_account_id")
            raise HTTPException(400, code)

    _require_plaid()
    if not conn.bank_account_id:
        raise HTTPException(
            400,
            "Plaid connection has no bank_account_id — re-link with a bank account to import statement lines",
        )
    access = decrypt_secret(conn.access_token)
    payload = {
        "client_id": os.environ["PLAID_CLIENT_ID"],
        "secret": os.environ["PLAID_SECRET"],
        "access_token": access,
    }
    try:
        r = httpx.post(_plaid_url("/transactions/sync"), json=payload, timeout=30.0)
        if r.status_code >= 400:
            mark_connection_error(conn, f"Plaid error: {r.text[:300]}")
            session.add(conn)
            session.commit()
            raise HTTPException(502, f"Plaid error: {r.text[:300]}")
        body = r.json()
        added_txns = body.get("added") or []
        from services.plaid_sync import upsert_plaid_transactions
        counts = upsert_plaid_transactions(
            session,
            tenant_id=user.tenant_id,
            bank_account_id=conn.bank_account_id,
            transactions=added_txns,
        )
        lines = list(session.exec(
            select(StatementLine).where(
                StatementLine.tenant_id == user.tenant_id,
                StatementLine.is_matched == False,  # noqa: E712
                StatementLine.categorized_account_id == None,  # noqa: E711
            )
        ).all())
        categorized = apply_rules_to_lines(session, tenant_id=user.tenant_id, lines=lines)
        mark_connection_ok(conn)
        session.add(conn)
        session.commit()
        return {
            "ok": True,
            "provider": "plaid",
            "added": len(added_txns),
            "imported": counts["imported"],
            "skipped": counts["skipped"],
            "categorized": categorized,
            "last_sync": conn.last_sync,
            "sync_status": conn.sync_status or STATUS_OK,
        }
    except HTTPException:
        raise
    except Exception as exc:
        mark_connection_error(conn, f"{type(exc).__name__}: {exc}")
        session.add(conn)
        session.commit()
        raise HTTPException(502, f"Plaid sync failed: {exc}") from exc


@plaid_router.delete("/connections/{connection_id}", status_code=204)
def disconnect(connection_id: int, session: SessionDep, user: WriteUserDep):
    conn = session.get(PlaidConnection, connection_id)
    if not conn or conn.tenant_id != user.tenant_id:
        raise HTTPException(404)
    conn.is_active = False
    session.add(conn)
    session.commit()


@plaid_router.post("/webhook")
async def plaid_webhook():
    return {"received": True}


# ── Provider-agnostic feeds (#301) ────────────────────────────────────────────

@feeds_router.get("/connections")
def list_feed_connections(session: SessionDep, user: CurrentUserDep):
    """Multi-account sync status: last success / error / consent expired."""
    rows = session.exec(
        select(PlaidConnection).where(
            PlaidConnection.tenant_id == user.tenant_id,
            PlaidConnection.is_active == True,  # noqa: E712
        )
    ).all()
    return [connection_status_payload(r) for r in rows]


class MockConnectBody(BaseModel):
    bank_account_id: int
    institution_name: str = "Mock Open Banking (EU/UK)"
    consent_days: int = Field(default=90, ge=1, le=180)


@feeds_router.post("/mock/connect", status_code=201)
def connect_mock_feed(body: MockConnectBody, session: SessionDep, user: WriteUserDep):
    """Attach a deterministic mock Open Banking feed for demo/tests (no aggregator)."""
    acct = session.get(BankAccount, body.bank_account_id)
    if not acct or acct.tenant_id != user.tenant_id:
        raise HTTPException(400, "Invalid bank account for this tenant")
    token = encrypt_secret(f"mock-{secrets.token_hex(8)}")
    conn = PlaidConnection(
        tenant_id=user.tenant_id,
        bank_account_id=body.bank_account_id,
        access_token=token,
        item_id=f"mock-item-{secrets.token_hex(6)}",
        institution_name=body.institution_name,
        provider="mock",
        sync_status="never",
        consent_expires_at=datetime.utcnow() + timedelta(days=body.consent_days),
    )
    session.add(conn)
    session.commit()
    session.refresh(conn)
    log_audit(session, user, "CREATE", "bank_feed_connection", conn.id, {
        "provider": "mock", "bank_account_id": body.bank_account_id,
    })
    session.commit()
    return connection_status_payload(conn)


class OpenBankingConnectBody(BaseModel):
    bank_account_id: int
    institution_name: str = "Open Banking (EU/UK)"
    consent_days: int = Field(default=90, ge=1, le=180)
    # Optional AIS JSON dump (Berlin Group / OBIE transactions array).
    transactions_json: Optional[str] = None


@feeds_router.post("/openbanking/connect", status_code=201)
def connect_openbanking_feed(body: OpenBankingConnectBody, session: SessionDep, user: WriteUserDep):
    """Attach an EU/UK Open Banking AIS connection (sandbox or JSON dump)."""
    acct = session.get(BankAccount, body.bank_account_id)
    if not acct or acct.tenant_id != user.tenant_id:
        raise HTTPException(400, "Invalid bank account for this tenant")
    secret = body.transactions_json.strip() if body.transactions_json else f"ob-{secrets.token_hex(8)}"
    token = encrypt_secret(secret)
    conn = PlaidConnection(
        tenant_id=user.tenant_id,
        bank_account_id=body.bank_account_id,
        access_token=token,
        item_id=f"ob-item-{secrets.token_hex(6)}",
        institution_name=body.institution_name,
        provider="openbanking",
        sync_status="never",
        consent_expires_at=datetime.utcnow() + timedelta(days=body.consent_days),
    )
    session.add(conn)
    session.commit()
    session.refresh(conn)
    log_audit(session, user, "CREATE", "bank_feed_connection", conn.id, {
        "provider": "openbanking", "bank_account_id": body.bank_account_id,
    })
    session.commit()
    return connection_status_payload(conn)


@feeds_router.post("/{connection_id}/sync")
def sync_feed_connection(connection_id: int, session: SessionDep, user: WriteUserDep):
    """On-demand pull for any provider (mock / openbanking). Plaid uses legacy path."""
    conn = session.get(PlaidConnection, connection_id)
    if not conn or conn.tenant_id != user.tenant_id or not conn.is_active:
        raise HTTPException(404, "Connection not found")
    if (conn.provider or "plaid").lower() == "plaid":
        return sync_plaid_connection(connection_id, session, user)
    try:
        return sync_connection(session, conn)
    except ValueError as exc:
        code = str(exc)
        if code == "consent_expired":
            raise HTTPException(400, "Open Banking consent expired — reconnect the account")
        if code == "connection_missing_bank_account":
            raise HTTPException(400, "Connection has no bank_account_id")
        raise HTTPException(400, code)


# ── Categorization rules (shared by Plaid + CSV/OFX) ─────────────────────────

class RuleIn(BaseModel):
    pattern: str
    account_id: int
    is_active: bool = True
    priority: int = Field(default=100, ge=0, le=10_000)
    match_amount: Optional[float] = None
    create_expense_draft: bool = False


class RuleUpdate(BaseModel):
    pattern: Optional[str] = None
    account_id: Optional[int] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=0, le=10_000)
    match_amount: Optional[float] = None
    create_expense_draft: Optional[bool] = None


def _validate_account(session, tenant_id: int, account_id: int) -> None:
    acct = session.get(Account, account_id)
    if not acct or acct.tenant_id != tenant_id:
        raise HTTPException(400, "Invalid GL account for this tenant")


@rules_router.get("")
def list_rules(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(CategorizationRule).where(CategorizationRule.tenant_id == user.tenant_id)
        .order_by(CategorizationRule.priority, CategorizationRule.id)  # type: ignore
    ).all()
    return [r.model_dump() for r in rows]


@rules_router.post("", status_code=201)
def create_rule(body: RuleIn, session: SessionDep, user: WriteUserDep):
    if not body.pattern.strip():
        raise HTTPException(400, "pattern is required")
    _validate_account(session, user.tenant_id, body.account_id)
    row = CategorizationRule(tenant_id=user.tenant_id, **body.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    data = row.model_dump()
    log_audit(session, user, "CREATE", "categorization_rule", row.id, {"pattern": row.pattern})
    session.commit()
    return data


@rules_router.put("/{rule_id}")
def update_rule(rule_id: int, body: RuleUpdate, session: SessionDep, user: WriteUserDep):
    row = session.get(CategorizationRule, rule_id)
    if not row or row.tenant_id != user.tenant_id:
        raise HTTPException(404, "Rule not found")
    data = body.model_dump(exclude_unset=True)
    if "account_id" in data:
        _validate_account(session, user.tenant_id, data["account_id"])
    if "pattern" in data and not (data["pattern"] or "").strip():
        raise HTTPException(400, "pattern is required")
    for k, v in data.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    out = row.model_dump()
    log_audit(session, user, "UPDATE", "categorization_rule", row.id, data)
    session.commit()
    return out


@rules_router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, session: SessionDep, user: WriteUserDep):
    row = session.get(CategorizationRule, rule_id)
    if not row or row.tenant_id != user.tenant_id:
        raise HTTPException(404, "Rule not found")
    session.delete(row)
    log_audit(session, user, "DELETE", "categorization_rule", rule_id, {})
    session.commit()


# Back-compat aliases under /api/banking/plaid/rules
@plaid_router.get("/rules")
def list_rules_legacy(session: SessionDep, user: CurrentUserDep):
    return list_rules(session, user)


@plaid_router.post("/rules", status_code=201)
def create_rule_legacy(body: RuleIn, session: SessionDep, user: WriteUserDep):
    return create_rule(body, session, user)


# main.py expects `router` — export a combined mount helper
from fastapi import APIRouter as _APIRouter

router = _APIRouter()
router.include_router(plaid_router)
router.include_router(feeds_router)
router.include_router(rules_router)
