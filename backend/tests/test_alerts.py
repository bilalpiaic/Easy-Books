"""In-app Alerts: emit, dedupe, read, tenant isolation."""
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import UserAlert


def _auth(client: TestClient, email: str, company: str) -> dict:
    r = client.post("/api/auth/signup", json={
        "email": email, "password": "pw12345678",
        "full_name": "Owner", "company_name": company,
    })
    assert r.status_code == 200, r.text
    tok = client.post("/api/auth/login", data={
        "username": email, "password": "pw12345678",
    }).json()["access_token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def test_overdue_invoice_emits_alert_dedupe_and_read(client: TestClient, admin_headers):
    auth = admin_headers

    r = client.post("/api/customers", headers=auth, json={"name": "Alert Co"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]

    past = (date.today() - timedelta(days=10)).isoformat()
    r = client.post("/api/invoices", headers=auth, json={
        "customer_id": cid,
        "issue_date": past,
        "due_date": past,
        "description": "Past due",
        "gst_rate": 0,
        "status": "posted",
        "lines": [{"description": "Svc", "qty": 1, "rate": 500}],
    })
    assert r.status_code == 201, r.text
    inv = r.json()

    # Flip to overdue the same way the sweep does
    from db import engine
    from models import Invoice
    from services.alerts import refresh_ops_alerts
    with Session(engine) as s:
        row = s.get(Invoice, inv["id"])
        assert row is not None
        row.status = "overdue"
        s.add(row)
        s.commit()
        n = refresh_ops_alerts(s, force=True)
        assert n >= 1
        # Dedupe
        n2 = refresh_ops_alerts(s, force=True)
        assert n2 == 0

    r = client.get("/api/alerts", headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] >= 1
    match = next(a for a in data["items"] if a["entity_id"] == inv["id"] and a["kind"] == "overdue_invoice")
    assert match["unread"] is True
    assert match["href"] == f"/invoices/{inv['id']}"

    r = client.get("/api/alerts/unread-count", headers=auth)
    assert r.status_code == 200
    assert r.json()["count"] >= 1
    assert r.json()["enabled"] is True

    r = client.patch(f"/api/alerts/{match['id']}/read", headers=auth)
    assert r.status_code == 200
    assert r.json()["unread"] is False

    r = client.get("/api/alerts/unread-count", headers=auth)
    # May still have other alerts; at least this one is read
    assert r.status_code == 200

    r = client.get("/api/alerts?unread_only=true", headers=auth)
    unread_ids = {a["id"] for a in r.json()["items"]}
    assert match["id"] not in unread_ids


def test_alerts_tenant_isolation(client: TestClient):
    auth_a = _auth(client, "alerts-a@test", "Tenant A")
    auth_b = _auth(client, "alerts-b@test", "Tenant B")

    r = client.post("/api/customers", headers=auth_a, json={"name": "Only A"})
    assert r.status_code == 201
    cid = r.json()["id"]
    past = (date.today() - timedelta(days=5)).isoformat()
    r = client.post("/api/invoices", headers=auth_a, json={
        "customer_id": cid,
        "issue_date": past,
        "due_date": past,
        "gst_rate": 0,
        "status": "posted",
        "lines": [{"description": "X", "qty": 1, "rate": 100}],
    })
    inv_id = r.json()["id"]

    from db import engine
    from models import Invoice
    from services.alerts import refresh_ops_alerts
    with Session(engine) as s:
        row = s.get(Invoice, inv_id)
        row.status = "overdue"
        s.add(row)
        s.commit()
        refresh_ops_alerts(s, force=True)

    a_items = client.get("/api/alerts", headers=auth_a).json()["items"]
    b_items = client.get("/api/alerts", headers=auth_b).json()["items"]
    assert any(a["entity_id"] == inv_id for a in a_items)
    assert not any(a["entity_id"] == inv_id for a in b_items)


def test_in_app_alerts_disabled(client: TestClient, admin_headers):
    auth = admin_headers
    r = client.patch("/api/settings", headers=auth, json={"in_app_alerts": "false"})
    assert r.status_code == 200, r.text

    r = client.get("/api/alerts/unread-count", headers=auth)
    assert r.status_code == 200
    assert r.json()["count"] == 0
    assert r.json()["enabled"] is False

    from db import engine
    from services.alerts import refresh_ops_alerts
    with Session(engine) as s:
        # Find tenant id from an alert-less refresh
        from models import User
        user = s.exec(select(User).where(User.email == "owner@acme.test")).first()
        n = refresh_ops_alerts(s, tenant_id=user.tenant_id, force=True)
        assert n == 0
        assert s.exec(select(UserAlert).where(UserAlert.tenant_id == user.tenant_id)).all() == []
