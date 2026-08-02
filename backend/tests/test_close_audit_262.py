"""#262 Month-end close checklist + auditor ZIP export pack."""
from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient


def _auth(client: TestClient, email: str, company: str = "CloseCo"):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": company,
            "business_model": "simple",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_period(client: TestClient, auth: dict) -> dict:
    r = client.post(
        "/api/periods",
        headers=auth,
        json={"name": "Jul 2026", "period_start": "2026-07-01", "period_end": "2026-07-31"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_lock_blocked_when_required_checklist_open(client: TestClient):
    auth = _auth(client, "close-block@test.local", "CloseBlock")
    period = _make_period(client, auth)
    pid = period["id"]

    cl = client.get(f"/api/periods/{pid}/checklist", headers=auth)
    assert cl.status_code == 200, cl.text
    items = cl.json()
    assert len(items) >= 3
    required = [i for i in items if i["required"]]
    assert required
    assert any(not i["is_done"] for i in required)

    soft = client.post(f"/api/periods/{pid}/close?mode=soft", headers=auth)
    assert soft.status_code == 400, soft.text
    assert "checklist" in soft.json()["detail"].lower()

    lock = client.patch(f"/api/periods/{pid}/lock?is_locked=true", headers=auth)
    assert lock.status_code == 400, lock.text

    # Complete only required tasks → soft close succeeds
    for item in required:
        r = client.patch(
            f"/api/periods/{pid}/checklist/{item['id']}",
            headers=auth,
            json={"is_done": True},
        )
        assert r.status_code == 200, r.text
        assert r.json()["is_done"] is True

    soft2 = client.post(f"/api/periods/{pid}/close?mode=soft", headers=auth)
    assert soft2.status_code == 200, soft2.text
    assert soft2.json()["period"]["is_locked"] is True


def test_lock_allowed_when_checklist_requirement_disabled(client: TestClient):
    auth = _auth(client, "close-off@test.local", "CloseOff")
    period = _make_period(client, auth)
    pid = period["id"]

    s = client.patch(
        "/api/settings",
        headers=auth,
        json={"period_close_require_checklist": "false"},
    )
    assert s.status_code == 200, s.text

    soft = client.post(f"/api/periods/{pid}/close?mode=soft", headers=auth)
    assert soft.status_code == 200, soft.text
    assert soft.json()["period"]["is_locked"] is True


def test_audit_pack_zip_contains_expected_files(client: TestClient):
    auth = _auth(client, "close-zip@test.local", "CloseZip")
    period = _make_period(client, auth)
    pid = period["id"]

    r = client.get(f"/api/periods/{pid}/audit-pack", headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers.get("content-disposition", "")

    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    expected = {
        "manifest.csv",
        "trial_balance.csv",
        "general_ledger.csv",
        "ar_aging.csv",
        "ap_aging.csv",
        "inventory_valuation.csv",
        "fixed_assets.csv",
        "cash_flow.csv",
    }
    assert expected <= names, f"missing {expected - names}; got {names}"

    # Formula-injection safety: cells that look like formulas should be prefixed
    from services.export_utils import safe_cell
    assert safe_cell("=1+1").startswith("'")
    assert safe_cell("ok").startswith("ok") or safe_cell("ok") == "ok"
