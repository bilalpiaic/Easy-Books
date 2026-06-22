"""Unit tests for PRA payload builder (no DB required)."""
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from services.pra import build_pra_payload, PAYMENT_MODE_LABELS


def _make_invoice(**kwargs):
    inv = MagicMock()
    inv.number = "SL-2026-001"
    inv.issue_date = "2026-06-22"
    inv.subtotal = Decimal("1000")
    inv.gst_amount = Decimal("170")
    inv.total = Decimal("1170")
    inv.gst_rate = Decimal("17")
    inv.payment_mode = 1
    inv.buyer_ntn = None
    inv.buyer_cnic = None
    for k, v in kwargs.items():
        setattr(inv, k, v)
    return inv


def _make_customer(**kwargs):
    c = MagicMock()
    c.name = "Test Customer"
    c.ntn = None
    c.cnic = None
    c.phone = None
    for k, v in kwargs.items():
        setattr(c, k, v)
    return c


def _make_config():
    return {"pos_id": "123", "token": "tok", "endpoint": "https://example.com", "sandbox": True}


def test_datetime_is_not_midnight():
    """DateTime must include actual time, not 00:00:00."""
    payload = build_pra_payload(_make_invoice(), [], None, {}, {}, _make_config())
    assert payload["DateTime"] != f"2026-06-22 00:00:00"
    # Must match YYYY-MM-DD HH:MM:SS pattern
    import re
    assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", payload["DateTime"])


def test_buyer_ntn_invoice_overrides_customer():
    """invoice.buyer_ntn takes priority over customer.ntn."""
    inv = _make_invoice(buyer_ntn="9999999-9")
    cust = _make_customer(ntn="1111111-1")
    payload = build_pra_payload(inv, [], cust, {}, {}, _make_config())
    assert payload["BuyerPNTN"] == "9999999-9"


def test_buyer_cnic_invoice_overrides_customer():
    """invoice.buyer_cnic takes priority over customer.cnic."""
    inv = _make_invoice(buyer_cnic="3520299999999")
    cust = _make_customer(cnic="1111122222222")
    payload = build_pra_payload(inv, [], cust, {}, {}, _make_config())
    assert payload["BuyerCNIC"] == "3520299999999"


def test_buyer_ntn_falls_back_to_customer():
    """When invoice.buyer_ntn is None, use customer.ntn."""
    inv = _make_invoice(buyer_ntn=None)
    cust = _make_customer(ntn="7654321-0")
    payload = build_pra_payload(inv, [], cust, {}, {}, _make_config())
    assert payload["BuyerPNTN"] == "7654321-0"


def test_buyer_empty_when_no_source():
    """When neither invoice nor customer have NTN/CNIC, send empty string."""
    payload = build_pra_payload(_make_invoice(), [], None, {}, {}, _make_config())
    assert payload["BuyerPNTN"] == ""
    assert payload["BuyerCNIC"] == ""
