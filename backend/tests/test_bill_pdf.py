"""Bill PDF endpoint (# Wave 2 mobile/PDF)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _auth(client: TestClient, email: str = "billpdf@co.test") -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "AP Clerk",
            "company_name": "Bill Co",
            "business_model": "simple",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_bill_pdf_ok_and_404(client: TestClient, monkeypatch):
    auth = _auth(client)
    monkeypatch.setattr(
        "services.pdf.render_bill_pdf",
        lambda *a, **k: b"%PDF-1.4 bill-fake",
    )

    r = client.post("/api/vendors", headers=auth, json={"name": "Acme Supplies"})
    assert r.status_code in (200, 201), r.text
    vendor_id = r.json()["id"]

    r = client.post(
        "/api/bills",
        headers=auth,
        json={
            "vendor_id": vendor_id,
            "bill_date": "2026-07-01",
            "due_date": "2026-07-31",
            "gst_rate": 0,
            "lines": [{"description": "Widgets", "qty": 2, "rate": 50}],
        },
    )
    assert r.status_code == 201, r.text
    bill = r.json()

    r = client.get(f"/api/bills/{bill['id']}/pdf", headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")
    assert bill["number"] in r.headers.get("content-disposition", "")

    # Cross-tenant / missing
    r = client.get("/api/bills/999999/pdf", headers=auth)
    assert r.status_code == 404
