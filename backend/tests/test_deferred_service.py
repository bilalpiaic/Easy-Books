"""Unit + schema tests for deferred-revenue origination (#47)."""
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import db as _db_module
from models import Account, DeferredRevenueSchedule, Product, Tenant
from services.money import ZERO, money


def test_product_create_accepts_deferred_flags(client, admin_headers):
    h = admin_headers
    p = client.post("/api/products", headers=h, json={
        "name": "Support Plan", "product_type": "service",
        "default_rate": 120, "is_deferred": True, "recognition_months": 24,
    }).json()
    assert p["is_deferred"] is True
    assert p["recognition_months"] == 24


def test_product_update_accepts_deferred_flags(client, admin_headers):
    h = admin_headers
    # Create a product without deferral
    p = client.post("/api/products", headers=h, json={
        "name": "Basic Plan", "product_type": "service",
        "default_rate": 100,
    }).json()

    # Update it to be deferred
    updated = client.put(f"/api/products/{p['id']}", headers=h, json={
        "name": "Basic Plan", "product_type": "service",
        "default_rate": 100, "is_deferred": True, "recognition_months": 18,
    }).json()

    assert updated["is_deferred"] is True
    assert updated["recognition_months"] == 18


def test_add_months_advances_date():
    from services.deferred import _add_months
    assert _add_months("2026-01-31", 1) == "2026-02-28"   # clamps to month end
    assert _add_months("2026-03-01", 12) == "2027-03-01"


@pytest.fixture
def dsession():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Tenant(id=1, name="T1"))
        s.commit()
        yield s


def _add_product(s, *, is_deferred, months=12, rev_acct=None):
    p = Product(tenant_id=1, name="P", product_type="service",
                is_deferred=is_deferred, recognition_months=months,
                revenue_account_id=rev_acct)
    s.add(p); s.commit(); s.refresh(p)
    return p


def test_plan_deferral_splits_deferred_and_normal(dsession):
    from types import SimpleNamespace
    from services.deferred import plan_deferral
    s = dsession
    pd = _add_product(s, is_deferred=True, months=24, rev_acct=7)
    pn = _add_product(s, is_deferred=False)
    lines = [
        SimpleNamespace(product_id=pd.id, qty=Decimal("2"), rate=Decimal("50")),  # 100 deferred
        SimpleNamespace(product_id=pn.id, qty=Decimal("1"), rate=Decimal("30")),  # 30 normal
        SimpleNamespace(product_id=None,  qty=Decimal("1"), rate=Decimal("10")),  # 10 normal (no product)
    ]
    plan = plan_deferral(s, tenant_id=1, lines=lines, fx_rate=Decimal("1"))
    assert plan.deferred_net_base == money(Decimal("100"))
    assert len(plan.deferred_lines) == 1
    assert plan.deferred_lines[0].recognition_months == 24
    assert plan.deferred_lines[0].revenue_account_id == 7
    assert plan.deferred_lines[0].net_base == money(Decimal("100"))


def test_plan_deferral_none_deferred(dsession):
    from types import SimpleNamespace
    from services.deferred import plan_deferral
    s = dsession
    pn = _add_product(s, is_deferred=False)
    lines = [SimpleNamespace(product_id=pn.id, qty=Decimal("3"), rate=Decimal("10"))]
    plan = plan_deferral(s, tenant_id=1, lines=lines, fx_rate=Decimal("1"))
    assert plan.deferred_net_base == ZERO
    assert plan.deferred_lines == []


def test_plan_deferral_floors_months_at_one(dsession):
    from types import SimpleNamespace
    from services.deferred import plan_deferral
    s = dsession
    pd = _add_product(s, is_deferred=True, months=0)
    lines = [SimpleNamespace(product_id=pd.id, qty=Decimal("1"), rate=Decimal("10"))]
    plan = plan_deferral(s, tenant_id=1, lines=lines, fx_rate=Decimal("1"))
    assert plan.deferred_lines[0].recognition_months == 1


def test_plan_deferral_applies_fx_rate(dsession):
    from types import SimpleNamespace
    from services.deferred import plan_deferral
    s = dsession
    pd = _add_product(s, is_deferred=True)
    lines = [SimpleNamespace(product_id=pd.id, qty=Decimal("2"), rate=Decimal("50"))]  # 100 doc
    plan = plan_deferral(s, tenant_id=1, lines=lines, fx_rate=Decimal("1.5"))
    assert plan.deferred_net_base == money(Decimal("150"))   # 100 × 1.5 → base
    assert plan.deferred_lines[0].net_base == money(Decimal("150"))


def test_resolve_deferred_account_defaults_to_2300(dsession):
    from services.deferred import resolve_deferred_account
    acc = resolve_deferred_account(dsession, tenant_id=1)
    assert acc.code == "2300"
    assert acc.type == "Liability"


def _add_account(s, code, typ="Liability"):
    a = Account(tenant_id=1, code=code, name=code, type=typ)
    s.add(a); s.commit(); s.refresh(a)
    return a


def test_create_schedules_one_row_per_deferred_line(dsession):
    from types import SimpleNamespace
    from services.deferred import plan_deferral, create_schedules, LineDeferral, DeferralPlan
    from models import DeferredRevenueSchedule
    s = dsession
    _add_account(s, "2300")
    rev = _add_account(s, "4000", "Revenue")
    plan = DeferralPlan(
        deferred_lines=[LineDeferral(net_base=money(Decimal("120")), recognition_months=12, revenue_account_id=rev.id)],
        deferred_net_base=money(Decimal("120")),
    )
    inv = SimpleNamespace(id=99, issue_date="2026-03-01")
    user = SimpleNamespace(tenant_id=1)
    rows = create_schedules(s, user, inv, plan)
    assert len(rows) == 1
    sch = s.exec(select(DeferredRevenueSchedule).where(DeferredRevenueSchedule.invoice_id == 99)).all()
    assert len(sch) == 1
    assert sch[0].total_amount == money(Decimal("120"))
    assert sch[0].start_date == "2026-03-01"
    assert sch[0].end_date == "2027-03-01"
    assert sch[0].revenue_account_id == rev.id
    assert sch[0].status == "active"


def test_has_any_recognition_and_reverse(dsession):
    from services.deferred import has_any_recognition, reverse_schedules
    from models import DeferredRevenueSchedule
    s = dsession
    a23 = _add_account(s, "2300"); a40 = _add_account(s, "4000", "Revenue")
    s.add(DeferredRevenueSchedule(
        tenant_id=1, invoice_id=99, total_amount=money(Decimal("120")),
        recognised_amount=ZERO, start_date="2026-03-01", end_date="2027-03-01",
        frequency="monthly", next_recognition_date="2026-03-01", status="active",
        deferred_revenue_account_id=a23.id, revenue_account_id=a40.id,
    ))
    s.commit()
    assert has_any_recognition(s, 1, 99) is False
    # Recognise part of it
    row = s.exec(select(DeferredRevenueSchedule).where(DeferredRevenueSchedule.invoice_id == 99)).first()
    row.recognised_amount = money(Decimal("10")); s.add(row); s.commit()
    assert has_any_recognition(s, 1, 99) is True
    # reverse_schedules deletes rows for the invoice
    reverse_schedules(s, 1, 99); s.commit()
    assert s.exec(select(DeferredRevenueSchedule).where(DeferredRevenueSchedule.invoice_id == 99)).all() == []
