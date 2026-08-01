"""Core multi-jurisdiction tax engine (#263)."""
from __future__ import annotations

from services.money import D, money
from services.tax_engine import aggregate_document_taxes, compute_line_tax


def _gl(client, auth, code="2200"):
    accounts = client.get("/api/accounts?limit=500", headers=auth).json()
    items = accounts["items"] if isinstance(accounts, dict) else accounts
    for a in items:
        if a["code"] == code:
            return a["id"]
    # Fallback: first liability
    for a in items:
        if a["type"] == "Liability" and not a.get("is_group"):
            return a["id"]
    raise AssertionError("no GL account for tax code")


def _make_code(client, auth, *, code, rate, ttype="output", **flags):
    gl = _gl(client, auth, "2200" if ttype == "output" else "1250")
    r = client.post(
        "/api/tax-codes",
        headers=auth,
        json={
            "code": code,
            "name": f"{code} {rate}%",
            "rate": rate,
            "type": ttype,
            "gl_account_id": gl,
            **flags,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_compute_line_tax_exclusive_inclusive_and_rc():
    exclusive = compute_line_tax(D("100"), D("17"), inclusive=False)
    assert exclusive.net == money(D("100"))
    assert exclusive.tax == money(D("17"))
    assert exclusive.include_in_total is True

    inclusive = compute_line_tax(D("117"), D("17"), inclusive=True)
    assert inclusive.net == money(D("100"))
    assert inclusive.tax == money(D("17"))

    rc = compute_line_tax(
        D("100"), D("17"), reverse_charge=True, gl_account_id=1
    )
    assert rc.tax == money(D("17"))
    assert rc.include_in_total is False
    assert rc.gl_account_id is None

    exempt = compute_line_tax(D("100"), D("17"), exempt=True, gl_account_id=1)
    assert exempt.tax == money(D("0"))
    assert exempt.is_exempt is True

    agg = aggregate_document_taxes([exclusive, rc])
    assert agg.total_tax_in_total == money(D("17"))
    assert agg.total_tax_rc_only == money(D("17"))
    assert 1 not in agg.per_gl_tax  # RC posts no GL


def test_multi_rate_invoice_two_gl_legs(client, admin_headers):
    auth = admin_headers
    std = _make_code(client, auth, code="STD17", rate=17)
    red = _make_code(client, auth, code="RED5", rate=5)
    # Give RED5 a distinct GL so we can assert two legs.
    accounts = client.get("/api/accounts?limit=500", headers=auth).json()["items"]
    alt = next(a for a in accounts if a["code"] == "2000" or (a["type"] == "Liability" and a["id"] != std["gl_account_id"] and not a.get("is_group")))
    client.put(
        f"/api/tax-codes/{red['id']}",
        headers=auth,
        json={"name": red["name"]},  # rate unchanged
    )
    # Directly patch gl via DB — update API may not expose gl change in all paths;
    # TaxCodeUpdate does support gl_account_id.
    r = client.put(
        f"/api/tax-codes/{red['id']}",
        headers=auth,
        json={"gl_account_id": alt["id"]},
    )
    assert r.status_code == 200, r.text
    red = r.json()
    assert red["gl_account_id"] != std["gl_account_id"]

    inv = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_name": "Multi-rate Co",
            "issue_date": "2026-06-15",
            "due_date": "2026-06-30",
            "gst_rate": 0,
            "lines": [
                {"description": "Std", "qty": 1, "rate": 1000, "tax_code_id": std["id"]},
                {"description": "Red", "qty": 1, "rate": 200, "tax_code_id": red["id"]},
            ],
        },
    )
    assert inv.status_code == 201, inv.text
    body = inv.json()
    assert float(body["subtotal"]) == 1200.0
    assert float(body["gst_amount"]) == 180.0  # 170 + 10
    assert float(body["total"]) == 1380.0
    lines = body["lines"]
    assert sorted(float(l["tax_amount"]) for l in lines) == [10.0, 170.0]

    ret = client.get(
        "/api/reports/tax-return?start=2026-06-01&end=2026-06-30",
        headers=auth,
    )
    assert ret.status_code == 200, ret.text
    rows = {r["code"]: r for r in ret.json()["rows"]}
    assert float(rows["STD17"]["output_tax"]) == 170.0
    assert float(rows["RED5"]["output_tax"]) == 10.0


