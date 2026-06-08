"""The existing run-recognition engine recognizes an origination-built schedule (#47)."""
from sqlmodel import Session, select

import db as _db_module
from models import DeferredRevenueSchedule


def test_recognition_advances_originated_schedule(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h, json={
        "name": "Support", "product_type": "service",
        "default_rate": 120, "is_deferred": True, "recognition_months": 12,
    }).json()
    client.post("/api/invoices", headers=h, json={
        "customer_name": "Acme", "issue_date": "2026-03-01", "gst_rate": 0,
        "lines": [{"product_id": p["id"], "description": "Support", "qty": 1, "rate": 120}],
    })
    r = client.post("/api/deferred-revenue/run-recognition?recognition_date=2026-03-31", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["recognised_count"] == 1
    with Session(_db_module.engine) as s:
        sch = s.exec(select(DeferredRevenueSchedule)).first()
    assert float(sch.recognised_amount) == 10.0   # 120 / 12 months
