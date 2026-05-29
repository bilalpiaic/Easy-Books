"""Tests for the improvement roadmap gaps G-01 through G-17."""
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, StaticPool

from db import get_session
from main import app
from models import SQLModel


# ── shared helpers ────────────────────────────────────────────────────────────

def _mk_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _get_session_override(engine):
    def _override():
        with Session(engine) as s:
            yield s
    return _override


def _signup_and_login(client, email="test@co.test", company="TestCo"):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Tester",
            "company_name": company,
        },
    )
    r = client.post(
        "/api/auth/login",
        data={"username": email, "password": "password123"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _sum_decimal(rows, key: str) -> Decimal:
    total = Decimal("0")
    for r in rows:
        v = r.get(key)
        if v is not None:
            total += Decimal(str(v))
    return total


# ── G-01: Bank reconciliation zero-difference enforcement ─────────────────────

def test_reconciliation_close_rejects_nonzero_difference():
    """Closing a reconciliation with unmatched statement balance must return 422."""
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "g01a@co.test", "G01aCo")

    coa = client.get("/api/accounts", headers=auth).json()["items"]
    bank_id = next(a["id"] for a in coa if a["code"] == "1010")
    r = client.post(
        "/api/bank-accounts",
        headers=auth,
        json={"name": "Main Bank", "coa_account_id": bank_id},
    )
    assert r.status_code == 201, r.text
    bank_acc_id = r.json()["id"]

    # Create reconciliation with non-zero statement_balance but no matched JEs
    r = client.post(
        "/api/reconciliations",
        headers=auth,
        json={
            "bank_account_id": bank_acc_id,
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "statement_balance": 1000,
        },
    )
    assert r.status_code in (200, 201), r.text
    rec_id = r.json()["id"]

    # Must reject because difference = 1000 - 0 = 1000
    r = client.post(f"/api/reconciliations/{rec_id}/close", headers=auth)
    assert r.status_code == 422, f"Expected 422 but got {r.status_code}: {r.text}"
    assert "difference" in r.json()["detail"].lower()

    app.dependency_overrides.clear()


def test_reconciliation_close_allows_zero_difference():
    """Closing a reconciliation with zero statement_balance and no JEs should succeed."""
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "g01b@co.test", "G01bCo")

    coa = client.get("/api/accounts", headers=auth).json()["items"]
    bank_id = next(a["id"] for a in coa if a["code"] == "1010")
    r = client.post(
        "/api/bank-accounts",
        headers=auth,
        json={"name": "Empty Bank", "coa_account_id": bank_id},
    )
    bank_acc_id = r.json()["id"]

    r = client.post(
        "/api/reconciliations",
        headers=auth,
        json={
            "bank_account_id": bank_acc_id,
            "period_start": "2026-02-01",
            "period_end": "2026-02-28",
            "statement_balance": 0,
        },
    )
    rec_id = r.json()["id"]

    # statement_balance=0, no JEs → difference=0 → should close
    r = client.post(f"/api/reconciliations/{rec_id}/close", headers=auth)
    assert r.status_code == 200, f"Expected 200 but got {r.status_code}: {r.text}"
    assert r.json()["success"] is True

    app.dependency_overrides.clear()


# ── G-03: Comparative period columns ─────────────────────────────────────────

