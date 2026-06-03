"""Report builder safety — the most important suite."""
from fastapi.testclient import TestClient


def _signup(client, email):
    client.post("/api/auth/signup", json={"email": email, "password": "password123",
                                          "full_name": "U", "company_name": email})
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_unknown_source_400(client: TestClient):
    auth = _signup(client, "s1@rb.test")
    r = client.post("/api/report-builder/run", headers=auth,
                    json={"source_key": "secrets", "config": {"columns": []}})
    assert r.status_code == 400


def test_op_type_mismatch_400(client: TestClient):
    auth = _signup(client, "s2@rb.test")
    r = client.post("/api/report-builder/run", headers=auth, json={
        "source_key": "invoices",
        "config": {"columns": ["total"], "filters": [{"field": "total", "op": "contains", "value": "x"}]}})
    assert r.status_code == 400


def test_tenant_isolation(client: TestClient):
    a = _signup(client, "tenantA@rb.test")
    cust = client.post("/api/customers", headers=a, json={"name": "SecretCo"}).json()
    client.post("/api/invoices", headers=a, json={
        "customer_id": cust["id"], "issue_date": "2026-05-02", "due_date": "2026-06-30",
        "gst_rate": 0, "currency": "USD", "lines": [{"description": "S", "qty": 1, "rate": 999}]})
    b = _signup(client, "tenantB@rb.test")
    r = client.post("/api/report-builder/run", headers=b, json={
        "source_key": "invoices", "config": {"columns": ["number", "customer_name", "total"]}})
    assert r.status_code == 200
    assert r.json()["total_count"] == 0            # B sees none of A's data
    assert all("SecretCo" != row.get("customer_name") for row in r.json()["rows"])
