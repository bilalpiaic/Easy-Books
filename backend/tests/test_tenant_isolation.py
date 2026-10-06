"""#421 — money and healthcare writes stay inside the caller tenant (incl. FK ids)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str) -> dict:
    r = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": email.split("@")[0],
            "business_model": "simple",
        },
    )
    assert r.status_code in (200, 201), r.text
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    client.cookies.clear()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _invoice_world(client: TestClient, auth: dict, name: str):
    cust = client.post("/api/customers", headers=auth, json={"name": name}).json()
    prod = client.post(
        "/api/products",
        headers=auth,
        json={"name": f"{name} svc", "product_type": "service", "sale_price": 50},
    ).json()
    inv = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-07-01",
            "gst_rate": 0,
            "lines": [{"product_id": prod["id"], "description": "svc", "qty": 1, "rate": 50}],
        },
    )
    assert inv.status_code == 201, inv.text
    return cust, prod, inv.json()


def test_invoice_cross_tenant_get_is_404(client: TestClient):
    a = _signup(client, "iso-inv-a@co.test")
    b = _signup(client, "iso-inv-b@co.test")
    _cust, _prod, inv = _invoice_world(client, a, "Alpha")
    r = client.get(f"/api/invoices/{inv['id']}", headers=b)
    assert r.status_code == 404
    listed = client.get("/api/invoices", headers=b).json()
    ids = [row["id"] for row in listed["items"]] if isinstance(listed, dict) else [row["id"] for row in listed]
    assert inv["id"] not in ids


def test_invoice_cannot_use_foreign_customer_fk(client: TestClient):
    a = _signup(client, "iso-fk-a@co.test")
    b = _signup(client, "iso-fk-b@co.test")
    cust_a, _prod_a, _inv = _invoice_world(client, a, "A Co")
    prod_b = client.post(
        "/api/products",
        headers=b,
        json={"name": "B svc", "product_type": "service", "sale_price": 10},
    ).json()
    r = client.post(
        "/api/invoices",
        headers=b,
        json={
            "customer_id": cust_a["id"],
            "issue_date": "2026-07-02",
            "gst_rate": 0,
            "lines": [{"product_id": prod_b["id"], "description": "x", "qty": 1, "rate": 10}],
        },
    )
    assert r.status_code == 404
    assert "Customer" in r.json()["detail"]


def test_bill_cannot_use_foreign_vendor_fk(client: TestClient):
    a = _signup(client, "iso-bill-a@co.test")
    b = _signup(client, "iso-bill-b@co.test")
    vendor_a = client.post("/api/vendors", headers=a, json={"name": "Vendor A"}).json()
    prod_b = client.post(
        "/api/products",
        headers=b,
        json={"name": "B item", "product_type": "service", "sale_price": 10},
    ).json()
    r = client.post(
        "/api/bills",
        headers=b,
        json={
            "vendor_id": vendor_a["id"],
            "bill_date": "2026-07-02",
            "gst_rate": 0,
            "lines": [{"product_id": prod_b["id"], "description": "x", "qty": 1, "rate": 10}],
        },
    )
    assert r.status_code in (400, 404)


def test_healthcare_patient_cross_tenant_404_and_fk(client: TestClient):
    a = _signup(client, "iso-hc-a@co.test")
    b = _signup(client, "iso-hc-b@co.test")
    for auth in (a, b):
        r = client.post("/api/modules/healthcare/install", headers=auth)
        assert r.status_code in (200, 201), r.text
    pat_a = client.post("/api/healthcare/patients", headers=a, json={"name": "Pat A"}).json()
    doc_b = client.post(
        "/api/healthcare/doctors", headers=b, json={"name": "Doc B", "opd_fee": 0}
    ).json()

    stolen = client.get(f"/api/healthcare/patients/{pat_a['id']}", headers=b)
    assert stolen.status_code == 404

    mutated = client.put(
        f"/api/healthcare/patients/{pat_a['id']}",
        headers=b,
        json={"name": "Hijacked"},
    )
    assert mutated.status_code == 404
    still = client.get(f"/api/healthcare/patients/{pat_a['id']}", headers=a)
    assert still.status_code == 200
    assert still.json()["name"] == "Pat A"

    visit = client.post(
        "/api/healthcare/opd/visits",
        headers=b,
        json={
            "patient_id": pat_a["id"],
            "doctor_id": doc_b["id"],
            "visit_date": "2026-07-20",
        },
    )
    assert visit.status_code == 404