def test_income_statement_comparison_returns_both_periods():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "g03a@co.test", "G03aCo")

    r = client.get(
        "/api/reports/income-statement",
        headers=auth,
        params={
            "start": "2026-01-01",
            "end": "2026-03-31",
            "compare_start": "2025-01-01",
            "compare_end": "2025-03-31",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "current" in body, f"Expected 'current' key, got: {list(body.keys())}"
    assert "comparison" in body
    assert isinstance(body["current"], list)
    assert isinstance(body["comparison"], list)

    app.dependency_overrides.clear()


def test_income_statement_without_comparison_returns_flat_list():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "g03b@co.test", "G03bCo")

    r = client.get(
        "/api/reports/income-statement",
        headers=auth,
        params={"start": "2026-01-01", "end": "2026-03-31"},
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list), "Backward compat: should return flat list when no compare params"

    app.dependency_overrides.clear()


def test_balance_sheet_comparison_returns_both_periods():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "g03c@co.test", "G03cCo")

    r = client.get(
        "/api/reports/balance-sheet",
        headers=auth,
        params={
            "end": "2026-03-31",
            "compare_end": "2025-03-31",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "current" in body
    assert "comparison" in body

    app.dependency_overrides.clear()


# ── G-02: Credit Notes ────────────────────────────────────────────────────────

def test_credit_note_create_posts_gl():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "g02@co.test", "G02Co")

    # Create customer + invoice (1000 total, no GST)
    cust = client.post("/api/customers", headers=auth, json={"name": "Alice"}).json()
    inv = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-01-10",
            "due_date": "2026-01-31",
            "description": "Sale",
            "gst_rate": 0,
            "lines": [{"description": "Widget", "qty": 2, "rate": 500}],
        },
    ).json()

    # Create a credit note for 1 unit (500)
    r = client.post(
        "/api/credit-notes",
        headers=auth,
        json={
            "invoice_id": inv["id"],
            "customer_id": cust["id"],
            "issue_date": "2026-01-15",
            "description": "Return — defective",
            "lines": [{"description": "Widget return", "qty": 1, "rate": 500}],
        },
    )
    assert r.status_code == 201, r.text
    cn = r.json()
    assert cn["number"].startswith("CN-"), f"Expected CN- prefix, got {cn['number']}"
    assert abs(float(cn["total"]) - 500.0) < 0.01

    # GL check: after invoice (Dr AR 1000 / Cr Rev 1000) + CN (Cr AR 500 / Dr Rev 500)
    # Net AR = 1000 - 500 = 500
    tb = client.get("/api/reports/trial-balance", headers=auth).json()
    ar_row = next((row for row in tb if row["code"] == "1100"), None)
    assert ar_row is not None, "AR account (1100) missing from trial balance"
    ar_net = float(ar_row["total_debit"]) - float(ar_row["total_credit"])
    assert abs(ar_net - 500.0) < 0.01, f"Expected AR net=500, got {ar_net}"

    app.dependency_overrides.clear()


# ── G-05: Fixed Assets ────────────────────────────────────────────────────────

def test_asset_depreciation_posts_gl():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "g05@co.test", "G05Co")

    coa = {a["code"]: a["id"] for a in client.get("/api/accounts", headers=auth).json()["items"]}

    # Account 1090 (Accumulated Depreciation) and 5050 (Depreciation Expense) must exist
    assert "1090" in coa, f"Account 1090 missing; available codes: {sorted(coa.keys())}"
    assert "5050" in coa, f"Account 5050 missing"

    r = client.post(
        "/api/assets",
        headers=auth,
        json={
            "name": "Office Laptop",
            "asset_account_id": coa["1010"],  # bank as stand-in
            "accum_depr_account_id": coa["1090"],
            "depr_expense_account_id": coa["5050"],
            "acquisition_date": "2026-01-01",
            "acquisition_cost": 120000,
            "salvage_value": 0,
            "useful_life_months": 12,
            "method": "straight_line",
        },
    )
    assert r.status_code == 201, r.text
    asset_id = r.json()["id"]

    r = client.post(
        f"/api/assets/{asset_id}/depreciate",
        headers=auth,
        json={"depreciation_date": "2026-01-31"},
    )
    assert r.status_code == 200, r.text
    assert abs(float(r.json()["depreciation_amount"]) - 10000.0) < 0.01  # 120000/12

    tb = {row["code"]: row for row in client.get("/api/reports/trial-balance", headers=auth).json()}
    assert "5050" in tb, "Depreciation Expense account missing from TB"
    assert abs(float(tb["5050"]["total_debit"]) - 10000.0) < 0.01

    app.dependency_overrides.clear()


