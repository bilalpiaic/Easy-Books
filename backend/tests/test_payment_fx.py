"""#215 Payment FX settlement (IAS 21) tests."""
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, StaticPool, create_engine

from db import get_session
from main import app


def _mk_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _override(engine):
    def _inner():
        with Session(engine) as s:
            yield s
    return _inner


def _auth(client, email="payfx@co.test", company="PayFxCo"):
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


def _tb_find(nodes, code):
    for n in nodes:
        if n["code"] == code:
            return n
        hit = _tb_find(n.get("children", []), code)
        if hit:
            return hit
    return None


def _net(row) -> Decimal:
    """Asset-style net (debit − credit); for Revenue use credit − debit."""
    return Decimal(str(row["debit"])) - Decimal(str(row["credit"]))


def test_fx_receipt_posts_realised_gain():
    """USD invoice @ 280, settle @ 290 → realised gain on 4903; AR cleared at carrying."""
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _override(engine)
    client = TestClient(app)
    auth = _auth(client, "fx-gain@co.test", "FxGainCo")

    client.patch("/api/settings", headers=auth, json={"currency": "PKR"})
    client.post("/api/exchange-rates", headers=auth, json={
        "from_currency": "USD", "to_currency": "PKR", "rate": 280, "date": "2026-01-01",
    })
    client.post("/api/exchange-rates", headers=auth, json={
        "from_currency": "USD", "to_currency": "PKR", "rate": 290, "date": "2026-01-15",
    })

    cust = client.post("/api/customers", headers=auth, json={"name": "Foreign"}).json()
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"],
        "issue_date": "2026-01-01",
        "due_date": "2026-01-31",
        "gst_rate": 0,
        "currency": "USD",
        "exchange_rate": 280,
        "lines": [{"description": "Svc", "qty": 1, "rate": 100}],
    }).json()
    assert Decimal(str(inv["total"])) == Decimal("100")

    r = client.post("/api/payments-received", headers=auth, json={
        "customer_id": cust["id"],
        "payment_date": "2026-01-15",
        "amount": 100,
        "currency": "USD",
        "exchange_rate": 290,
        "method": "bank_transfer",
        "allocations": [{"invoice_id": inv["id"], "amount": 100}],
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["currency"] == "USD"
    assert Decimal(str(body["exchange_rate"])) == Decimal("290")

    tb = client.get("/api/reports/trial-balance", headers=auth).json()
    # Balanced
    assert Decimal(str(tb["totals"]["debit"])) == Decimal(str(tb["totals"]["credit"]))

    ar = _tb_find(tb["tree"], "1100")
    cash = _tb_find(tb["tree"], "1000")
    fx = _tb_find(tb["tree"], "4903")
    assert ar is not None and cash is not None and fx is not None
    # Invoice Dr AR 28_000; payment Cr AR 28_000 → AR net 0
    assert _net(ar) == Decimal("0")
    # Cash Dr 29_000
    assert _net(cash) == Decimal("29000")
    # Realised gain Cr 1_000 → revenue credit − debit = 1000
    assert Decimal(str(fx["credit"])) - Decimal(str(fx["debit"])) == Decimal("1000")

    app.dependency_overrides.clear()


def test_fx_receipt_posts_realised_loss():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _override(engine)
    client = TestClient(app)
    auth = _auth(client, "fx-loss@co.test", "FxLossCo")

    client.patch("/api/settings", headers=auth, json={"currency": "PKR"})
    cust = client.post("/api/customers", headers=auth, json={"name": "Foreign"}).json()
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"],
        "issue_date": "2026-01-01",
        "due_date": "2026-01-31",
        "gst_rate": 0,
        "currency": "USD",
        "exchange_rate": 280,
        "lines": [{"description": "Svc", "qty": 1, "rate": 100}],
    }).json()

    r = client.post("/api/payments-received", headers=auth, json={
        "customer_id": cust["id"],
        "payment_date": "2026-01-20",
        "amount": 100,
        "currency": "USD",
        "exchange_rate": 270,
        "method": "cash",
        "allocations": [{"invoice_id": inv["id"], "amount": 100}],
    })
    assert r.status_code == 201, r.text

    tb = client.get("/api/reports/trial-balance", headers=auth).json()
    assert Decimal(str(tb["totals"]["debit"])) == Decimal(str(tb["totals"]["credit"]))
    fx = _tb_find(tb["tree"], "4903")
    assert fx is not None
    # Loss: Dr 1000
    assert Decimal(str(fx["debit"])) - Decimal(str(fx["credit"])) == Decimal("1000")

    app.dependency_overrides.clear()


