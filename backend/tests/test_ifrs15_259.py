"""IFRS 15 remaining (#259): relative SSP allocation + contract assets."""
from decimal import Decimal

from sqlmodel import Session, select

import db as _db_module
from models import Account, JournalEntry, RevenueAllocationAudit
from services.ifrs15 import allocate_relative_ssp
from services.money import D, money


def _sum_col(code, col):
    with Session(_db_module.engine) as s:
        acc = s.exec(select(Account).where(Account.code == code)).first()
        if not acc:
            return 0.0
        rows = s.exec(select(JournalEntry).where(JournalEntry.account_id == acc.id)).all()
        return float(sum(D(getattr(r, col)) for r in rows))


def test_allocate_relative_ssp_60_40():
    lines = [
        {"qty": 1, "rate": 70, "discount_pct": 0, "ssp": 60, "description": "A"},
        {"qty": 1, "rate": 30, "discount_pct": 0, "ssp": 40, "description": "B"},
    ]
    allocated, audit = allocate_relative_ssp(lines)
    assert audit["method"] == "relative_ssp"
    assert float(audit["transaction_price"]) == 100.0
    assert sum(allocated) == money(Decimal("100"))
    assert allocated[0] == money(Decimal("60"))
    assert allocated[1] == money(Decimal("40"))


def test_allocate_none_without_ssp():
    lines = [
        {"qty": 1, "rate": 50, "discount_pct": 0, "description": "A"},
        {"qty": 1, "rate": 50, "discount_pct": 0, "description": "B"},
    ]
    allocated, audit = allocate_relative_ssp(lines)
    assert audit["method"] == "none"
    assert allocated == [money(Decimal("50")), money(Decimal("50"))]


def test_invoice_create_with_ssp_writes_audit(client, admin_headers):
    h = admin_headers
    r = client.post("/api/invoices", headers=h, json={
        "customer_name": "Bundle Co",
        "issue_date": "2026-04-01",
        "gst_rate": 0,
        "lines": [
            {"description": "License", "qty": 1, "rate": 70, "ssp": 60},
            {"description": "Support", "qty": 1, "rate": 30, "ssp": 40},
        ],
    })
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert float(body["subtotal"]) == 100.0
    amounts = [float(ln["amount"]) for ln in body["lines"]]
    assert sum(amounts) == 100.0
    assert amounts[0] == 60.0
    assert amounts[1] == 40.0

    detail = client.get(f"/api/invoices/{body['id']}", headers=h).json()
    assert "allocation_audit" in detail
    assert detail["allocation_audit"]["method"] == "relative_ssp"
    assert float(detail["allocation_audit"]["transaction_price"]) == 100.0

    with Session(_db_module.engine) as s:
        audits = s.exec(select(RevenueAllocationAudit)).all()
    assert len(audits) == 1
    assert audits[0].method == "relative_ssp"


def test_certify_ca_and_contract_balances(client, admin_headers):
    h = admin_headers
    cust = client.post("/api/customers", headers=h, json={"name": "CA Customer"}).json()

    # Deferred product → contract liability via schedule
    pd = client.post("/api/products", headers=h, json={
        "name": "Annual Support", "product_type": "service",
        "default_rate": 120, "is_deferred": True, "recognition_months": 12,
    }).json()
    inv = client.post("/api/invoices", headers=h, json={
        "customer_id": cust["id"], "customer_name": cust["name"],
        "issue_date": "2026-04-01", "gst_rate": 0,
        "lines": [{"product_id": pd["id"], "description": "Support", "qty": 1, "rate": 120}],
    })
    assert inv.status_code in (200, 201), inv.text

    # Certify unbilled performance → contract asset
    ca = client.post("/api/contract-assets", headers=h, json={
        "customer_id": cust["id"],
        "amount": 500,
        "certify_date": "2026-04-15",
        "description": "Milestone 1 delivered",
    })
    assert ca.status_code == 201, ca.text
    assert float(ca.json()["amount"]) == 500.0
    assert _sum_col("1140", "debit") == 500.0
    assert _sum_col("4000", "credit") == 500.0  # certify Cr Revenue (deferred went to 2300)

    bal = client.get("/api/reports/contract-balances", headers=h)
    assert bal.status_code == 200, bal.text
    data = bal.json()
    assert data["totals"]["contract_asset"] == 500.0
    assert data["totals"]["contract_liability"] == 120.0
    row = next(c for c in data["customers"] if c["customer_id"] == cust["id"])
    assert row["contract_asset"] == 500.0
    assert row["contract_liability"] == 120.0

    # Recognition run still balances (Dr 2300 / Cr Revenue)
    before_dr = _sum_col("2300", "debit")
    before_cr = _sum_col("4000", "credit")
    run = client.post(
        "/api/deferred-revenue/run-recognition?recognition_date=2026-04-01",
        headers=h,
    )
    assert run.status_code == 200, run.text
    assert run.json()["recognised_count"] >= 1
    after_dr = _sum_col("2300", "debit")
    after_cr = _sum_col("4000", "credit")
    assert after_dr - before_dr == after_cr - before_cr
    assert after_dr > before_dr


def test_plan_deferral_uses_discount_and_amount():
    """Regression: deferred net must honour discount / allocated amount (#259)."""
    from types import SimpleNamespace
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine
    from models import Product, Tenant
    from services.deferred import plan_deferral
    from services.money import ZERO

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Tenant(id=1, name="T"))
        p = Product(tenant_id=1, name="D", product_type="service",
                    is_deferred=True, recognition_months=12)
        s.add(p)
        s.commit()
        s.refresh(p)
        # 100 with 10% discount → 90
        lines = [SimpleNamespace(
            product_id=p.id, qty=Decimal("1"), rate=Decimal("100"),
            discount_pct=Decimal("10"),
        )]
        plan = plan_deferral(s, 1, lines, Decimal("1"))
        assert plan.deferred_net_base == money(Decimal("90"))
        # Explicit amount wins (allocated)
        lines2 = [SimpleNamespace(
            product_id=p.id, qty=Decimal("1"), rate=Decimal("100"),
            discount_pct=Decimal("0"), amount=Decimal("60"),
        )]
        plan2 = plan_deferral(s, 1, lines2, Decimal("1"))
        assert plan2.deferred_net_base == money(Decimal("60"))
