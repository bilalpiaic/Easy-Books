"""#417 — healthcare lab / OPD / pharmacy writes must stay inside the caller tenant."""
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
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install_hc(client: TestClient, auth: dict) -> None:
    r = client.post("/api/modules/healthcare/install", headers=auth)
    assert r.status_code in (200, 201), r.text


def _patient(client: TestClient, auth: dict, name: str) -> dict:
    r = client.post("/api/healthcare/patients", headers=auth, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def _doctor(client: TestClient, auth: dict, name: str) -> dict:
    r = client.post("/api/healthcare/doctors", headers=auth, json={"name": name, "opd_fee": 0})
    assert r.status_code == 201, r.text
    return r.json()


def _lab_order_with_item(client: TestClient, auth: dict):
    patient = _patient(client, auth, "Pat Lab")
    r = client.post(
        "/api/healthcare/lab/tests",
        headers=auth,
        json={"code": "CBC", "name": "CBC", "category": "hematology", "standard_fee": 100},
    )
    assert r.status_code in (200, 201), r.text
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
    assert r.status_code in (200, 201), r.text
    order = r.json()
    detail = client.get(f"/api/healthcare/lab/orders/{order['id']}", headers=auth)
    assert detail.status_code == 200, detail.text
    item_id = detail.json()["items"][0]["id"]
    return order, item_id


def _result_payload():
    return {
        "result_value": "12.5",
        "result_unit": "g/dL",
        "reference_range": "12-16",
        "is_abnormal": False,
    }


def test_enter_result_same_tenant_ok(client: TestClient):
    auth = _signup(client, "hc-lab-ok@a.test")
    _install_hc(client, auth)
    order, item_id = _lab_order_with_item(client, auth)
    r = client.put(
        f"/api/healthcare/lab/orders/{order['id']}/items/{item_id}/result",
        headers=auth,
        json=_result_payload(),
    )
    assert r.status_code == 200, r.text
    check = client.get(f"/api/healthcare/lab/orders/{order['id']}", headers=auth)
    assert check.status_code == 200, check.text
    item = next(i for i in check.json()["items"] if i["id"] == item_id)
    assert item["result_value"] == "12.5"


def test_enter_result_cross_tenant_404_no_mutate(client: TestClient):
    auth_a = _signup(client, "hc-lab-a@a.test")
    auth_b = _signup(client, "hc-lab-b@b.test")
    _install_hc(client, auth_a)
    _install_hc(client, auth_b)
    order, item_id = _lab_order_with_item(client, auth_a)

    r = client.put(
        f"/api/healthcare/lab/orders/{order['id']}/items/{item_id}/result",
        headers=auth_b,
        json=_result_payload(),
    )
    assert r.status_code == 404, r.text

    check = client.get(f"/api/healthcare/lab/orders/{order['id']}", headers=auth_a)
    assert check.status_code == 200
    item = check.json()["items"][0]
    assert item["result_value"] in (None, "")
    assert item.get("resulted_at") in (None, "")


def test_create_visit_same_tenant_marks_token(client: TestClient):
    auth = _signup(client, "hc-opd-ok@a.test")
    _install_hc(client, auth)
    patient = _patient(client, auth, "Walk In")
    doctor = _doctor(client, auth, "Dr Ok")
    r = client.post(
        "/api/healthcare/opd/tokens",
        headers=auth,
        json={"doctor_id": doctor["id"], "visit_date": "2026-07-20", "patient_id": patient["id"]},
    )
    assert r.status_code == 201, r.text
    token = r.json()
    r = client.post(
        "/api/healthcare/opd/visits",
        headers=auth,
        json={
            "patient_id": patient["id"],
            "doctor_id": doctor["id"],
            "visit_date": "2026-07-20",
            "token_id": token["id"],
            "visit_type": "first",
        },
    )
    assert r.status_code == 201, r.text
    tokens = client.get(
        "/api/healthcare/opd/tokens",
        headers=auth,
        params={"doctor_id": doctor["id"], "date": "2026-07-20"},
    ).json()
    assert tokens[0]["status"] == "visited"


def test_create_visit_foreign_token_404_no_mutate(client: TestClient):
    auth_a = _signup(client, "hc-opd-a@a.test")
    auth_b = _signup(client, "hc-opd-b@b.test")
    _install_hc(client, auth_a)
    _install_hc(client, auth_b)
    patient_a = _patient(client, auth_a, "Pat A")
    doctor_a = _doctor(client, auth_a, "Dr A")
    token = client.post(
        "/api/healthcare/opd/tokens",
        headers=auth_a,
        json={"doctor_id": doctor_a["id"], "visit_date": "2026-07-20", "patient_id": patient_a["id"]},
    ).json()

    patient_b = _patient(client, auth_b, "Pat B")
    doctor_b = _doctor(client, auth_b, "Dr B")
    r = client.post(
        "/api/healthcare/opd/visits",
        headers=auth_b,
        json={
            "patient_id": patient_b["id"],
            "doctor_id": doctor_b["id"],
            "visit_date": "2026-07-20",
            "token_id": token["id"],
            "visit_type": "first",
        },
    )
    assert r.status_code == 404, r.text

    still = client.get(
        "/api/healthcare/opd/tokens",
        headers=auth_a,
        params={"doctor_id": doctor_a["id"], "date": "2026-07-20"},
    ).json()
    assert still[0]["id"] == token["id"]
    assert still[0]["status"] == "waiting"

    visits_b = client.get("/api/healthcare/opd/visits", headers=auth_b).json()
    assert visits_b == []


def test_dispense_same_tenant_ok(client: TestClient):
    auth = _signup(client, "hc-rx-ok@a.test")
    _install_hc(client, auth)
    item_id = _prescription_item(client, auth)
    r = client.post(
        "/api/healthcare/store/pharmacy/dispense",
        headers=auth,
        params={"item_id": item_id, "dispensed_qty": "1"},
    )
    assert r.status_code == 200, r.text
    pending = client.get("/api/healthcare/store/pharmacy/pending", headers=auth).json()
    assert all(i["id"] != item_id for i in pending)


def test_dispense_cross_tenant_404_no_mutate(client: TestClient):
    auth_a = _signup(client, "hc-rx-a@a.test")
    auth_b = _signup(client, "hc-rx-b@b.test")
    _install_hc(client, auth_a)
    _install_hc(client, auth_b)
    item_id = _prescription_item(client, auth_a)
    r = client.post(
        "/api/healthcare/store/pharmacy/dispense",
        headers=auth_b,
        params={"item_id": item_id, "dispensed_qty": "99"},
    )
    assert r.status_code == 404, r.text
    pending = client.get("/api/healthcare/store/pharmacy/pending", headers=auth_a).json()
    assert any(i["id"] == item_id for i in pending)
    stolen = next(i for i in pending if i["id"] == item_id)
    assert stolen.get("dispensed_qty") in (None, "")


def _prescription_item(client: TestClient, auth: dict) -> int:
    patient = _patient(client, auth, "Rx Pat")
    doctor = _doctor(client, auth, "Rx Dr")
    visit = client.post(
        "/api/healthcare/opd/visits",
        headers=auth,
        json={
            "patient_id": patient["id"],
            "doctor_id": doctor["id"],
            "visit_date": "2026-07-20",
            "visit_type": "first",
        },
    )
    assert visit.status_code == 201, visit.text
    rx = client.post(
        f"/api/healthcare/opd/visits/{visit.json()['id']}/prescriptions",
        headers=auth,
        json={"notes": "take with food"},
    )
    assert rx.status_code == 201, rx.text
    item = client.post(
        f"/api/healthcare/prescriptions/{rx.json()['id']}/items",
        headers=auth,
        json={"medicine_name": "Paracetamol", "qty": 1},
    )
    assert item.status_code == 201, item.text
    return item.json()["id"]