def test_base_currency_payment_unchanged():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _override(engine)
    client = TestClient(app)
    auth = _auth(client, "base-pay@co.test", "BasePayCo")

    cust = client.post("/api/customers", headers=auth, json={"name": "Local"}).json()
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"],
        "issue_date": "2026-01-01",
        "due_date": "2026-01-31",
        "gst_rate": 0,
        "lines": [{"description": "Svc", "qty": 1, "rate": 500}],
    }).json()

    r = client.post("/api/payments-received", headers=auth, json={
        "customer_id": cust["id"],
        "payment_date": "2026-01-10",
        "amount": 500,
        "method": "cash",
        "allocations": [{"invoice_id": inv["id"], "amount": 500}],
    })
    assert r.status_code == 201, r.text

    tb = client.get("/api/reports/trial-balance", headers=auth).json()
    assert Decimal(str(tb["totals"]["debit"])) == Decimal(str(tb["totals"]["credit"]))
    fx = _tb_find(tb["tree"], "4903")
    # No realised FX account activity required
    if fx is not None:
        assert Decimal(str(fx["debit"])) == Decimal("0")
        assert Decimal(str(fx["credit"])) == Decimal("0")

    app.dependency_overrides.clear()


def test_mixed_currency_allocations_rejected():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _override(engine)
    client = TestClient(app)
    auth = _auth(client, "mix@co.test", "MixCo")

    client.patch("/api/settings", headers=auth, json={"currency": "PKR"})
    client.post("/api/exchange-rates", headers=auth, json={
        "from_currency": "USD", "to_currency": "PKR", "rate": 280, "date": "2026-01-01",
    })
    client.post("/api/exchange-rates", headers=auth, json={
        "from_currency": "EUR", "to_currency": "PKR", "rate": 300, "date": "2026-01-01",
    })
    cust = client.post("/api/customers", headers=auth, json={"name": "Multi"}).json()
    usd = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"],
        "issue_date": "2026-01-01",
        "due_date": "2026-01-31",
        "gst_rate": 0,
        "currency": "USD",
        "exchange_rate": 280,
        "lines": [{"description": "U", "qty": 1, "rate": 50}],
    }).json()
    eur = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"],
        "issue_date": "2026-01-01",
        "due_date": "2026-01-31",
        "gst_rate": 0,
        "currency": "EUR",
        "exchange_rate": 300,
        "lines": [{"description": "E", "qty": 1, "rate": 50}],
    }).json()

    r = client.post("/api/payments-received", headers=auth, json={
        "customer_id": cust["id"],
        "payment_date": "2026-01-10",
        "amount": 100,
        "currency": "USD",
        "exchange_rate": 280,
        "allocations": [
            {"invoice_id": usd["id"], "amount": 50},
            {"invoice_id": eur["id"], "amount": 50},
        ],
    })
    assert r.status_code == 400, r.text
    assert "mixed" in r.json()["detail"].lower()

    app.dependency_overrides.clear()


def test_fx_payment_rejects_unallocated_remainder():
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _override(engine)
    client = TestClient(app)
    auth = _auth(client, "unalloc@co.test", "UnallocCo")

    client.patch("/api/settings", headers=auth, json={"currency": "PKR"})
    cust = client.post("/api/customers", headers=auth, json={"name": "F"}).json()
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"],
        "issue_date": "2026-01-01",
        "due_date": "2026-01-31",
        "gst_rate": 0,
        "currency": "USD",
        "exchange_rate": 280,
        "lines": [{"description": "S", "qty": 1, "rate": 100}],
    }).json()

    r = client.post("/api/payments-received", headers=auth, json={
        "customer_id": cust["id"],
        "payment_date": "2026-01-10",
        "amount": 120,
        "currency": "USD",
        "exchange_rate": 280,
        "allocations": [{"invoice_id": inv["id"], "amount": 100}],
    })
    assert r.status_code == 400, r.text

    app.dependency_overrides.clear()