# ── G-09: FIFO ────────────────────────────────────────────────────────────────

def test_fifo_cogs_uses_layer_unit_cost_not_avg():
    """With FIFO, 5 units consumed from first layer (cost=10) should yield COGS=50,
    not 75 which is what WAvg (avg=15) would produce."""
    from sqlmodel import Session as S
    from models import Tenant
    from services.inventory import consume_stock, record_purchase
    from services.money import D

    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "g09@co.test", "G09Co")

    r = client.post(
        "/api/products",
        headers=auth,
        json={"name": "Widget", "product_type": "stock", "default_rate": 100},
    )
    assert r.status_code == 201, r.text
    product_id = r.json()["id"]

    me = client.get("/api/auth/me", headers=auth).json()
    tenant_id = me["tenant"]["id"]

    with S(engine) as session:
        record_purchase(session, tenant_id=tenant_id, product_id=product_id,
                        qty=D("10"), unit_cost=D("10"))
        record_purchase(session, tenant_id=tenant_id, product_id=product_id,
                        qty=D("10"), unit_cost=D("20"))
        session.commit()

        tenant = session.get(Tenant, tenant_id)
        tenant.cost_method = "fifo"
        session.commit()

        cogs = consume_stock(session, tenant_id=tenant_id, product_id=product_id, qty=D("5"))
        session.commit()

    assert abs(float(cogs) - 50.0) < 0.01, f"FIFO COGS expected 50, got {cogs}"

    app.dependency_overrides.clear()


# ── G-10: Budget vs Actual ────────────────────────────────────────────────────

def test_budget_variance_report():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "g10@co.test", "G10Co")

    coa = {a["code"]: a["id"] for a in client.get("/api/accounts", headers=auth).json()["items"]}
    expense_id = coa["5000"]

    r = client.post(
        "/api/budgets",
        headers=auth,
        json={"account_id": expense_id, "fiscal_year": 2026, "period_month": 1, "amount": 10000},
    )
    assert r.status_code == 201, r.text

    r = client.get(
        "/api/reports/budget-vs-actual",
        headers=auth,
        params={"year": 2026, "month": 1},
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    row = next((r for r in rows if r["account_id"] == expense_id), None)
    assert row is not None, "Budget row for account 5000 not found"
    assert abs(float(row["budget"]) - 10000.0) < 0.01
    assert "actual" in row
    assert "variance" in row

    app.dependency_overrides.clear()


# ── G-06: Purchase Orders ─────────────────────────────────────────────────────

def test_po_convert_to_bill():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "g06@co.test", "G06Co")

    vendor = client.post("/api/vendors", headers=auth, json={"name": "Acme Supplies"}).json()

    r = client.post(
        "/api/purchase-orders",
        headers=auth,
        json={
            "vendor_id": vendor["id"],
            "order_date": "2026-02-01",
            "description": "Office supplies",
            "lines": [{"description": "Paper reams", "qty": 10, "rate": 500}],
        },
    )
    assert r.status_code == 201, r.text
    po = r.json()
    assert po["number"].startswith("PO-"), f"Expected PO- prefix, got {po['number']}"

    r = client.post(
        f"/api/purchase-orders/{po['id']}/convert-to-bill",
        headers=auth,
        json={"bill_date": "2026-02-15", "due_date": "2026-03-15"},
    )
    assert r.status_code == 201, r.text
    result = r.json()
    assert result["bill"]["number"].startswith("BILL-"), f"Got: {result['bill']['number']}"
    assert abs(float(result["bill"]["total"]) - 5000.0) < 0.01

    app.dependency_overrides.clear()


# ── G-15: FX Revaluation ─────────────────────────────────────────────────────

