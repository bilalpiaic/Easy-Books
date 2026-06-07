"""Editing a posted invoice with deferred lines: rebuild before recognition,
block after (#47)."""
from sqlmodel import Session, select

import db as _db_module
from models import Account, DeferredRevenueSchedule, JournalEntry
from services.money import D


def _sum_col(code, col):
    with Session(_db_module.engine) as s:
        acc = s.exec(select(Account).where(Account.code == code)).first()
        if not acc:
            return 0.0
        rows = s.exec(select(JournalEntry).where(JournalEntry.account_id == acc.id)).all()
        return float(sum(D(getattr(r, col)) for r in rows))


def _net_2300():
    return _sum_col("2300", "credit") - _sum_col("2300", "debit")


def _mk(client, h):
    p = client.post("/api/products", headers=h, json={
        "name": "Support", "product_type": "service",
        "default_rate": 120, "is_deferred": True, "recognition_months": 12,
    }).json()
    inv = client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Support", "qty": 1, "rate": 120}],
    }).json()
    client.patch(f"/api/invoices/{inv['id']}/status?status=sent", headers=h)
    return p, inv


def _schedules():
    with Session(_db_module.engine) as s:
        return s.exec(select(DeferredRevenueSchedule)).all()


def test_edit_before_recognition_rebuilds_schedule(client, admin_headers):
    h = admin_headers
    p, inv = _mk(client, h)
    assert len(_schedules()) == 1 and float(_schedules()[0].total_amount) == 120.0
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Support", "qty": 2, "rate": 120}],
    })
    assert r.status_code in (200, 201), r.text
    sch = _schedules()
    assert len(sch) == 1                       # replaced, not duplicated
    assert float(sch[0].total_amount) == 240.0
    # Net 2300 after reversal+repost = 240 (original 120 credit reversed by the
    # main-JV reversal which debits 2300, then new 240 credited).
    assert _net_2300() == 240.0


def test_edit_after_recognition_is_blocked(client, admin_headers):
    h = admin_headers
    p, inv = _mk(client, h)
    rr = client.post("/api/deferred-revenue/run-recognition?recognition_date=2026-03-15", headers=h)
    assert rr.status_code == 200, rr.text
    assert any(float(s.recognised_amount) > 0 for s in _schedules())
    r = client.put(f"/api/invoices/{inv['id']}", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Support", "qty": 2, "rate": 120}],
    })
    assert r.status_code == 400, r.text
    assert "recogni" in r.json()["detail"].lower()
    assert float(_schedules()[0].total_amount) == 120.0   # untouched
