"""Uniform module CoA / location integration on install + repair."""


def _signup(client, email, model="simple"):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "Owner", "company_name": "Co", "business_model": model,
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_install_textile_seeds_coa_and_locations(client):
    auth = _signup(client, "integ-tp@test.com", "simple")
    r = client.post("/api/modules/textile_processing/install", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "integration" in body
    assert any(x["module_id"] == "textile_processing" for x in body["integration"])

    status = client.get("/api/modules/integration-status", headers=auth).json()
    tp = next(m for m in status["modules"] if m["module_id"] == "textile_processing")
    assert tp["ok"] is True
    assert "4150" not in tp["missing_accounts"]
    assert "5220" not in tp["missing_accounts"]
    assert "1210" not in tp["missing_accounts"]
    assert "GODOWN" not in tp["missing_locations"]


def test_install_healthcare_seeds_revenue_accounts(client):
    auth = _signup(client, "integ-hc@test.com", "simple")
    r = client.post("/api/modules/healthcare/install", headers=auth)
    assert r.status_code == 200, r.text
    status = client.get("/api/modules/integration-status", headers=auth).json()
    hc = next(m for m in status["modules"] if m["module_id"] == "healthcare")
    assert hc["ok"] is True
    for code in ("4100", "4110", "4121", "4130", "2310"):
        assert code not in hc["missing_accounts"]


def test_install_spinning_seeds_wip_and_sales_coa(client):
    auth = _signup(client, "integ-sp@test.com", "simple")
    r = client.post("/api/modules/spinning/install", headers=auth)
    assert r.status_code == 200, r.text
    status = client.get("/api/modules/integration-status", headers=auth).json()
    sp = next(m for m in status["modules"] if m["module_id"] == "spinning")
    assert sp["ok"] is True
    for code in ("1200", "1204", "4170", "5010"):
        assert code not in sp["missing_accounts"]
    for loc in ("RAW", "FG-YARN"):
        assert loc not in sp["missing_locations"]


def test_repair_integration_backfills(client):
    auth = _signup(client, "integ-repair@test.com", "simple")
    client.post("/api/modules/textile_processing/install", headers=auth)
    r = client.post("/api/modules/repair-integration", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["status"]["all_ok"] is True


def test_textile_contractor_expense_avoids_mfg_collision(client):
    """Manufacturing 5200 = OH; textile labor must resolve to 5220."""
    auth = _signup(client, "integ-collide@test.com", "manufacturing")
    r = client.post("/api/modules/textile_processing/install", headers=auth)
    assert r.status_code == 200, r.text
    status = client.get("/api/modules/integration-status", headers=auth).json()
    tp = next(m for m in status["modules"] if m["module_id"] == "textile_processing")
    assert "5220" not in tp["missing_accounts"]
    assert "5215" not in tp["missing_accounts"]
