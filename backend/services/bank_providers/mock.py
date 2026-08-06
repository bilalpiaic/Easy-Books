"""Deterministic mock EU/UK-style Open Banking provider for tests + demo (#301)."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlmodel import Session

from models import PlaidConnection
from services.bank_providers.base import NormalizedTxn


class MockOpenBankingProvider:
    name = "mock"

    def list_transactions(
        self,
        session: Session,
        connection: PlaidConnection,
        *,
        since: Optional[date] = None,
    ) -> list[NormalizedTxn]:
        # Stable IDs so re-sync de-dupes via StatementLine.external_id.
        base = since or (date.today() - timedelta(days=7))
        tid = connection.tenant_id
        cid = connection.id or 0
        return [
            NormalizedTxn(
                external_id=f"mock-{tid}-{cid}-rent",
                booking_date=base,
                amount=Decimal("1200.00"),
                remittance="RENT ACME PROPERTIES LTD INV-8841",
                counterparty_name="ACME PROPERTIES LTD",
                counterparty_iban="GB29NWBK60161331926819",
                currency="GBP",
            ),
            NormalizedTxn(
                external_id=f"mock-{tid}-{cid}-saas",
                booking_date=base + timedelta(days=1),
                amount=Decimal("49.00"),
                remittance="CLOUD SAAS MONTHLY SUB *9842",
                counterparty_name="CLOUD SAAS",
                currency="GBP",
            ),
            NormalizedTxn(
                external_id=f"mock-{tid}-{cid}-inflow",
                booking_date=base + timedelta(days=2),
                amount=Decimal("-850.00"),  # inflow
                remittance="CUSTOMER PAYMENT REF PO-221",
                counterparty_name="WIDGET BUYER LTD",
                counterparty_iban="DE89370400440532013000",
                currency="EUR",
            ),
        ]
