"""HC lab PDF + patient portal publish (Wave 1)."""
from __future__ import annotations

from urllib.parse import unquote

from fastapi.testclient import TestClient


def _auth(client: TestClient, email: str = "labpub@co.test") -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Lab Tech",
            "company_name": "Lab Co",
            "business_model": "simple",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install_hc(client: TestClient, auth: dict) -> None:
    r = client.post("/api/modules/healthcare/install", headers=auth)
    assert r.status_code in (200, 201), r.text


def _resulted_order(client: TestClient, auth: dict, *, email: str | None = "pat@ex.com", phone: str | None = "+92 300 1234567"):
    body = {"name": "Pat Ient", "gender": "female"}
    if email is not None:
        body["email"] = email
    if phone is not None:
        body["phone"] = phone
    r = client.post("/api/healthcare/patients", headers=auth, json=body)
    assert r.status_code == 201, r.text
    patient = r.json()

    r = client.post(
        "/api/healthcare/lab/tests",
        headers=auth,
        json={"code": "CBC", "name": "Complete Blood Count", "category": "hematology", "standard_fee": 500},
    )
    assert r.status_code == 201, r.text
    test_id = r.json()["id"]

    r = client.post(
        "/api/healthcare/lab/orders",
        headers=auth,
        json={
            "patient_id": patient["id"],
            "order_date": "2026-07-20",
            "source": "walkin",
            "test_ids": [test_id],
        },
    )
    assert r.status_code == 201, r.text
    order = r.json()

    detail = client.get(f"/api/healthcare/lab/orders/{order['id']}", headers=auth)
    assert detail.status_code == 200, detail.text
    item_id = detail.json()["items"][0]["id"]

    r = client.put(
        f"/api/healthcare/lab/orders/{order['id']}/items/{item_id}/result",
        headers=auth,
        json={"result_value": "12.5", "result_unit": "g/dL", "reference_range": "12-16", "is_abnormal": False},
    )
    assert r.status_code == 200, r.text
    return patient, order


def test_lab_pdf_requires_results_then_succeeds(client: TestClient, monkeypatch):
    auth = _auth(client, "pdf1@co.test")
    _install_hc(client, auth)

    r = client.post("/api/healthcare/patients", headers=auth, json={"name": "No Results"})
    assert r.status_code == 201
    patient_id = r.json()["id"]
    r = client.post(
        "/api/healthcare/lab/tests",
        headers=auth,
        json={"code": "GLU", "name": "Glucose", "category": "biochemistry", "standard_fee": 200},
    )
    test_id = r.json()["id"]
    r = client.post(
        "/api/healthcare/lab/orders",
        headers=auth,
        json={"patient_id": patient_id, "order_date": "2026-07-20", "source": "walkin", "test_ids": [test_id]},
    )
    order_id = r.json()["id"]

    r = client.get(f"/api/healthcare/lab/orders/{order_id}/pdf", headers=auth)
    assert r.status_code == 400
    assert "results" in r.json()["detail"].lower()

    patient, order = _resulted_order(client, auth)
    monkeypatch.setattr(
        "services.pdf.render_lab_report_pdf",
        lambda *a, **k: b"%PDF-1.4 lab-fake",
    )
    r = client.get(f"/api/healthcare/lab/orders/{order['id']}/pdf", headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")
    assert patient["email"] == "pat@ex.com"


def test_patient_portal_lab_scoped(client: TestClient, monkeypatch):
    auth = _auth(client, "portal-lab@co.test")
    _install_hc(client, auth)
    monkeypatch.setattr(
        "services.pdf.render_lab_report_pdf",
        lambda *a, **k: b"%PDF-1.4 portal-lab",
    )

    p1, o1 = _resulted_order(client, auth, email="a@ex.com", phone="03001112222")
    p2, o2 = _resulted_order(client, auth, email="b@ex.com", phone="03003334444")

    r = client.post(
        f"/api/portal/mint?entity_type=patient&entity_id={p1['id']}",
        headers=auth,
    )
    assert r.status_code == 200, r.text
    token = r.json()["token"]

    home = client.get(f"/api/portal/{token}")
    assert home.status_code == 200
    assert home.json()["entity_type"] == "patient"
    assert home.json()["entity_name"] == p1["name"]

    labs = client.get(f"/api/portal/{token}/lab-orders")
    assert labs.status_code == 200
    ids = {row["id"] for row in labs.json()}
    assert o1["id"] in ids
    assert o2["id"] not in ids

    ok = client.get(f"/api/portal/{token}/lab-orders/{o1['id']}/pdf")
    assert ok.status_code == 200
    assert ok.content.startswith(b"%PDF")

    denied = client.get(f"/api/portal/{token}/lab-orders/{o2['id']}/pdf")
    assert denied.status_code == 404


def test_publish_portal_email_whatsapp(client: TestClient, monkeypatch):
    auth = _auth(client, "pub-ch@co.test")
    _install_hc(client, auth)
    monkeypatch.setattr(
        "services.pdf.render_lab_report_pdf",
        lambda *a, **k: b"%PDF-1.4",
    )
    # Force complete-results check without needing WeasyPrint during publish either
    sent: list[tuple] = []

    def _capture(to, subject, html_body):
        sent.append((to, subject, html_body))

    monkeypatch.setattr("services.email.queue_email", _capture)
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")

    patient, order = _resulted_order(
        client, auth, email="patient@example.com", phone="+92 (300) 555-7788",
    )

    r = client.post(
        f"/api/healthcare/lab/orders/{order['id']}/publish",
        headers=auth,
        json={"channels": ["portal", "email", "whatsapp"], "mark_delivered": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["portal_url"].startswith("https://app.example.com/portal/")
    assert body["emailed"] is True
    assert body["status"] == "delivered"
    assert body["whatsapp_url"]
    assert "wa.me/923005557788" in body["whatsapp_url"] or "wa.me/9203005557788" in body["whatsapp_url"]
    # Digits-only: strip non-digits from +92 (300) 555-7788 → 923005557788
    assert "923005557788" in body["whatsapp_url"]
    assert "/portal/" in unquote(body["whatsapp_url"])
    assert len(sent) == 1
    assert sent[0][0] == "patient@example.com"
    assert order["order_number"] in sent[0][1]
    assert body["portal_url"] in sent[0][2]

    # Email without address → 400
    p2, o2 = _resulted_order(client, auth, email=None, phone="03009998888")
    # Clear customer email too (create without email still may leave empty string)
    r = client.put(
        f"/api/healthcare/patients/{p2['id']}",
        headers=auth,
        json={"email": ""},
    )
    assert r.status_code == 200
    r = client.post(
        f"/api/healthcare/lab/orders/{o2['id']}/publish",
        headers=auth,
        json={"channels": ["email"]},
    )
    assert r.status_code == 400
    assert "email" in r.json()["detail"].lower()
