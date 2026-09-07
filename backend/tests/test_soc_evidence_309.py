"""SOC 2 evidence pack (#309) — admin ZIP + controls catalogue."""
from __future__ import annotations

import csv
import io
import zipfile

from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str, company: str = "SocCo"):
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


def test_controls_catalogue_admin_only(client: TestClient):
    auth = _signup(client, "soc-ctl@test.local")
    r = client.get("/api/compliance/controls", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "not a certified" in body["disclaimer"].lower()
    keys = {c["criterion"] for c in body["controls"]}
    assert "CC6.1" in keys
    assert "CC7.2" in keys
    assert "A1.2" in keys
    assert all(c.get("product") and c.get("evidence") for c in body["controls"])


def test_evidence_pack_zip_contents_and_redaction(client: TestClient):
    auth = _signup(client, "soc-zip@test.local", "SocZip")
    client.patch(
        "/api/settings",
        headers=auth,
        json={"zatca_csid_token": "super-secret-csid", "company_name": "SocZip Ltd"},
    )

    r = client.get("/api/compliance/evidence-pack", headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert "soc2-evidence-pack.zip" in r.headers.get("content-disposition", "")

    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    expected = {
        "DISCLAIMER.txt",
        "runbook.md",
        "manifest.csv",
        "controls.csv",
        "users.csv",
        "access_matrix.csv",
        "permission_overrides.csv",
        "settings_snapshot.csv",
        "api_keys.csv",
        "audit_sample.csv",
        "modules.csv",
        "meta.txt",
    }
    assert expected <= names, f"missing {expected - names}; got {names}"

    disclaimer = zf.read("DISCLAIMER.txt").decode("utf-8").lower()
    assert "not" in disclaimer and "type ii" in disclaimer

    users_text = zf.read("users.csv").decode("utf-8").lower()
    assert "hashed_password" not in users_text
    assert "totp_secret" not in users_text
    assert "soc-zip@test.local" in users_text

    settings_text = zf.read("settings_snapshot.csv").decode("utf-8")
    assert "zatca_csid_token" not in settings_text
    assert "super-secret-csid" not in settings_text
    assert "SocZip Ltd" in settings_text or "company_name" in settings_text

    audit_text = zf.read("audit_sample.csv").decode("utf-8")
    assert "soc_evidence_pack" in audit_text
    assert "EXPORT" in audit_text

    api_text = zf.read("api_keys.csv").decode("utf-8").lower()
    assert "key_hash" not in api_text

    blob = r.content
    assert b"super-secret-csid" not in blob
    assert b"hashed_password" not in blob
    assert b"totp_secret" not in blob
    assert b"key_hash" not in blob

    from services.export_utils import safe_cell
    assert safe_cell("=1+1").startswith("'")

    reader = csv.DictReader(io.StringIO(zf.read("users.csv").decode("utf-8")))
    cols = reader.fieldnames or []
    assert "email" in cols and "role" in cols
    assert "hashed_password" not in cols
    assert "totp_secret" not in cols


def test_evidence_pack_forbidden_for_accountant(client: TestClient):
    owner = _signup(client, "soc-owner@test.local", "SocRbac")
    created = client.post(
        "/api/users",
        headers=owner,
        json={"email": "soc-acct@test.local", "password": "pw12345678", "role": "accountant", "full_name": "Acct"},
    )
    assert created.status_code == 201, created.text
    login = client.post(
        "/api/auth/login",
        data={"username": "soc-acct@test.local", "password": "pw12345678"},
    )
    assert login.status_code == 200, login.text
    client.cookies.clear()
    acct = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = client.get("/api/compliance/evidence-pack", headers=acct)
    assert r.status_code == 403
    r2 = client.get("/api/compliance/controls", headers=acct)
    assert r2.status_code == 403
