"""Scheduled + on-demand bank feed sync (#301)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session, select

from models import PlaidConnection, StatementLine
from services.bank_providers import get_provider
from services.bank_rules import apply_rules_to_lines
from services.plaid_sync import upsert_feed_transactions

# Sync statuses persisted on PlaidConnection.sync_status
STATUS_NEVER = "never"
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_CONSENT_EXPIRED = "consent_expired"


def connection_status_payload(conn: PlaidConnection) -> dict[str, Any]:
    status = conn.sync_status or STATUS_NEVER
    if conn.consent_expires_at and conn.consent_expires_at < datetime.utcnow():
        status = STATUS_CONSENT_EXPIRED
    return {
        "id": conn.id,
        "provider": conn.provider or "plaid",
        "institution_name": conn.institution_name,
        "item_id": conn.item_id,
        "bank_account_id": conn.bank_account_id,
        "last_sync": conn.last_sync,
        "last_error": conn.last_error,
        "sync_status": status,
        "consent_expires_at": conn.consent_expires_at,
        "is_active": conn.is_active,
    }


def mark_connection_error(conn: PlaidConnection, message: str) -> None:
    conn.last_error = (message or "sync failed")[:500]
    # Preserve consent_expired if already set by consent check
    if conn.sync_status != STATUS_CONSENT_EXPIRED:
        conn.sync_status = STATUS_ERROR


def mark_connection_ok(conn: PlaidConnection) -> None:
    conn.last_sync = datetime.utcnow()
    conn.last_error = None
    conn.sync_status = STATUS_OK


def sync_connection(
    session: Session,
    conn: PlaidConnection,
    *,
    since: Optional[Any] = None,
) -> dict[str, Any]:
    """Pull via the connection's provider and upsert statement lines.

    Raises ValueError for caller-mapped HTTP errors (missing bank account, etc.).
    Provider/network failures are recorded on the connection and re-raised.
    """
    if conn.consent_expires_at and conn.consent_expires_at < datetime.utcnow():
        conn.sync_status = STATUS_CONSENT_EXPIRED
        conn.last_error = "Open Banking consent expired — reconnect the account"
        session.add(conn)
        session.commit()
        raise ValueError("consent_expired")

    if not conn.bank_account_id:
        raise ValueError("connection_missing_bank_account")

    provider_name = (conn.provider or "plaid").lower()
    if provider_name == "plaid":
        # Live Plaid HTTP stays in the router (needs credentials + sync cursor).
        raise ValueError("plaid_use_legacy_sync")

    try:
        provider = get_provider(provider_name)
        txns = provider.list_transactions(session, conn, since=since)
        counts = upsert_feed_transactions(
            session,
            tenant_id=conn.tenant_id,
            bank_account_id=conn.bank_account_id,
            transactions=txns,
            provider=provider_name,
        )
        lines = list(
            session.exec(
                select(StatementLine).where(
                    StatementLine.tenant_id == conn.tenant_id,
                    StatementLine.is_matched == False,  # noqa: E712
                    StatementLine.categorized_account_id == None,  # noqa: E711
                )
            ).all()
        )
        categorized = apply_rules_to_lines(
            session, tenant_id=conn.tenant_id, lines=lines
        )
        mark_connection_ok(conn)
        session.add(conn)
        session.commit()
        return {
            "ok": True,
            "provider": provider_name,
            "added": counts["added"],
            "imported": counts["imported"],
            "skipped": counts["skipped"],
            "categorized": categorized,
            "last_sync": conn.last_sync,
            "sync_status": conn.sync_status,
        }
    except ValueError:
        raise
    except Exception as exc:
        mark_connection_error(conn, f"{type(exc).__name__}: {exc}")
        session.add(conn)
        session.commit()
        raise


def sync_all_active_connections(session: Session) -> dict[str, int]:
    """Cross-tenant scheduled pull for non-Plaid (mock / future OB) connections."""
    rows = session.exec(
        select(PlaidConnection).where(PlaidConnection.is_active == True)  # noqa: E712
    ).all()
    ok = err = skipped = 0
    for conn in rows:
        provider = (conn.provider or "plaid").lower()
        if provider == "plaid":
            skipped += 1
            continue
        try:
            sync_connection(session, conn)
            ok += 1
        except ValueError as exc:
            if str(exc) == "consent_expired":
                err += 1
            else:
                skipped += 1
        except Exception:
            err += 1
    return {"ok": ok, "error": err, "skipped": skipped}