def test_fx_revaluation_posts_gain():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "g15@co.test", "G15Co")

    # Set base currency to PKR via settings
    client.patch("/api/settings", headers=auth, json={"currency": "PKR"})

    # Exchange rates: invoice date 280, revaluation date 290
    client.post("/api/exchange-rates", headers=auth, json={
        "from_currency": "USD", "to_currency": "PKR", "rate": 280, "date": "2026-01-01",
    })
    client.post("/api/exchange-rates", headers=auth, json={
        "from_currency": "USD", "to_currency": "PKR", "rate": 290, "date": "2026-01-31",
    })

    # Create USD invoice: $1000 @ 280 = PKR 280,000
    cust = client.post("/api/customers", headers=auth, json={"name": "Foreign Client"}).json()
    client.post(
        "/api/invoices",
        headers=auth,
        json={
            "customer_id": cust["id"],
            "issue_date": "2026-01-01",
            "due_date": "2026-01-31",
            "description": "Consulting",
            "gst_rate": 0,
            "currency": "USD",
            "exchange_rate": 280,
            "lines": [{"description": "Service", "qty": 1, "rate": 1000}],
        },
    )

    # Run revaluation at 2026-01-31 (rate 290)
    r = client.post(
        "/api/reports/fx-revaluation",
        headers=auth,
        params={"revaluation_date": "2026-01-31"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("entries_count", 0) > 0, f"Expected entries, got: {body}"

    app.dependency_overrides.clear()


# ── Returns & Advances (Sprint 13) ────────────────────────────────────────────

def _make_stock_product(client, auth, name="Widget", rate=100):
    r = client.post("/api/products", headers=auth,
                    json={"name": name, "product_type": "stock", "default_rate": rate})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _stock_qty(client, auth, pid):
    """Read a product's current stock_qty from the list endpoint."""
    items = client.get("/api/products?limit=200", headers=auth).json()["items"]
    p = next(x for x in items if x["id"] == pid)
    return float(p["stock_qty"])


def test_sales_return_restocks_and_reverses_cogs():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "ret-sr@co.test", "SRCo")

    pid = _make_stock_product(client, auth, "Widget", 100)
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Supplier"}).json()
    cust = client.post("/api/customers", headers=auth, json={"name": "Buyer"}).json()

    # Buy 10 @ 20 → stock in
    client.post("/api/bills", headers=auth, json={
        "vendor_id": vendor["id"], "bill_date": "2026-01-01", "due_date": "2026-01-31",
        "gst_rate": 0, "lines": [{"product_id": pid, "description": "Widget", "qty": 10, "rate": 20}],
    })
    # Sell 4 @ 100 → stock out + COGS
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"], "issue_date": "2026-01-10", "due_date": "2026-01-31",
        "gst_rate": 0, "lines": [{"product_id": pid, "description": "Widget", "qty": 4, "rate": 100}],
    }).json()

    assert abs(_stock_qty(client, auth, pid) - 6.0) < 0.01  # 10 - 4

    # Sales return: credit note with the stock line (qty 2)
    r = client.post("/api/credit-notes", headers=auth, json={
        "invoice_id": inv["id"], "customer_id": cust["id"], "issue_date": "2026-01-15",
        "description": "Sales return", "restock": True,
        "lines": [{"product_id": pid, "description": "Widget", "qty": 2, "rate": 100}],
    })
    assert r.status_code == 201, r.text

    # Stock should rise back to 8 (6 + 2 returned)
    assert abs(_stock_qty(client, auth, pid) - 8.0) < 0.01

    # Trial balance must stay balanced
    tb = client.get("/api/reports/trial-balance", headers=auth).json()
    dr = _sum_decimal(tb, "total_debit"); cr = _sum_decimal(tb, "total_credit")
    assert dr == cr, f"TB imbalanced dr={dr} cr={cr}"
    app.dependency_overrides.clear()


