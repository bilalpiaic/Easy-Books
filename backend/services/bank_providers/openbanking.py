"""EU/UK Open Banking AIS adapter (#301).

Pull-only: Berlin Group NextGenPSD2 / OBIE-shaped payloads. When
``access_token`` decrypts to a JSON array of transactions (sandbox /
aggregator webhook dump), those are used. Otherwise a deterministic
GBP/EUR sample set is returned so demos and scheduled sync work without
a live TPP.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlmodel import Session

from models import PlaidConnection
from services.bank_providers.base import NormalizedTxn
from services.crypto_secrets import decrypt_secret


def _parse_ob_payload(raw: str) -> list[NormalizedTxn] | None:
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, list):
        return None
    out: list[NormalizedTxn] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        ext = str(row.get("transactionId") or row.get("entryReference") or row.get("external_id") or "")
        if not ext:
            continue
        bd = str(row.get("bookingDate") or row.get("booking_date") or "")[:10]
        try:
            booking = date.fromisoformat(bd)
        except ValueError:
            continue
        amt = row.get("amount")
        if isinstance(amt, dict):
            # Berlin Group Amount: {amount, currency} — sign via creditDebitIndicator
            val = Decimal(str(amt.get("amount") or 0))
            ind = str(row.get("creditDebitIndicator") or "DBIT").upper()
            if ind.startswith("C"):
                val = -abs(val)
            else:
                val = abs(val)
            currency = str(amt.get("currency") or "")
        else:
            val = Decimal(str(amt or 0))
            currency = str(row.get("currency") or "")
        rem = ""
        rem_info = row.get("remittanceInformation") or row.get("remittance") or ""
        if isinstance(rem_info, dict):
            u = rem_info.get("unstructured") or rem_info.get("reference") or ""
            if isinstance(u, list):
                rem = " ".join(str(x) for x in u)
            else:
                rem = str(u)
        else:
            rem = str(rem_info)
        cp = row.get("creditorName") or row.get("debtorName") or row.get("counterparty_name") or ""
        iban = ""
        acct = row.get("creditorAccount") or row.get("debtorAccount") or {}
        if isinstance(acct, dict):
            iban = str(acct.get("iban") or "")
        out.append(NormalizedTxn(
            external_id=ext,
            booking_date=booking,
            amount=val,
            remittance=rem,
            counterparty_name=str(cp),
            counterparty_iban=iban,
            currency=currency,
        ))
    return out


class OpenBankingProvider:
    """Regional EU/UK Open Banking path (sandbox + JSON AIS dump)."""

    name = "openbanking"

    def list_transactions(
        self,
        session: Session,
        connection: PlaidConnection,
        *,
        since: Optional[date] = None,
    ) -> list[NormalizedTxn]:
        raw = ""
        try:
            raw = decrypt_secret(connection.access_token or "") or ""
        except Exception:
            raw = connection.access_token or ""

        parsed = _parse_ob_payload(raw) if raw.strip().startswith("[") else None
        if parsed is not None:
            if since:
                return [t for t in parsed if t.booking_date >= since]
            return parsed

        # Deterministic sandbox when no AIS JSON is stored (demo / scheduler).
        base = since or (date.today() - timedelta(days=7))
        tid = connection.tenant_id
        cid = connection.id or 0
        return [
            NormalizedTxn(
                external_id=f"ob-{tid}-{cid}-salary",
                booking_date=base,
                amount=Decimal("3200.00"),
                remittance="SALARY ACME LTD REF PAYROLL",
                counterparty_name="ACME LTD",
                counterparty_iban="GB33BUKB20201555555555",
                currency="GBP",
            ),
            NormalizedTxn(
                external_id=f"ob-{tid}-{cid}-util",
                booking_date=base + timedelta(days=1),
                amount=Decimal("86.40"),
                remittance="BRITISH GAS ENERGY DD MONTHLY",
                counterparty_name="BRITISH GAS",
                currency="GBP",
            ),
            NormalizedTxn(
                external_id=f"ob-{tid}-{cid}-sepa",
                booking_date=base + timedelta(days=2),
                amount=Decimal("-1500.00"),
                remittance="SEPA CT CUSTOMER INV-7781",
                counterparty_name="EURO BUYER GmbH",
                counterparty_iban="DE89370400440532013000",
                currency="EUR",
            ),
        ]