def test_reverse_charge_excludes_tax_from_total_and_gl(client, admin_headers):
    auth = admin_headers
    rc = _make_code(
        client, auth, code="RC17", rate=17, is_reverse_charge=True
    )
    inv = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_name": "RC Customer",
            "issue_date": "2026-06-20",
            "gst_rate": 0,
            "lines": [
                {"description": "Imported svc", "qty": 1, "rate": 500, "tax_code_id": rc["id"]},
            ],
        },
    )
    assert inv.status_code == 201, inv.text
    body = inv.json()
    assert float(body["subtotal"]) == 500.0
    assert float(body["gst_amount"]) == 0.0
    assert float(body["total"]) == 500.0
    assert float(body["lines"][0]["tax_amount"]) == 85.0  # reported

    ret = client.get(
        "/api/reports/tax-return?start=2026-06-01&end=2026-06-30",
        headers=auth,
    ).json()
    row = next(r for r in ret["rows"] if r["code"] == "RC17")
    assert float(row["reverse_charge_tax"]) == 85.0
    assert float(row["output_tax"]) == 0.0
    assert float(row["net"]) == 0.0


def test_rate_change_uses_document_date(client, admin_headers):
    auth = admin_headers
    tc = _make_code(client, auth, code="HIST", rate=10)
    # Change rate effective 2026-07-01
    r = client.put(
        f"/api/tax-codes/{tc['id']}",
        headers=auth,
        json={"rate": 15, "effective_from": "2026-07-01"},
    )
    assert r.status_code == 200, r.text
    assert float(r.json()["rate"]) == 15.0

    hist = client.get(f"/api/tax-codes/{tc['id']}/rates", headers=auth).json()["items"]
    assert len(hist) >= 2

    before = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_name": "Before",
            "issue_date": "2026-06-30",
            "gst_rate": 0,
            "lines": [
                {"description": "A", "qty": 1, "rate": 100, "tax_code_id": tc["id"]},
            ],
        },
    )
    assert before.status_code == 201, before.text
    assert float(before.json()["gst_amount"]) == 10.0
    assert float(before.json()["lines"][0]["tax_rate"]) == 10.0

    after = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_name": "After",
            "issue_date": "2026-07-01",
            "gst_rate": 0,
            "lines": [
                {"description": "B", "qty": 1, "rate": 100, "tax_code_id": tc["id"]},
            ],
        },
    )
    assert after.status_code == 201, after.text
    assert float(after.json()["gst_amount"]) == 15.0
    assert float(after.json()["lines"][0]["tax_rate"]) == 15.0


def test_inclusive_line_splits_net_tax(client, admin_headers):
    auth = admin_headers
    tc = _make_code(client, auth, code="INC17", rate=17)
    inv = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_name": "Inclusive",
            "issue_date": "2026-06-01",
            "gst_rate": 0,
            "lines": [
                {
                    "description": "Gross",
                    "qty": 1,
                    "rate": 117,
                    "tax_code_id": tc["id"],
                    "tax_inclusive": True,
                },
            ],
        },
    )
    assert inv.status_code == 201, inv.text
    body = inv.json()
    assert float(body["subtotal"]) == 100.0
    assert float(body["gst_amount"]) == 17.0
    assert float(body["total"]) == 117.0
    assert float(body["lines"][0]["amount"]) == 100.0
    assert body["lines"][0]["tax_inclusive"] is True


def test_bill_input_tax_mirrors(client, admin_headers):
    auth = admin_headers
    tc = _make_code(client, auth, code="IN17", rate=17, ttype="input")
    bill = client.post(
        "/api/bills",
        headers=auth,
        json={
            "vendor_name": "Supplier",
            "bill_date": "2026-06-10",
            "gst_rate": 0,
            "lines": [
                {"description": "Parts", "qty": 2, "rate": 50, "tax_code_id": tc["id"]},
            ],
        },
    )
    assert bill.status_code == 201, bill.text
    body = bill.json()
    assert float(body["subtotal"]) == 100.0
    assert float(body["gst_amount"]) == 17.0
    assert float(body["total"]) == 117.0
    assert float(body["lines"][0]["tax_amount"]) == 17.0

    ret = client.get(
        "/api/reports/tax-return?start=2026-06-01&end=2026-06-30",
        headers=auth,
    ).json()
    row = next(r for r in ret["rows"] if r["code"] == "IN17")
    assert float(row["input_tax"]) == 17.0
    assert float(row["net"]) == -17.0


def test_uae_zero_rated_flag(client, admin_headers):
    r = client.post("/api/modules/uae_vat/install?seed_sample=true", headers=admin_headers)
    assert r.status_code == 200, r.text
    taxes = client.get("/api/tax-codes", headers=admin_headers).json()["items"]
    zero = next(t for t in taxes if t["code"] == "VAT0_OUT")
    assert zero["is_zero_rated"] is True
    assert float(zero["rate"]) == 0.0