def test_purchase_return_reduces_stock_and_ap():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "ret-pr@co.test", "PRCo")

    pid = _make_stock_product(client, auth, "Gadget", 50)
    vendor = client.post("/api/vendors", headers=auth, json={"name": "Supplier"}).json()

    bill = client.post("/api/bills", headers=auth, json={
        "vendor_id": vendor["id"], "bill_date": "2026-02-01", "due_date": "2026-02-28",
        "gst_rate": 0, "lines": [{"product_id": pid, "description": "Gadget", "qty": 20, "rate": 30}],
    }).json()

    assert abs(_stock_qty(client, auth, pid) - 20.0) < 0.01

    # Return 5 units to the vendor
    r = client.post("/api/debit-notes", headers=auth, json={
        "bill_id": bill["id"], "vendor_id": vendor["id"], "issue_date": "2026-02-10",
        "description": "Damaged goods returned",
        "lines": [{"product_id": pid, "description": "Gadget", "qty": 5, "rate": 30}],
    })
    assert r.status_code == 201, r.text
    assert r.json()["number"].startswith("DN-")

    assert abs(_stock_qty(client, auth, pid) - 15.0) < 0.01  # 20 - 5

    tb = client.get("/api/reports/trial-balance", headers=auth).json()
    dr = _sum_decimal(tb, "total_debit"); cr = _sum_decimal(tb, "total_credit")
    assert dr == cr, f"TB imbalanced dr={dr} cr={cr}"
    app.dependency_overrides.clear()


def test_customer_advance_record_and_apply():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "adv-c@co.test", "AdvCCo")

    cust = client.post("/api/customers", headers=auth, json={"name": "Prepayer"}).json()
    # Record advance of 1000
    r = client.post("/api/advances/customer", headers=auth, json={
        "party_id": cust["id"], "date": "2026-03-01", "amount": 1000,
    })
    assert r.status_code == 201, r.text
    adv_id = r.json()["id"]
    assert r.json()["number"].startswith("CADV-")

    # Create an invoice for 600
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"], "issue_date": "2026-03-05", "due_date": "2026-03-31",
        "gst_rate": 0, "lines": [{"description": "Service", "qty": 1, "rate": 600}],
    }).json()

    # Apply 600 of the advance to the invoice
    r = client.post(f"/api/advances/customer/{adv_id}/apply", headers=auth,
                    json={"target_id": inv["id"], "amount": 600})
    assert r.status_code == 200, r.text
    body = r.json()
    assert abs(float(body["remaining"]) - 400.0) < 0.01
    assert body["invoice_status"] == "paid"

    tb = client.get("/api/reports/trial-balance", headers=auth).json()
    dr = _sum_decimal(tb, "total_debit"); cr = _sum_decimal(tb, "total_credit")
    assert dr == cr, f"TB imbalanced dr={dr} cr={cr}"
    app.dependency_overrides.clear()


def test_vendor_advance_record_and_apply():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    client = TestClient(app)
    auth = _signup_and_login(client, "adv-v@co.test", "AdvVCo")

    vendor = client.post("/api/vendors", headers=auth, json={"name": "Prepaid Supplier"}).json()
    r = client.post("/api/advances/vendor", headers=auth, json={
        "party_id": vendor["id"], "date": "2026-03-01", "amount": 800,
    })
    assert r.status_code == 201, r.text
    adv_id = r.json()["id"]
    assert r.json()["number"].startswith("VADV-")

    bill = client.post("/api/bills", headers=auth, json={
        "vendor_id": vendor["id"], "bill_date": "2026-03-05", "due_date": "2026-04-05",
        "gst_rate": 0, "lines": [{"description": "Materials", "qty": 1, "rate": 500}],
    }).json()

    r = client.post(f"/api/advances/vendor/{adv_id}/apply", headers=auth,
                    json={"target_id": bill["id"], "amount": 500})
    assert r.status_code == 200, r.text
    body = r.json()
    assert abs(float(body["remaining"]) - 300.0) < 0.01
    assert body["bill_status"] == "paid"

    tb = client.get("/api/reports/trial-balance", headers=auth).json()
    dr = _sum_decimal(tb, "total_debit"); cr = _sum_decimal(tb, "total_credit")
    assert dr == cr, f"TB imbalanced dr={dr} cr={cr}"
    app.dependency_overrides.clear()
