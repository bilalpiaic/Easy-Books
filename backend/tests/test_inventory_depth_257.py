"""#257 Inventory depth: landed cost allocation, lot/serial, NRV JE."""
from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import InventoryLayer, JournalEntry, LandedCostAllocation, Product, StockSerial, Transaction
from services.inventory import InventoryError, consume_stock, record_purchase
from services.landed_cost import plan_allocation
from services.money import D


def _auth(client: TestClient, email: str, company: str = "InvDepth"):
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": company,
            "business_model": "trader",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _stock_product(client, auth, *, name="Widget", track_lot=False, track_serial=False, nrv=None):
    body = {
        "name": name,
        "product_type": "stock",
        "unit": "pcs",
        "default_rate": 20,
        "track_lot": track_lot,
        "track_serial": track_serial,
        "opening_qty": 0,
        "opening_cost": 0,
    }
    if nrv is not None:
        body["nrv_unit"] = nrv
    r = client.post("/api/products", headers=auth, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_landed_cost_allocation_math_and_post(client: TestClient):
    auth = _auth(client, "lc@inv.test", "LcCo")
    p = _stock_product(client, auth, name="Bolt")

    # Receive via record_purchase in-session (bill would also work)
    session = Session(client.app.state.engine)
    from models import User
    user = session.exec(select(User)).first()
    assert user
    record_purchase(
        session, tenant_id=user.tenant_id, product_id=p["id"],
        qty=Decimal("10"), unit_cost=Decimal("5"),
        source_doc="BILL-LC-1", lot_no="LOT-A",
    )
    record_purchase(
        session, tenant_id=user.tenant_id, product_id=p["id"],
        qty=Decimal("10"), unit_cost=Decimal("5"),
        source_doc="BILL-LC-1", lot_no="LOT-B",
    )
    session.commit()
    layers = session.exec(
        select(InventoryLayer).where(InventoryLayer.source_doc == "BILL-LC-1")
    ).all()
    assert len(layers) == 2
    plan = plan_allocation(list(layers), Decimal("20"), "value")
    assert len(plan) == 2
    assert sum(D(r["amount"]) for r in plan) == Decimal("20.0000") or abs(
        float(sum(D(r["amount"]) for r in plan)) - 20
    ) < 0.01
    session.close()

    r = client.post(
        "/api/inventory/landed-costs",
        headers=auth,
        json={
            "cost_date": "2026-08-02",
            "amount": 20,
            "goods_source_doc": "BILL-LC-1",
            "allocation_method": "value",
            "post": True,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body.get("status") == "posted", body
    txn_id = body.get("transaction_id")
    assert txn_id, body

    session = Session(client.app.state.engine)
    layers = session.exec(
        select(InventoryLayer).where(InventoryLayer.source_doc == "BILL-LC-1")
    ).all()
    # Each layer got +1 unit cost (20 total / 20 qty across equal value layers → +1 each)
    for ly in layers:
        assert D(ly.unit_cost) == Decimal("6.0000") or abs(float(ly.unit_cost) - 6) < 0.01
    allocs = session.exec(select(LandedCostAllocation)).all()
    assert len(allocs) == 2
    # GL balanced
    txn = session.get(Transaction, txn_id)
    assert txn
    jes = session.exec(select(JournalEntry).where(JournalEntry.transaction_id == txn.id)).all()
    assert abs(sum(float(j.debit) for j in jes) - sum(float(j.credit) for j in jes)) < 0.001
    session.close()


def test_lot_required_and_fifo_lot_consume(client: TestClient):
    auth = _auth(client, "lot@inv.test", "LotCo")
    # Set tenant FIFO
    client.patch("/api/settings", headers=auth, json={"cost_method": "fifo"})
    p = _stock_product(client, auth, name="LotWidget", track_lot=True)

    session = Session(client.app.state.engine)
    from models import User
    user = session.exec(select(User)).first()
    try:
        record_purchase(
            session, tenant_id=user.tenant_id, product_id=p["id"],
            qty=Decimal("5"), unit_cost=Decimal("10"),
            source_doc="B1",
        )
        assert False, "expected InventoryError for missing lot"
    except InventoryError:
        session.rollback()

    record_purchase(
        session, tenant_id=user.tenant_id, product_id=p["id"],
        qty=Decimal("5"), unit_cost=Decimal("10"),
        source_doc="B1", lot_no="L1",
    )
    record_purchase(
        session, tenant_id=user.tenant_id, product_id=p["id"],
        qty=Decimal("5"), unit_cost=Decimal("20"),
        source_doc="B2", lot_no="L2",
    )
    session.commit()

    # Consume from L2 only
    cogs = consume_stock(
        session, tenant_id=user.tenant_id, product_id=p["id"],
        qty=Decimal("2"), lot_no="L2", block_negative=True,
    )
    session.commit()
    assert abs(float(cogs) - 40) < 0.01  # 2 × 20

    try:
        consume_stock(
            session, tenant_id=user.tenant_id, product_id=p["id"],
            qty=Decimal("1"), block_negative=True,
        )
        assert False, "lot required"
    except InventoryError:
        session.rollback()
    session.close()


def test_serial_tracking_receipt_and_sale(client: TestClient):
    auth = _auth(client, "ser@inv.test", "SerCo")
    p = _stock_product(client, auth, name="Phone", track_serial=True)
    session = Session(client.app.state.engine)
    from models import User
    user = session.exec(select(User)).first()
    record_purchase(
        session, tenant_id=user.tenant_id, product_id=p["id"],
        qty=Decimal("2"), unit_cost=Decimal("100"),
        source_doc="B-SER", serials=["SN-1", "SN-2"],
    )
    session.commit()
    serials = session.exec(select(StockSerial)).all()
    assert len(serials) == 2
    consume_stock(
        session, tenant_id=user.tenant_id, product_id=p["id"],
        qty=Decimal("1"), serials=["SN-1"], block_negative=True,
    )
    session.commit()
    sn1 = session.exec(select(StockSerial).where(StockSerial.serial == "SN-1")).first()
    assert sn1.status == "sold"
    session.close()


def test_nrv_write_down_journal(client: TestClient):
    auth = _auth(client, "nrv@inv.test", "NrvCo")
    p = _stock_product(client, auth, name="OldStock", nrv=4)
    session = Session(client.app.state.engine)
    from models import User
    user = session.exec(select(User)).first()
    record_purchase(
        session, tenant_id=user.tenant_id, product_id=p["id"],
        qty=Decimal("10"), unit_cost=Decimal("10"),
        source_doc="B-NRV",
    )
    # Also set nrv on product row (create may have set it)
    prod = session.get(Product, p["id"])
    prod.nrv_unit = Decimal("4")
    session.add(prod)
    session.commit()
    session.close()

    r = client.post(
        "/api/inventory/nrv/runs",
        headers=auth,
        json={"run_date": "2026-08-02", "use_allowance": True},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "posted"
    # Write-down = (10-4)*10 = 60
    detail = client.get(f"/api/inventory/nrv/runs/{r.json()['id']}", headers=auth).json()
    assert abs(float(detail["lines"][0]["write_down"]) - 60) < 0.01

    session = Session(client.app.state.engine)
    jes = session.exec(
        select(JournalEntry).where(JournalEntry.transaction_id == r.json()["transaction_id"])
    ).all()
    assert abs(sum(float(j.debit) for j in jes) - sum(float(j.credit) for j in jes)) < 0.001
    session.close()

    # Reversible
    rev = client.post(f"/api/inventory/nrv/runs/{r.json()['id']}/reverse", headers=auth)
    assert rev.status_code == 200
    assert rev.json()["status"] == "reversed"
