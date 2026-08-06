"""Provider-agnostic bank feed types (#301).

Maps the useful common subset across Berlin Group NextGenPSD2 (EU) and OBIE (UK)
onto one shape Easy-Books can upsert:

- ``external_id`` ← transactionId / entryReference
- ``booking_date`` ← bookingDate (prefer over valueDate for matching)
- ``amount`` ← signed amount in account currency (positive = money OUT,
  matching Plaid's convention so existing Dr/Cr mapping stays stable)
- ``remittance`` ← remittanceInformation unstructured (merchant text lives here)
- ``counterparty_name`` / ``counterparty_iban`` ← optional enrichment
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional, Protocol, runtime_checkable

from sqlmodel import Session

from models import PlaidConnection


@dataclass(frozen=True)
class NormalizedTxn:
    external_id: str
    booking_date: date
    amount: Decimal  # positive = outflow from the bank account
    remittance: str = ""
    counterparty_name: str = ""
    counterparty_iban: str = ""
    currency: str = ""

    @property
    def description(self) -> str:
        """Best display/match string — remittance first, then counterparty."""
        rem = (self.remittance or "").strip()
        if rem:
            return rem
        return (self.counterparty_name or "Bank transaction").strip()


@runtime_checkable
class BankFeedProvider(Protocol):
    """Pull-only adapter. EU/UK Open Banking has no bank-side webhooks."""

    name: str

    def list_transactions(
        self,
        session: Session,
        connection: PlaidConnection,
        *,
        since: Optional[date] = None,
    ) -> list[NormalizedTxn]:
        """Return new/changed transactions for this connection."""
        ...
