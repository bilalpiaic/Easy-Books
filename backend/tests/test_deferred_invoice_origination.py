"""Invoicing a deferred product credits Deferred Revenue + builds a schedule (#47)."""
from decimal import Decimal

from sqlmodel import Session, select

import db as _db_module
from models import Account, DeferredRevenueSchedule, JournalEntry
from services.money import D


def _credits_to(code):
    with Session(_db_module.engine) as s:
        acc = s.exec(select(Account).where(Account.code == code)).first()
        if not acc:
            return 0.0
        rows = s.exec(select(JournalEntry).where(JournalEntry.account_id == acc.id)).all()
        return float(sum(D(r.credit) for r in rows))


def _mk_deferred_product(client, h, months=12):
    return client.post("/api/products", headers=h, json={
        "name": "Support", "product_type": "service",
        "default_rate": 120, "is_deferred": True, "recognition_months": months,
    }).json()


def test_deferred_line_credits_2300_not_revenue(client, admin_headers):
    h = admin_headers
    p = _mk_deferred_product(client, h, months=12)
    r = client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Support", "qty": 1, "rate": 120}],
    })
    assert r.status_code in (200, 201), r.text
    assert _credits_to("2300") == 120.0      # net parked in Deferred Revenue
    assert _credits_to("4000") == 0.0        # nothing in Sales Revenue
    with Session(_db_module.engine) as s:
        sch = s.exec(select(DeferredRevenueSchedule)).all()
    assert len(sch) == 1
    assert sch[0].start_date == "2026-03-01"
    assert sch[0].end_date == "2027-03-01"


def test_mixed_invoice_splits_revenue_and_keeps_gst(client, admin_headers):
    h = admin_headers
    pd = _mk_deferred_product(client, h)
    pn = client.post("/api/products", headers=h, json={
        "name": "Setup", "product_type": "service", "default_rate": 80,
    }).json()
    r = client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 10,
        "lines": [
            {"product_id": pd["id"], "description": "Support", "qty": 1, "rate": 120},
            {"product_id": pn["id"], "description": "Setup",   "qty": 1, "rate": 80},
        ],
    })
    assert r.status_code in (200, 201), r.text
    assert _credits_to("2300") == 120.0      # deferred net
    assert _credits_to("4000") == 80.0       # normal net
    assert _credits_to("2200") == 20.0       # GST on 200 @ 10% — posted immediately


def test_non_deferred_invoice_unchanged(client, admin_headers):
    h = admin_headers
    pn = client.post("/api/products", headers=h, json={
        "name": "Setup", "product_type": "service", "default_rate": 80,
    }).json()
    r = client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": pn["id"], "description": "Setup", "qty": 1, "rate": 80}],
    })
    assert r.status_code in (200, 201), r.text
    assert _credits_to("4000") == 80.0
    assert _credits_to("2300") == 0.0
    with Session(_db_module.engine) as s:
        assert s.exec(select(DeferredRevenueSchedule)).all() == []
