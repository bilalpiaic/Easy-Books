"""Upsert Plaid (or similar) bank transactions into StatementLine rows (#214)."""
from __future__ import annotations

from datetime import date as DateType
from decimal import Decimal
from hashlib import sha256
from typing import Any, Iterable

from sqlmodel import Session, select

from models import BankStatementImport, StatementLine
from services.money import D, ZERO, money


def _plaid_amount_to_dr_cr(amount: float | Decimal) -> tuple[Decimal, Decimal]:
    """Plaid: positive amount = money out of account (bank debit from our view = expense).

    Our StatementLine convention (bank_imports): credit = money INTO the account.
    So Plaid positive (outflow) → debit; Plaid negative (inflow) → credit.
    """
    amt = D(amount)
    if amt >= ZERO:
        return money(amt), ZERO
    return ZERO, money(-amt)


def upsert_plaid_transactions(
    session: Session,
    *,
    tenant_id: int,
    bank_account_id: int,
    transactions: Iterable[dict[str, Any]],
    sync_label: str | None = None,
) -> dict[str, int]:
    """Write Plaid `added` transactions as StatementLines under a sync import batch.

    De-dupes by StatementLine.external_id = Plaid transaction_id when present.
    Returns counts: {added, imported, skipped}.
    """
    txns = list(transactions)
    label = sync_label or f"plaid-sync-{DateType.today().isoformat()}"
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
        ext_id = txn.get("transaction_id") or txn.get("transaction_id_pending")
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

        raw_date = txn.get("date") or txn.get("authorized_date") or DateType.today().isoformat()
        desc = (txn.get("name") or txn.get("merchant_name") or "Plaid transaction").strip()
        debit, credit = _plaid_amount_to_dr_cr(txn.get("amount") or 0)
        session.add(
            StatementLine(
                tenant_id=tenant_id,
                import_id=imp.id,
                date=str(raw_date)[:10],
                description=desc[:500],
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
