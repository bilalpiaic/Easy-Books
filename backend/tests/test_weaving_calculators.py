"""#196 — weaving/sizing calculator API (preview, assign, history)."""


def _signup(client, email, company="Calc Co"):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "Calc User", "company_name": company, "business_model": "trader",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install(client, auth, *modules):
    for m in modules:
        r = client.post(f"/api/modules/{m}/install", headers=auth)
        assert r.status_code in (200, 201), f"{m}: {r.text}"


def _make_contract(client, auth):
    cust = client.post("/api/customers", headers=auth, json={"name": "Buyer"}).json()
    fq = client.post("/api/weaving/fabric-qualities", headers=auth,
                    json={"code": "FQ", "name": "Poplin"}).json()
    yt = client.post("/api/weaving/yarn-types", headers=auth,
                    json={"code": "YT", "name": "Cotton", "count_ne": 40}).json()
    assert yt.get("count_ne") == 40.0
    c = client.post("/api/weaving/contracts", headers=auth, json={
        "customer_id": cust["id"],
        "fabric_quality_id": fq["id"],
        "yarn_type_id": yt["id"],
        "start_date": "2026-07-01",
        "contract_meters": 10000,
        "pick_per_inch": 60,
        "assumed_yarn_rate_per_kg": 220,
        "fabric_return_price_per_meter": 50,
        "weaving_rate": 10,
        "status": "draft",
    }).json()
    return c


_WEAVE_BODY = {
    "epi": 60, "ppi": 50, "width_in": 60, "length_yd": 1000,
    "warp_ne": 40, "weft_ne": 30,
    "warp_crimp_pct": 10, "weft_crimp_pct": 5,
    "visible_waste_pct": 3, "invisible_waste_pct": 1,
}


def test_calculators_module_gate(client):
    auth = _signup(client, "calc-gate@test.com")
    r = client.post("/api/weaving/calculators/weaving", headers=auth, json=_WEAVE_BODY)
    assert r.status_code == 403


def test_preview_weaving_and_sizing(client):
    auth = _signup(client, "calc-prev@test.com")
    _install(client, auth, "inventory", "weaving")
    w = client.post("/api/weaving/calculators/weaving", headers=auth, json=_WEAVE_BODY)
    assert w.status_code == 200, w.text
    body = w.json()
    assert abs(body["warp_lbs"] - 122.57) < 0.02
    assert body["total"]["kg"] > 0
    assert body["total"]["bags"] > 0

    s = client.post("/api/weaving/calculators/sizing", headers=auth, json={
        "unsized_kg": 100, "pickup_pct": 12, "stretch_pct": 1.5,
        "visible_waste_pct": 0.7, "invisible_waste_pct": 1.0,
    })
    assert s.status_code == 200, s.text
    assert abs(s.json()["net_before_waste_kg"] - 113.68) < 0.02


def test_assign_first_then_mismatch(client):
    auth = _signup(client, "calc-assign@test.com")
    _install(client, auth, "inventory", "weaving")
    c = _make_contract(client, auth)

    r1 = client.post("/api/weaving/calculators/weaving/assign", headers=auth, json={
        **_WEAVE_BODY, "contract_id": c["id"],
    })
    assert r1.status_code == 200, r1.text
    data = r1.json()
    assert data["contract"]["planned_total_yarn_kg"] is not None
    assert data["contract"]["planned_warp_kg"] is not None
    assert data["contract"]["warp_count_ne"] == 40.0
    assert data["run"]["calc_type"] == "weaving"
    planned = data["contract"]["planned_total_yarn_kg"]

    hist = client.get(
        f"/api/weaving/calculators/history?contract_id={c['id']}", headers=auth
    )
    assert hist.status_code == 200
    assert len(hist.json()) == 1

    # Different length → large qty change vs planned
    bad = {**_WEAVE_BODY, "length_yd": 2000, "contract_id": c["id"]}
    r2 = client.post("/api/weaving/calculators/weaving/assign", headers=auth, json=bad)
    assert r2.status_code == 400, r2.text
    detail = r2.json()["detail"]
    assert "warnings" in detail or "override" in str(detail).lower()

    r3 = client.post("/api/weaving/calculators/weaving/assign", headers=auth, json={
        **bad, "override_reason": "Customer increased order",
    })
    assert r3.status_code == 200, r3.text
    assert r3.json()["contract"]["planned_total_yarn_kg"] > planned
    assert r3.json()["run"]["override_reason"] == "Customer increased order"

    hist2 = client.get(
        f"/api/weaving/calculators/history?contract_id={c['id']}", headers=auth
    )
    assert len(hist2.json()) == 2


def test_assign_sizing(client):
    auth = _signup(client, "calc-size@test.com")
    _install(client, auth, "inventory", "weaving")
    c = _make_contract(client, auth)
    r = client.post("/api/weaving/calculators/sizing/assign", headers=auth, json={
        "contract_id": c["id"],
        "unsized_kg": 100,
        "pickup_pct": 12,
        "stretch_pct": 1.5,
        "visible_waste_pct": 0.7,
        "invisible_waste_pct": 1.0,
    })
    assert r.status_code == 200, r.text
    assert r.json()["contract"]["planned_total_yarn_kg"] is not None
    assert r.json()["run"]["calc_type"] == "sizing"


def test_history_tenant_isolation(client):
    auth_a = _signup(client, "calc-a@test.com", "CoA")
    _install(client, auth_a, "inventory", "weaving")
    c = _make_contract(client, auth_a)
    client.post("/api/weaving/calculators/weaving/assign", headers=auth_a, json={
        **_WEAVE_BODY, "contract_id": c["id"],
    })

    auth_b = _signup(client, "calc-b@test.com", "CoB")
    _install(client, auth_b, "inventory", "weaving")
    r = client.get(
        f"/api/weaving/calculators/history?contract_id={c['id']}", headers=auth_b
    )
    assert r.status_code == 404
