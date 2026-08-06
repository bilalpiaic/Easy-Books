"""Upsert bank-feed transactions into StatementLine rows (#214 / #301)."""
from __future__ import annotations

from datetime import date as DateType
from decimal import Decimal
from hashlib import sha256
from typing import Any, Iterable

from sqlmodel import Session, select

from models import BankStatementImport, StatementLine
from services.bank_providers.base import NormalizedTxn
from services.bank_providers.plaid_adapter import plaid_dict_to_normalized
from services.money import D, ZERO, money


def _amount_to_dr_cr(amount: float | Decimal) -> tuple[Decimal, Decimal]:
    """Provider convention: positive amount = money out of account.

    StatementLine: credit = money INTO the account.
    So positive (outflow) → debit; negative (inflow) → credit.
    """
    amt = D(amount)
    if amt >= ZERO:
        return money(amt), ZERO
    return ZERO, money(-amt)


def upsert_feed_transactions(
    session: Session,
    *,
    tenant_id: int,
    bank_account_id: int,
    transactions: Iterable[NormalizedTxn],
    sync_label: str | None = None,
    provider: str = "feed",
) -> dict[str, int]:
    """Write normalized feed txns as StatementLines under a sync import batch.

    De-dupes by StatementLine.external_id. Returns {added, imported, skipped}.
    """
    txns = list(transactions)
    label = sync_label or f"{provider}-sync-{DateType.today().isoformat()}"
    file_hash = sha256(f"{tenant_id}:{bank_account_id}:{label}".encode()).hexdigest()[:32]

    imp = session.exec(
        select(BankStatementImport).where(
            BankStatementImport.tenant_id == tenant_id,
            BankStatementImport.bank_account_id == bank_account_id,
            BankStatementImport.file_hash == file_hash,
        )
    ).first()
    if imp is None:
        imp = BankStatementImport(
            tenant_id=tenant_id,
            bank_account_id=bank_account_id,
            file_name=label,
            file_hash=file_hash,
            line_count=0,
            status="parsed",
        )
        session.add(imp)
        session.flush()

    imported = 0
    skipped = 0
    for txn in txns:
        ext_id = txn.external_id
        if ext_id:
            exists = session.exec(
                select(StatementLine).where(
                    StatementLine.tenant_id == tenant_id,
                    StatementLine.external_id == str(ext_id),
                )
            ).first()
            if exists:
                skipped += 1
                continue

        debit, credit = _amount_to_dr_cr(txn.amount)
        session.add(
            StatementLine(
                tenant_id=tenant_id,
                import_id=imp.id,
                date=txn.booking_date.isoformat()[:10],
                description=txn.description[:500],
                debit=debit,
                credit=credit,
                balance=ZERO,
                external_id=str(ext_id) if ext_id else None,
            )
        )
        imported += 1

    imp.line_count = (imp.line_count or 0) + imported
    session.add(imp)
    return {"added": len(txns), "imported": imported, "skipped": skipped}


def upsert_plaid_transactions(
    session: Session,
    *,
    tenant_id: int,
    bank_account_id: int,
    transactions: Iterable[dict[str, Any]],
    sync_label: str | None = None,
) -> dict[str, int]:
    """Backward-compatible wrapper: Plaid dicts → NormalizedTxn → upsert."""
    normalized: list[NormalizedTxn] = []
    for txn in transactions:
        n = plaid_dict_to_normalized(txn)
        if n is not None:
            normalized.append(n)
    return upsert_feed_transactions(
        session,
        tenant_id=tenant_id,
        bank_account_id=bank_account_id,
        transactions=normalized,
        sync_label=sync_label or f"plaid-sync-{DateType.today().isoformat()}",
        provider="plaid",
    )
