"""Plaid → NormalizedTxn adapter (#301). Live HTTP still lives in bank_feeds.py."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlmodel import Session

from models import PlaidConnection
from services.bank_providers.base import NormalizedTxn
from services.money import D


def plaid_dict_to_normalized(txn: dict[str, Any]) -> NormalizedTxn | None:
    ext = txn.get("transaction_id") or txn.get("transaction_id_pending")
    if not ext:
        return None
    raw_date = txn.get("date") or txn.get("authorized_date") or date.today().isoformat()
    try:
        booking = date.fromisoformat(str(raw_date)[:10])
    except ValueError:
        booking = date.today()
    remittance = (
        txn.get("name")
        or txn.get("merchant_name")
        or txn.get("original_description")
        or ""
    )
    return NormalizedTxn(
        external_id=str(ext),
        booking_date=booking,
        amount=D(txn.get("amount") or 0),
        remittance=str(remittance),
        counterparty_name=str(txn.get("merchant_name") or ""),
        currency=str(txn.get("iso_currency_code") or txn.get("currency") or ""),
    )


class PlaidProvider:
    """Placeholder pull adapter — production sync still uses /transactions/sync
    in the router and maps via ``plaid_dict_to_normalized``. Kept so
    ``get_provider("plaid")`` resolves for the scheduler status path."""

    name = "plaid"

    def list_transactions(
        self,
        session: Session,
        connection: PlaidConnection,
        *,
        since: Optional[date] = None,
    ) -> list[NormalizedTxn]:
        # Live pull requires Plaid credentials + access token; the router
        # handles that HTTP call. Scheduler skips plaid unless a future
        # cached-cursor pull is wired here.
        return []
