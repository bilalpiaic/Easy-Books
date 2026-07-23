"""V2.4 tests: GRN + ProductionOrder full lifecycle.

Covers:
- GRN creation: validation, custodial movement + layer, memo JE (if declared)
- PO create from BoM + Customer + RatePlan
- PO state machine: draft → started → completed → delivered → billed
- JE balanced at every stage
- Customer-supplied materials stay off-balance-sheet (memo only)
- Bill amount applies materials passthrough + overhead + margin correctly
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from db import get_session
from main import app
from models import (
    Account, GoodsReceiptNote, GRNLine, InventoryLayer, JournalEntry,
    Product, ProductionOrder, StockMovement, Transaction,
)


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as session:
            yield session

    app.state.engine = engine
    app.dependency_overrides[get_session] = _override
    client = TestClient(app)
    yield client, engine
    app.dependency_overrides.clear()
    if hasattr(app.state, "engine"):
        delattr(app.state, "engine")
    engine.dispose()


def _signup(c: TestClient, model: str, email: str) -> dict:
    c.post(
        "/api/auth/signup",
        json={
            "email": email, "password": "password123",
            "full_name": "U", "company_name": "Co",
            "business_model": model,
        },
    )
    r = c.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_product(c, auth, code, default_rate=0):
    return c.post(
        "/api/products", headers=auth,
        json={
            "code": code, "name": code, "unit": "ea",
            "product_type": "stock", "default_rate": default_rate,
        },
    ).json()


def _make_customer(c, auth, name):
    return c.post("/api/customers", headers=auth, json={"name": name}).json()


def _make_vendor(c, auth, name):
    return c.post("/api/vendors", headers=auth, json={"name": name}).json()


def _buy(c, auth, vendor_id, prod, qty, rate, date="2026-05-01"):
    return c.post(
        "/api/bills", headers=auth,
        json={
            "vendor_id": vendor_id, "bill_date": date, "due_date": "2026-05-31",
            "gst_rate": 0,
            "lines": [{"product_id": prod["id"], "description": "buy",
                       "qty": qty, "rate": rate}],
        },
    ).json()


# ── GRN ─────────────────────────────────────────────────────────────────────


def test_grn_records_custodial_movement(client):
    c, engine = client
    auth = _signup(c, "manufacturing", "g1@m.test")
    cust = _make_customer(c, auth, "Brand Co.")
    fabric = _make_product(c, auth, "FABRIC")

    r = c.post(
        "/api/grn", headers=auth,
        json={
            "customer_id": cust["id"], "received_date": "2026-05-10",
            "lines": [{"product_id": fabric["id"], "qty": 100, "lot_no": "LOT-A"}],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["number"].startswith("GRN-")
    assert len(body["lines"]) == 1

    with Session(engine) as s:
        mv = s.exec(
            select(StockMovement).where(StockMovement.direction == "CUSTODIAL_RECEIPT")
        ).first()
        assert mv is not None
        assert mv.posted_to_gl is False
        assert mv.owner_customer_id == cust["id"]
        # No JE since declared_value defaulted to 0
        assert s.exec(select(Transaction)).first() is None


def test_grn_with_declared_value_posts_memo_je(client):
    c, engine = client
    auth = _signup(c, "manufacturing", "g2@m.test")
    cust = _make_customer(c, auth, "Brand Co.")
    fabric = _make_product(c, auth, "FABRIC")

    r = c.post(
        "/api/grn", headers=auth,
        json={
            "customer_id": cust["id"], "received_date": "2026-05-10",
            "lines": [{"product_id": fabric["id"], "qty": 50, "declared_value": "500"}],
        },
    )
    assert r.status_code == 201, r.text

    with Session(engine) as s:
        txn = s.exec(select(Transaction)).first()
        assert txn is not None
        jes = s.exec(select(JournalEntry).where(JournalEntry.transaction_id == txn.id)).all()
        assert len(jes) == 2
        # Both rows hit memo accounts
        acc_ids = {j.account_id for j in jes}
        memo_accs = s.exec(
            select(Account).where(Account.id.in_(acc_ids))
        ).all()
        assert all(a.is_memo for a in memo_accs)
        total_dr = sum(Decimal(str(j.debit)) for j in jes)
        total_cr = sum(Decimal(str(j.credit)) for j in jes)
        assert total_dr == total_cr == Decimal("500")


def test_grn_rejects_non_custodial_location(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "g3@m.test")
    cust = _make_customer(c, auth, "X")
    fabric = _make_product(c, auth, "F")
    main = next(
        l for l in c.get("/api/stock-locations", headers=auth).json()["items"]
        if l["code"] == "MAIN"
    )
    r = c.post(
        "/api/grn", headers=auth,
        json={
            "customer_id": cust["id"], "received_date": "2026-05-10",
            "location_id": main["id"],
            "lines": [{"product_id": fabric["id"], "qty": 1}],
        },
    )
    assert r.status_code == 400


def test_grn_rejects_empty_lines(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "g4@m.test")
    cust = _make_customer(c, auth, "X")
    r = c.post(
        "/api/grn", headers=auth,
        json={"customer_id": cust["id"], "received_date": "2026-05-10", "lines": []},
    )
    assert r.status_code == 400


# ── PO create + state machine guards ────────────────────────────────────────


def test_create_po_requires_valid_bom_and_customer(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "po1@m.test")
    cust = _make_customer(c, auth, "Brand")
    r = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": 999, "customer_id": cust["id"], "output_qty": 10},
    )
    assert r.status_code == 400


def test_po_cancel_only_from_draft(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "po2@m.test")
    cust = _make_customer(c, auth, "Brand")
    out = _make_product(c, auth, "OUT")
    raw = _make_product(c, auth, "RAW")
    bom = c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": out["id"], "output_qty": 1,
            "lines": [{"component_product_id": raw["id"], "qty_per_output": 1, "source": "own_stock"}],
        },
    ).json()
    po = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 5},
    ).json()
    r = c.post(f"/api/production-orders/{po['id']}/cancel", headers=auth)
    assert r.status_code == 200
    assert r.json()["state"] == "cancelled"


def test_po_start_requires_stock(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "po3@m.test")
    cust = _make_customer(c, auth, "Brand")
    out = _make_product(c, auth, "OUT")
    raw = _make_product(c, auth, "RAW")
    bom = c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": out["id"],
            "lines": [{"component_product_id": raw["id"], "qty_per_output": 2, "source": "own_stock"}],
        },
    ).json()
    po = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 10},
    ).json()
    # No stock purchased yet → start should fail
    r = c.post(f"/api/production-orders/{po['id']}/start", headers=auth)
    assert r.status_code == 400


# ── Full lifecycle ──────────────────────────────────────────────────────────


def _scenario_full_chain(c, auth):
    """Build a scenario:
      - 1 customer with declared GRN of fabric (50 units, value 500)
      - 1 BoM: output WIDGET, consumes 2 BUTTON (own) + 1 FABRIC (customer_supplied)
      - 1 RatePlan: $10/unit, includes materials at cost, 5% overhead, 10% margin
      - Buy 100 BUTTON @ $1
      - Customer assigned to plan
    Returns (cust, out, raw, fabric, bom, plan)
    """
    cust = _make_customer(c, auth, "Brand Co.")
    out = _make_product(c, auth, "WIDGET")
    button = _make_product(c, auth, "BUTTON")
    fabric = _make_product(c, auth, "FABRIC")

    vendor = _make_vendor(c, auth, "Acme")
    _buy(c, auth, vendor["id"], button, qty=100, rate=1)

    bom = c.post(
        "/api/bom", headers=auth,
        json={
            "output_product_id": out["id"], "output_qty": 1,
            "lines": [
                {"component_product_id": button["id"], "qty_per_output": 2, "source": "own_stock"},
                {"component_product_id": fabric["id"], "qty_per_output": 1, "source": "customer_supplied"},
            ],
        },
    ).json()
    plan = c.post(
        "/api/rate-plans", headers=auth,
        json={
            "code": "STITCH", "name": "Stitching", "per_unit_rate": "10",
            "includes_materials_at_cost": True,
            "overhead_pct": "5", "margin_pct": "10",
        },
    ).json()
    c.post(
        "/api/rate-plans/assign", headers=auth,
        json={"customer_id": cust["id"], "rate_plan_id": plan["id"]},
    )
    # Customer brings 30 fabric
    c.post(
        "/api/grn", headers=auth,
        json={
            "customer_id": cust["id"], "received_date": "2026-05-10",
            "lines": [{"product_id": fabric["id"], "qty": 30, "lot_no": "LOT-F1",
                       "declared_value": "300"}],
        },
    )
    return cust, out, button, fabric, bom, plan


def test_full_lifecycle_through_billing(client):
    c, engine = client
    auth = _signup(c, "manufacturing", "full@m.test")
    cust, out, button, fabric, bom, plan = _scenario_full_chain(c, auth)

    # Produce 10 widgets — needs 20 buttons + 10 fabric
    po = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 10},
    ).json()
    assert po["state"] == "draft"
    assert po["rate_plan_id"] == plan["id"]   # auto-resolved from customer

    # Start
    r = c.post(f"/api/production-orders/{po['id']}/start", headers=auth)
    assert r.status_code == 200, r.text
    started = r.json()
    assert started["state"] == "started"
    assert Decimal(str(started["own_material_cost"])) == Decimal("20")  # 20 buttons × $1

    # Complete
    r = c.post(f"/api/production-orders/{po['id']}/complete", headers=auth)
    assert r.status_code == 200, r.text
    completed = r.json()
    assert completed["state"] == "completed"
    assert Decimal(str(completed["output_unit_cost"])) == Decimal("2")  # $20 / 10

    # Deliver
    r = c.post(f"/api/production-orders/{po['id']}/deliver", headers=auth)
    assert r.status_code == 200, r.text
    delivered = r.json()
    assert delivered["state"] == "delivered"

    # Bill
    r = c.post(f"/api/production-orders/{po['id']}/bill", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["production_order"]["state"] == "billed"
    inv = body["invoice"]
    # Expected:
    #   base = 10 × $10 = $100
    #   materials = $20
    #   subtotal_pre = $120
    #   overhead = 5% × 120 = $6
    #   subtotal = $126
    #   margin = 10% × 126 = $12.60
    #   total = $138.60
    assert Decimal(str(inv["total"])) == Decimal("138.60")

    # Verify every JE balances
    with Session(engine) as s:
        txns = s.exec(select(Transaction)).all()
        assert len(txns) >= 4  # GRN memo + start + complete + deliver-cogs + deliver-memo + bill
        for t in txns:
            jes = s.exec(select(JournalEntry).where(JournalEntry.transaction_id == t.id)).all()
            dr = sum(Decimal(str(j.debit)) for j in jes)
            cr = sum(Decimal(str(j.credit)) for j in jes)
            assert dr == cr, f"Txn {t.jv_number} unbalanced: dr={dr} cr={cr}"


def test_customer_supplied_components_do_not_hit_gl(client):
    c, engine = client
    auth = _signup(c, "manufacturing", "memo@m.test")
    cust, out, button, fabric, bom, plan = _scenario_full_chain(c, auth)

    po = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 10},
    ).json()
    c.post(f"/api/production-orders/{po['id']}/start", headers=auth)

    with Session(engine) as s:
        # CUSTODIAL_ISSUE movement exists and is posted_to_gl=False
        mv = s.exec(
            select(StockMovement).where(StockMovement.direction == "CUSTODIAL_ISSUE")
        ).first()
        assert mv is not None
        assert mv.posted_to_gl is False
        # No JE references fabric on the start txn — only own_stock JE
        # (start posts exactly 2 entries: Dr WIP / Cr Raw Material for $20)
        start_txn = s.exec(
            select(Transaction).where(Transaction.description.like("%issue to WIP%"))
        ).first()
        assert start_txn is not None
        jes = s.exec(
            select(JournalEntry).where(JournalEntry.transaction_id == start_txn.id)
        ).all()
        assert len(jes) == 2
        total = sum(Decimal(str(j.debit)) for j in jes)
        assert total == Decimal("20")


def test_partial_grn_fabric_used_only_partially(client):
    """Customer brought 30 fabric, we use 10 — memo not released yet."""
    c, engine = client
    auth = _signup(c, "manufacturing", "part@m.test")
    cust, out, button, fabric, bom, plan = _scenario_full_chain(c, auth)

    po = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 10},
    ).json()
    c.post(f"/api/production-orders/{po['id']}/start", headers=auth)
    c.post(f"/api/production-orders/{po['id']}/complete", headers=auth)
    c.post(f"/api/production-orders/{po['id']}/deliver", headers=auth)

    with Session(engine) as s:
        # GRN layer still has 20 remaining → declared_value NOT released
        grn = s.exec(select(GoodsReceiptNote)).first()
        assert Decimal(str(grn.declared_value)) == Decimal("300")  # untouched
        layer = s.exec(
            select(InventoryLayer).where(
                InventoryLayer.product_id == fabric["id"],
                InventoryLayer.owner_customer_id == cust["id"],
            )
        ).first()
        assert Decimal(str(layer.qty_remaining)) == Decimal("20")


def test_bill_requires_delivered_state(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "billg@m.test")
    cust, out, button, fabric, bom, plan = _scenario_full_chain(c, auth)
    po = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 10},
    ).json()
    r = c.post(f"/api/production-orders/{po['id']}/bill", headers=auth)
    assert r.status_code == 400


def test_cannot_skip_states(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "skip@m.test")
    cust, out, button, fabric, bom, plan = _scenario_full_chain(c, auth)
    po = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 10},
    ).json()
    # Cannot complete before start
    r = c.post(f"/api/production-orders/{po['id']}/complete", headers=auth)
    assert r.status_code == 400
    # Cannot deliver from draft
    r = c.post(f"/api/production-orders/{po['id']}/deliver", headers=auth)
    assert r.status_code == 400


def test_po_tenant_isolation(client):
    c, _ = client
    auth_a = _signup(c, "manufacturing", "ia@m.test")
    auth_b = _signup(c, "manufacturing", "ib@m.test")
    cust_a, _, _, _, bom_a, _ = _scenario_full_chain(c, auth_a)
    po_a = c.post(
        "/api/production-orders", headers=auth_a,
        json={"bom_id": bom_a["id"], "customer_id": cust_a["id"], "output_qty": 5},
    ).json()
    r = c.get(f"/api/production-orders/{po_a['id']}", headers=auth_b)
    assert r.status_code == 404
    r = c.post(f"/api/production-orders/{po_a['id']}/start", headers=auth_b)
    assert r.status_code == 404


def test_list_pos_filters_by_state(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "fil@m.test")
    cust, out, button, fabric, bom, plan = _scenario_full_chain(c, auth)
    po1 = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 5},
    ).json()
    po2 = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 5},
    ).json()
    c.post(f"/api/production-orders/{po1['id']}/cancel", headers=auth)
    r = c.get("/api/production-orders?state=draft", headers=auth)
    assert all(p["state"] == "draft" for p in r.json()["items"])
    r = c.get("/api/production-orders?state=cancelled", headers=auth)
    assert all(p["state"] == "cancelled" for p in r.json()["items"])

# ── Reverse (#221) ───────────────────────────────────────────────────────────


def test_po_reverse_from_started_restores_components(client):
    c, engine = client
    auth = _signup(c, "manufacturing", "rev1@m.test")
    cust, out, button, fabric, bom, plan = _scenario_full_chain(c, auth)
    po = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 10},
    ).json()
    assert c.post(f"/api/production-orders/{po['id']}/start", headers=auth).status_code == 200

    with Session(engine) as s:
        btn = s.exec(select(Product).where(Product.code == "BUTTON")).first()
        assert Decimal(str(btn.stock_qty)) == Decimal("80")  # 100 − 20

    r = c.post(f"/api/production-orders/{po['id']}/reverse", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "cancelled"
    assert body["from_state"] == "started"

    with Session(engine) as s:
        btn = s.exec(select(Product).where(Product.code == "BUTTON")).first()
        assert Decimal(str(btn.stock_qty)) == Decimal("100")
        start_txn = s.exec(
            select(Transaction).where(Transaction.description.like("%issue to WIP%"))
        ).first()
        assert start_txn is not None
        assert start_txn.is_reversed is True
        cust_layers = s.exec(
            select(InventoryLayer).where(
                InventoryLayer.owner_customer_id != None,  # noqa: E711
                InventoryLayer.qty_remaining > 0,
            )
        ).all()
        fabric_remaining = sum(Decimal(str(l.qty_remaining)) for l in cust_layers)
        assert fabric_remaining == Decimal("30")


def test_po_reverse_from_delivered_unwinds_all_stages(client):
    c, engine = client
    auth = _signup(c, "manufacturing", "rev2@m.test")
    cust, out, button, fabric, bom, plan = _scenario_full_chain(c, auth)
    po = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 10},
    ).json()
    assert c.post(f"/api/production-orders/{po['id']}/start", headers=auth).status_code == 200
    assert c.post(f"/api/production-orders/{po['id']}/complete", headers=auth).status_code == 200
    assert c.post(f"/api/production-orders/{po['id']}/deliver", headers=auth).status_code == 200

    r = c.post(f"/api/production-orders/{po['id']}/reverse", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "cancelled"
    assert body["from_state"] == "delivered"
    assert len(body["reversed_jvs"]) >= 1

    with Session(engine) as s:
        btn = s.exec(select(Product).where(Product.code == "BUTTON")).first()
        widget = s.exec(select(Product).where(Product.code == "WIDGET")).first()
        assert Decimal(str(btn.stock_qty)) == Decimal("100")
        assert Decimal(str(widget.stock_qty)) == Decimal("0")
        for suffix in ("issue to WIP", "capitalise FG", "deliver / COGS"):
            txn = s.exec(
                select(Transaction).where(Transaction.description.like(f"%{suffix}%"))
            ).first()
            assert txn is not None, suffix
            assert txn.is_reversed is True, suffix


def test_po_reverse_rejects_draft_and_billed(client):
    c, _ = client
    auth = _signup(c, "manufacturing", "rev3@m.test")
    cust, out, button, fabric, bom, plan = _scenario_full_chain(c, auth)
    po = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 5},
    ).json()
    r = c.post(f"/api/production-orders/{po['id']}/reverse", headers=auth)
    assert r.status_code == 400

    assert c.post(f"/api/production-orders/{po['id']}/start", headers=auth).status_code == 200
    assert c.post(f"/api/production-orders/{po['id']}/complete", headers=auth).status_code == 200
    assert c.post(f"/api/production-orders/{po['id']}/deliver", headers=auth).status_code == 200
    assert c.post(f"/api/production-orders/{po['id']}/bill", headers=auth).status_code == 200
    r = c.post(f"/api/production-orders/{po['id']}/reverse", headers=auth)
    assert r.status_code == 400
    assert "invoice" in r.json()["detail"].lower()


# ── #222 absorption + partial delivery ──────────────────────────────────────


def test_po_start_absorbs_labour_and_overhead(client):
    c, engine = client
    auth = _signup(c, "manufacturing", "abs1@m.test")
    cust, out, button, fabric, bom, plan = _scenario_full_chain(c, auth)
    c.put(
        f"/api/rate-plans/{plan['id']}", headers=auth,
        json={"labour_per_unit": "3", "overhead_per_unit": "1.5"},
    )
    po = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 10},
    ).json()
    r = c.post(f"/api/production-orders/{po['id']}/start", headers=auth)
    assert r.status_code == 200, r.text
    started = r.json()
    assert Decimal(str(started["labour_cost"])) == Decimal("30")
    assert Decimal(str(started["overhead_cost"])) == Decimal("15")

    with Session(engine) as s:
        labour = s.exec(
            select(Transaction).where(Transaction.description.like("%absorb labour%"))
        ).first()
        oh = s.exec(
            select(Transaction).where(Transaction.description.like("%absorb overhead%"))
        ).first()
        assert labour is not None and labour.is_reversed is False
        assert oh is not None and oh.is_reversed is False
        # WIP debits: materials 20 + labour 30 + overhead 15
        jes = s.exec(select(JournalEntry)).all()
        wip = s.exec(select(Account).where(Account.code == "1201")).first()
        assert wip is not None
        wip_debit = sum(
            Decimal(str(je.debit)) for je in jes if je.account_id == wip.id
        )
        assert wip_debit == Decimal("65")

    r = c.post(f"/api/production-orders/{po['id']}/complete", headers=auth)
    assert r.status_code == 200
    completed = r.json()
    assert Decimal(str(completed["output_unit_cost"])) == Decimal("6.5")  # 65 / 10


def test_po_partial_delivery_keeps_completed_until_full(client):
    c, engine = client
    auth = _signup(c, "manufacturing", "part1@m.test")
    cust, out, button, fabric, bom, plan = _scenario_full_chain(c, auth)
    po = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 10},
    ).json()
    assert c.post(f"/api/production-orders/{po['id']}/start", headers=auth).status_code == 200
    assert c.post(f"/api/production-orders/{po['id']}/complete", headers=auth).status_code == 200

    r = c.post(
        f"/api/production-orders/{po['id']}/deliver", headers=auth,
        json={"qty": "4"},
    )
    assert r.status_code == 200, r.text
    mid = r.json()
    assert mid["state"] == "completed"
    assert Decimal(str(mid["delivered_qty"])) == Decimal("4")

    r = c.post(f"/api/production-orders/{po['id']}/bill", headers=auth)
    assert r.status_code == 400  # still completed, not fully delivered

    r = c.post(
        f"/api/production-orders/{po['id']}/deliver", headers=auth,
        json={"qty": "7"},
    )
    assert r.status_code == 400  # exceeds remaining 6

    r = c.post(
        f"/api/production-orders/{po['id']}/deliver", headers=auth,
        json={"qty": "6"},
    )
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["state"] == "delivered"
    assert Decimal(str(done["delivered_qty"])) == Decimal("10")

    with Session(engine) as s:
        widget = s.exec(select(Product).where(Product.code == "WIDGET")).first()
        assert Decimal(str(widget.stock_qty)) == Decimal("0")
        deliver_txns = s.exec(
            select(Transaction).where(Transaction.description.like("%deliver / COGS%"))
        ).all()
        assert len(deliver_txns) == 2


def test_po_reverse_partial_delivery_restores_delivered_qty(client):
    c, engine = client
    auth = _signup(c, "manufacturing", "partrev@m.test")
    cust, out, button, fabric, bom, plan = _scenario_full_chain(c, auth)
    c.put(
        f"/api/rate-plans/{plan['id']}", headers=auth,
        json={"labour_per_unit": "2", "overhead_per_unit": "1"},
    )
    po = c.post(
        "/api/production-orders", headers=auth,
        json={"bom_id": bom["id"], "customer_id": cust["id"], "output_qty": 10},
    ).json()
    assert c.post(f"/api/production-orders/{po['id']}/start", headers=auth).status_code == 200
    assert c.post(f"/api/production-orders/{po['id']}/complete", headers=auth).status_code == 200
    assert c.post(
        f"/api/production-orders/{po['id']}/deliver", headers=auth, json={"qty": "3"},
    ).status_code == 200

    r = c.post(f"/api/production-orders/{po['id']}/reverse", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "cancelled"
    assert body["from_state"] == "completed"

    with Session(engine) as s:
        widget = s.exec(select(Product).where(Product.code == "WIDGET")).first()
        btn = s.exec(select(Product).where(Product.code == "BUTTON")).first()
        assert Decimal(str(widget.stock_qty)) == Decimal("0")
        assert Decimal(str(btn.stock_qty)) == Decimal("100")
        for suffix in ("absorb labour", "absorb overhead", "deliver / COGS", "capitalise FG"):
            txn = s.exec(
                select(Transaction).where(Transaction.description.like(f"%{suffix}%"))
            ).first()
            assert txn is not None, suffix
            assert txn.is_reversed is True, suffix
