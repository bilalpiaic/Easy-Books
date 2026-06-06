"""Voucher series catalog and numbering helpers.

This module is the single source of truth for the voucher-type catalog,
per-type sequence numbering, and the cash/bank account classification
used to split payment vouchers into CR/BR and CP/BP.
"""
from __future__ import annotations

from sqlmodel import Session, select

VOUCHER_TYPES: dict[str, str] = {
    "JV": "Journal Voucher",
    "CP": "Cash Payment",
    "CR": "Cash Receipt",
    "BP": "Bank Payment",
    "BR": "Bank Receipt",
    "SL": "Sales Invoice",
    "SR": "Sales Return",
    "PR": "Purchase Invoice",
    "PV": "Purchase Return",
    "CO": "Contra",
    "DN": "Debit Note",
    "CN": "Credit Note",
}


def voucher_number(session: Session, tenant_id: int, vtype: str) -> str:
    """Return the next formatted voucher number for the given type.

    Uses the project's atomic per-tenant SequenceCounter mechanism so
    concurrent callers serialise without minting duplicate numbers.
    Falls back to "JV" for any unrecognised type.

    Format: ``{TYPE}-{seq:06d}`` e.g. ``SL-000001``.
    """
    from routers.common import next_number

    if vtype not in VOUCHER_TYPES:
        vtype = "JV"
    return next_number(
        session,
        tenant_id,
        name=f"voucher:{vtype}",
        prefix=vtype,
        width=6,
        fmt="{prefix}-{seq:06d}",
    )


def classify_cash_account(
    session: Session, tenant_id: int, account_id: int | None
) -> str:
    """Return ``'bank'`` if *account_id* is referenced by a ``BankAccount``
    row for the tenant, otherwise ``'cash'``.

    Used by payment routers to assign ``BR``/``CR`` (bank/cash receipt) and
    ``BP``/``CP`` (bank/cash payment) voucher types automatically.
    """
    if account_id is None:
        return "cash"

    from models import BankAccount

    linked = session.exec(
        select(BankAccount.id).where(
            BankAccount.tenant_id == tenant_id,
            BankAccount.coa_account_id == account_id,
        )
    ).first()
    return "bank" if linked else "cash"
