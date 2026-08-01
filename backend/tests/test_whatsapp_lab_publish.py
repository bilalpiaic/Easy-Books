"""WhatsApp Meta Cloud API — lab publish send + settings redaction (#237)."""
from __future__ import annotations

from urllib.parse import unquote

from fastapi.testclient import TestClient


def _auth(client: TestClient, email: str = "waba@co.test") -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "WA Admin",
            "company_name": "WA Co",
            "business_model": "simple",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install_hc(client: TestClient, auth: dict) -> None:
    r = client.post("/api/modules/healthcare/install", headers=auth)
    assert r.status_code in (200, 201), r.text


def _configure_wa(client: TestClient, auth: dict) -> None:
    r = client.patch(
        "/api/settings",
        headers=auth,
        json={
            "wa_meta_access_token": "EAAG-supersecret-token-x9Zq",
            "wa_meta_phone_number_id": "1234567890",
            "wa_meta_template_name": "lab_report_ready",
            "wa_meta_template_lang": "en",
        },
    )
    assert r.status_code == 200, r.text


def _resulted_order(client: TestClient, auth: dict):
    r = client.post(
        "/api/healthcare/patients",
        headers=auth,
        json={"name": "Pat Ient", "email": "p@ex.com", "phone": "+92 300 5557788"},
    )
    assert r.status_code == 201, r.text
    patient = r.json()
    r = client.post(
        "/api/healthcare/lab/tests",
        headers=auth,
        json={"code": "CBC", "name": "CBC", "category": "hematology", "standard_fee": 100},
    )
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
    order = r.json()
    item_id = client.get(f"/api/healthcare/lab/orders/{order['id']}", headers=auth).json()["items"][0]["id"]
    r = client.put(
        f"/api/healthcare/lab/orders/{order['id']}/items/{item_id}/result",
        headers=auth,
        json={"result_value": "12.5", "result_unit": "g/dL", "reference_range": "12-16", "is_abnormal": False},
    )
    assert r.status_code == 200, r.text
    return patient, order


class _FakeResp:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or str(payload or "")

    def json(self):
        return self._payload


def test_settings_redacts_wa_token(client: TestClient):
    auth = _auth(client, "wareact@co.test")
    _configure_wa(client, auth)

    r = client.get("/api/settings", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert "wa_meta_access_token" not in body
    assert body.get("wa_meta_phone_number_id") == "1234567890"
    assert body.get("wa_meta_template_name") == "lab_report_ready"

    st = client.get("/api/settings/whatsapp-status", headers=auth)
    assert st.status_code == 200, st.text
    status = st.json()
    assert status["configured"] is True
    assert status["token_tail"] == "••••x9Zq"
    assert "EAAG" not in (status["token_tail"] or "")
    assert status["phone_number_id"] == "1234567890"


def test_publish_whatsapp_meta_success(client: TestClient, monkeypatch):
    auth = _auth(client, "wasend@co.test")
    _install_hc(client, auth)
    _configure_wa(client, auth)
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
    monkeypatch.setattr("services.pdf.render_lab_report_pdf", lambda *a, **k: b"%PDF")

    captured: dict = {}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _FakeResp(200, {"messages": [{"id": "wamid.ABC"}]})

        def close(self):
            pass

    monkeypatch.setattr("services.whatsapp.httpx.Client", FakeClient)

    _patient, order = _resulted_order(client, auth)
    r = client.post(
        f"/api/healthcare/lab/orders/{order['id']}/publish",
        headers=auth,
        json={"channels": ["whatsapp"], "mark_delivered": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["whatsapp_sent"] is True
    assert body["whatsapp_error"] is None
    assert body["whatsapp_url"]  # still provided for reference
    assert "EAAG" not in str(body)
    assert "supersecret" not in str(body)
    assert "/1234567890/messages" in captured["url"]
    assert captured["json"]["type"] == "template"
    assert captured["json"]["template"]["name"] == "lab_report_ready"
    params = captured["json"]["template"]["components"][0]["parameters"]
    assert params[0]["text"] == order["order_number"]
    assert "/portal/" in params[1]["text"]
    assert "Bearer EAAG" in captured["headers"]["Authorization"]


def test_publish_whatsapp_meta_failure_keeps_wame(client: TestClient, monkeypatch):
    auth = _auth(client, "wafail@co.test")
    _install_hc(client, auth)
    _configure_wa(client, auth)
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
    monkeypatch.setattr("services.pdf.render_lab_report_pdf", lambda *a, **k: b"%PDF")

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def post(self, url, json=None, headers=None):
            return _FakeResp(
                400,
                {"error": {"message": "Template name does not exist in the translation"}},
                text="bad",
            )

        def close(self):
            pass

    monkeypatch.setattr("services.whatsapp.httpx.Client", FakeClient)

    _patient, order = _resulted_order(client, auth)
    r = client.post(
        f"/api/healthcare/lab/orders/{order['id']}/publish",
        headers=auth,
        json={"channels": ["portal", "whatsapp"], "mark_delivered": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["whatsapp_sent"] is False
    assert body["whatsapp_error"]
    assert "Template" in body["whatsapp_error"]
    assert body["whatsapp_url"]
    assert "wa.me/" in body["whatsapp_url"]
    assert "/portal/" in unquote(body["whatsapp_url"])
    assert body["status"] == "delivered"
