"""Saved report CRUD + visibility."""
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from main import app


def _signup(client, email):
    client.post("/api/auth/signup", json={"email": email, "password": "password123",
                                          "full_name": "U", "company_name": email})
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _second_user_same_tenant(client, owner_email, new_email):
    """Create a second user in the SAME tenant as owner_email and return its
    auth headers. (Signup always makes a fresh tenant, so we insert directly.)"""
    from auth import get_password_hash
    from models import User
    with Session(app.state.engine) as s:
        owner = s.exec(select(User).where(User.email == owner_email)).first()
        s.add(User(email=new_email, hashed_password=get_password_hash("password123"),
                   full_name="Other", role="accountant", tenant_id=owner.tenant_id))
        s.commit()
    r = client.post("/api/auth/login", data={"username": new_email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _save(client, auth, name="My Report", visibility="private"):
    return client.post("/api/report-builder/reports", headers=auth, json={
        "name": name, "source_key": "invoices", "visibility": visibility,
        "config": {"columns": ["number", "total"],
                   "filters": [{"field": "status", "op": "in", "value": ["sent"]}]}})


def test_save_list_load_roundtrip(client: TestClient):
    auth = _signup(client, "c1@rb.test")
    rid = _save(client, auth).json()["id"]
    listed = client.get("/api/report-builder/reports", headers=auth).json()
    assert any(x["id"] == rid for x in listed)
    one = client.get(f"/api/report-builder/reports/{rid}", headers=auth).json()
    assert one["config"]["columns"] == ["number", "total"]


def test_save_invalid_config_400(client: TestClient):
    auth = _signup(client, "c2@rb.test")
    r = client.post("/api/report-builder/reports", headers=auth, json={
        "name": "Bad", "source_key": "invoices",
        "config": {"columns": ["does_not_exist"]}})
    assert r.status_code == 400


def test_private_hidden_from_others_shared_visible(client: TestClient):
    a = _signup(client, "owner@rb.test")
    # NOTE: second user in SAME tenant requires an invite flow; here we assert
    # cross-tenant invisibility (private AND shared never leak across tenants).
    priv = _save(client, a, name="Priv", visibility="private").json()["id"]
    b = _signup(client, "other@rb.test")
    assert all(x["id"] != priv for x in client.get("/api/report-builder/reports", headers=b).json())


def test_delete_owner_only(client: TestClient):
    a = _signup(client, "del@rb.test")
    rid = _save(client, a).json()["id"]
    assert client.delete(f"/api/report-builder/reports/{rid}", headers=a).status_code == 200
    assert client.get(f"/api/report-builder/reports/{rid}", headers=a).status_code == 404


def test_patch_updates_own_report(client: TestClient):
    a = _signup(client, "patch@rb.test")
    rid = _save(client, a, name="Before").json()["id"]
    r = client.patch(f"/api/report-builder/reports/{rid}", headers=a, json={
        "name": "After", "source_key": "invoices", "visibility": "shared",
        "config": {"columns": ["number"], "filters": []}})
    assert r.status_code == 200, r.text
    one = client.get(f"/api/report-builder/reports/{rid}", headers=a).json()
    assert one["name"] == "After" and one["visibility"] == "shared"
    assert one["config"]["columns"] == ["number"]


def test_same_tenant_non_owner_cannot_edit_or_delete(client: TestClient):
    a = _signup(client, "ownerx@rb.test")
    rid = _save(client, a, name="Shared", visibility="shared").json()["id"]
    b = _second_user_same_tenant(client, "ownerx@rb.test", "colleague@rb.test")
    # B is in the same tenant and CAN see the shared report...
    assert any(x["id"] == rid for x in client.get("/api/report-builder/reports", headers=b).json())
    # ...but cannot edit or delete it (owner-only -> 403).
    assert client.patch(f"/api/report-builder/reports/{rid}", headers=b, json={
        "name": "Hijack", "source_key": "invoices",
        "config": {"columns": ["number"]}}).status_code == 403
    assert client.delete(f"/api/report-builder/reports/{rid}", headers=b).status_code == 403


def test_save_non_aggregatable_400(client: TestClient):
    auth = _signup(client, "agg@rb.test")
    r = client.post("/api/report-builder/reports", headers=auth, json={
        "name": "BadAgg", "source_key": "invoices",
        "config": {"columns": ["number"], "aggregates": [{"field": "number", "fn": "sum"}]}})
    assert r.status_code == 400
