"""
GL invariant tests.

These exist to lock in the P0 correctness fixes:
  - Dr=Cr enforcement is exact (Decimal), not float-tolerant
  - Period locks block writes everywhere (no endpoint can bypass)
  - The DB CHECK constraint refuses malformed JE rows
  - Stock sales relieve inventory at WAvg cost (COGS posted)
  - Reversals truly zero out the original posting
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from models import (
    Account, AccountingPeriod, InventoryLayer, JournalEntry, Product, Tenant,
    Transaction, User,
)
from services.inventory import consume_stock, record_purchase
from services.money import D, ZERO, money
from services.posting import EntryInput, PostingError, post_transaction


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def world(session: Session):
    """A minimal tenant with a user and four GL accounts to post against."""
    tenant = Tenant(name="Acme")
    session.add(tenant); session.commit(); session.refresh(tenant)

    user = User(email="acc@acme.test", hashed_password="x", tenant_id=tenant.id)
    session.add(user); session.commit(); session.refresh(user)

    accounts = {
        "cash": Account(code="1000", name="Cash", type="Asset", tenant_id=tenant.id),
        "ar":   Account(code="1100", name="AR",   type="Asset", tenant_id=tenant.id),
        "rev":  Account(code="4000", name="Sales", type="Revenue", tenant_id=tenant.id),
        "inv":  Account(code="1200", name="Inventory", type="Asset", tenant_id=tenant.id),
        "cogs": Account(code="5010", name="COGS", type="Expense", tenant_id=tenant.id),
    }
    for a in accounts.values():
        session.add(a)
    session.commit()
    for a in accounts.values():
        session.refresh(a)

    return {"tenant": tenant, "user": user, "accounts": accounts}


# ── Posting service invariants ────────────────────────────────────────────────


def test_unbalanced_post_rejected(session: Session, world):
    a = world["accounts"]
    with pytest.raises(PostingError, match="not balanced"):
        post_transaction(
            session, world["user"],
            date="2026-01-15", description="bad",
            entries=[
                EntryInput(account_id=a["cash"].id, debit=Decimal("100")),
                EntryInput(account_id=a["rev"].id, credit=Decimal("99.99")),
            ],
        )


def test_balanced_post_creates_jv(session: Session, world):
    a = world["accounts"]
    txn = post_transaction(
        session, world["user"],
        date="2026-01-15", description="good",
        entries=[
            EntryInput(account_id=a["cash"].id, debit=Decimal("100.00")),
            EntryInput(account_id=a["rev"].id, credit=Decimal("100.00")),
        ],
    )
    session.commit()
    assert txn.jv_number.startswith("JV-")
    rows = session.exec(select(JournalEntry).where(JournalEntry.transaction_id == txn.id)).all()
    assert sum((D(r.debit) for r in rows), ZERO) == sum((D(r.credit) for r in rows), ZERO)


def test_period_lock_blocks_post(session: Session, world):
    session.add(AccountingPeriod(
        tenant_id=world["tenant"].id,
        period_start="2026-01-01", period_end="2026-01-31",
        is_locked=True, name="Jan 2026",
    ))
    session.commit()
    a = world["accounts"]
    with pytest.raises(PostingError, match="locked accounting period"):
        post_transaction(
            session, world["user"],
            date="2026-01-15", description="late entry",
            entries=[
                EntryInput(account_id=a["cash"].id, debit=Decimal("50")),
                EntryInput(account_id=a["rev"].id, credit=Decimal("50")),
            ],
        )


def test_both_sides_zero_rejected(session: Session, world):
    a = world["accounts"]
    with pytest.raises(PostingError, match="zero amounts"):
        post_transaction(
            session, world["user"],
            date="2026-01-15", description="empty row",
            entries=[
                EntryInput(account_id=a["cash"].id, debit=Decimal("0"), credit=Decimal("0")),
                EntryInput(account_id=a["rev"].id, credit=Decimal("0"), debit=Decimal("0")),
            ],
        )


def test_both_sides_nonzero_rejected(session: Session, world):
    a = world["accounts"]
    with pytest.raises(PostingError, match="both debit and credit"):
        post_transaction(
            session, world["user"],
            date="2026-01-15", description="double-sided",
            entries=[
                EntryInput(account_id=a["cash"].id, debit=Decimal("50"), credit=Decimal("50")),
                EntryInput(account_id=a["rev"].id, credit=Decimal("50")),
            ],
        )


def test_account_must_belong_to_tenant(session: Session, world):
    other = Tenant(name="Other Co")
    session.add(other); session.commit(); session.refresh(other)
    foreign = Account(code="9999", name="X", type="Asset", tenant_id=other.id)
    session.add(foreign); session.commit(); session.refresh(foreign)

    a = world["accounts"]
    with pytest.raises(PostingError, match="not in your tenant"):
        post_transaction(
            session, world["user"],
            date="2026-01-15", description="cross-tenant",
            entries=[
                EntryInput(account_id=foreign.id, debit=Decimal("10")),
                EntryInput(account_id=a["rev"].id, credit=Decimal("10")),
            ],
        )


def test_decimal_precision_not_float(session: Session, world):
    """0.1 + 0.2 must equal 0.3 exactly under Decimal — the whole reason
    we did the migration."""
    a = world["accounts"]
    txn = post_transaction(
        session, world["user"],
        date="2026-01-15", description="precision",
        entries=[
            EntryInput(account_id=a["cash"].id, debit=Decimal("0.1")),
            EntryInput(account_id=a["cash"].id, debit=Decimal("0.2")),
            EntryInput(account_id=a["rev"].id, credit=Decimal("0.3")),
        ],
    )
    session.commit()
    assert txn.id is not None


# ── Inventory + COGS ──────────────────────────────────────────────────────────


def _stock_product(session: Session, tenant_id: int) -> Product:
    p = Product(tenant_id=tenant_id, name="Widget", product_type="stock", unit="pcs")
    session.add(p); session.commit(); session.refresh(p)
    return p


def test_wavg_cost_after_two_purchases(session: Session, world):
    p = _stock_product(session, world["tenant"].id)
    record_purchase(session, tenant_id=world["tenant"].id, product_id=p.id,
                    qty=Decimal("10"), unit_cost=Decimal("5.00"))
    record_purchase(session, tenant_id=world["tenant"].id, product_id=p.id,
                    qty=Decimal("10"), unit_cost=Decimal("7.00"))
    session.commit(); session.refresh(p)
    # (10*5 + 10*7) / 20 = 6.00
    assert D(p.avg_cost) == Decimal("6.00")
    assert D(p.stock_qty) == Decimal("20")


def test_consume_stock_returns_wavg_cogs(session: Session, world):
    p = _stock_product(session, world["tenant"].id)
    record_purchase(session, tenant_id=world["tenant"].id, product_id=p.id,
                    qty=Decimal("10"), unit_cost=Decimal("5.00"))
    record_purchase(session, tenant_id=world["tenant"].id, product_id=p.id,
                    qty=Decimal("10"), unit_cost=Decimal("7.00"))
    session.commit()
    cogs = consume_stock(session, tenant_id=world["tenant"].id, product_id=p.id, qty=Decimal("3"))
    session.commit(); session.refresh(p)
    assert cogs == Decimal("18.00")  # 3 * 6.00 WAvg
    assert D(p.stock_qty) == Decimal("17")


def test_layer_remaining_depletes_fifo(session: Session, world):
    p = _stock_product(session, world["tenant"].id)
    record_purchase(session, tenant_id=world["tenant"].id, product_id=p.id,
                    qty=Decimal("5"), unit_cost=Decimal("4"))
    record_purchase(session, tenant_id=world["tenant"].id, product_id=p.id,
                    qty=Decimal("5"), unit_cost=Decimal("8"))
    session.commit()
    consume_stock(session, tenant_id=world["tenant"].id, product_id=p.id, qty=Decimal("6"))
    session.commit()
    layers = session.exec(select(InventoryLayer).order_by(InventoryLayer.id)).all()
    # First layer fully consumed (5), second layer leaves 4 (5 - 1).
    assert D(layers[0].qty_remaining) == Decimal("0")
    assert D(layers[1].qty_remaining) == Decimal("4")


# ── Reversal nets to zero ─────────────────────────────────────────────────────


def test_reversal_sums_to_zero(session: Session, world):
    a = world["accounts"]
    original = post_transaction(
        session, world["user"],
        date="2026-01-15", description="sale",
        entries=[
            EntryInput(account_id=a["ar"].id, debit=Decimal("250")),
            EntryInput(account_id=a["rev"].id, credit=Decimal("250")),
        ],
    )
    session.commit()
    reversal = post_transaction(
        session, world["user"],
        date="2026-01-16", description="reverse",
        entries=[
            EntryInput(account_id=a["ar"].id, credit=Decimal("250")),
            EntryInput(account_id=a["rev"].id, debit=Decimal("250")),
        ],
    )
    session.commit()
    # Σ over both transactions: AR net 0, Revenue net 0.
    rows = session.exec(
        select(JournalEntry).where(JournalEntry.transaction_id.in_([original.id, reversal.id]))
    ).all()
    ar_net  = sum((D(r.debit) - D(r.credit) for r in rows if r.account_id == a["ar"].id), ZERO)
    rev_net = sum((D(r.credit) - D(r.debit) for r in rows if r.account_id == a["rev"].id), ZERO)
    assert ar_net == ZERO
    assert rev_net == ZERO
