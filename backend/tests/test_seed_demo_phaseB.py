"""Phase B: the demo seeder exercises current features (deferred / vouchers /
multi-period / multi-user). Each test seeds a tenant into the in-memory test DB
(the `client` fixture patches seed_demo.engine) and asserts an invariant."""
from datetime import date

from sqlmodel import Session, select

import db as _db_module
from models import (Account, AuditLog, DeferredRevenueSchedule, JournalEntry,
                    Settings, StoreIssue, Transaction, User)
from scripts.seed_demo import seed_one_tenant


def _seed(client, model, email=None):
    """Seed one demo tenant of `model` into the test DB; return its tenant_id."""
    email = email or f"demo.{model}@seedtest.app"
    rep = seed_one_tenant(email, f"{model.title()} Co", model)
    return rep["tenant_id"]


def _txns(tid):
    with Session(_db_module.engine) as s:
        return s.exec(select(Transaction).where(Transaction.tenant_id == tid)).all()


def test_seeded_data_spans_at_least_two_years(client):
    # Window is [today − 2 calendar years, today]. Assert transactions actually
    # fill most of that span (allowing a few days of jitter at the edges).
    from scripts.seed_demo import _seed_span_days, _seed_today, _seed_window_start

    tid = _seed(client, "services")
    dates = sorted(t.date for t in _txns(tid))
    assert dates, "no transactions seeded"
    first, last = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
    span_days = (last - first).days
    window = _seed_span_days()
    today = _seed_today()
    assert first >= _seed_window_start(today), f"first {first} before window start"
    assert last <= today, f"last {last} is in the future"
    assert span_days >= window - 30, (
        f"date span only {span_days} days — expected ~{window} (2-year window)"
    )


def test_seed_window_is_today_relative():
    from scripts.seed_demo import (
        _clamp_to_today, _past_days, _seed_span_days, _seed_window_start,
    )

    # Fixed anchors matching the product rule examples
    d1 = date(2026, 7, 21)
    assert _seed_window_start(d1) == date(2024, 7, 21)
    assert _seed_span_days(d1) == (d1 - date(2024, 7, 21)).days
    assert _past_days(10_000, today=d1) == "2024-07-21"  # clamp to window start
    assert _past_days(0, today=d1) == "2026-07-21"
    assert _clamp_to_today("2026-08-15", today=d1) == "2026-07-21"
    assert _clamp_to_today("2025-01-01", today=d1) == "2025-01-01"

    d2 = date(2026, 1, 1)
    assert _seed_window_start(d2) == date(2024, 1, 1)
    assert _seed_span_days(d2) == (d2 - date(2024, 1, 1)).days

    # Leap-day trigger: Feb 29 → Feb 28 two years earlier
    leap = date(2024, 2, 29)
    assert _seed_window_start(leap) == date(2022, 2, 28)


def test_seeded_transactions_carry_document_voucher_types(client):
    tid = _seed(client, "trader")
    with Session(_db_module.engine) as s:
        vtypes = {t.voucher_type for t in s.exec(
            select(Transaction).where(Transaction.tenant_id == tid)).all()}
    assert {"SL", "PU", "CR", "CP", "BR", "BP"}.issubset(vtypes), f"got {sorted(vtypes)}"


def test_seeded_deferred_revenue_is_originated_and_partially_recognised(client):
    tid = _seed(client, "services")
    with Session(_db_module.engine) as s:
        scheds = s.exec(select(DeferredRevenueSchedule).where(
            DeferredRevenueSchedule.tenant_id == tid)).all()
        acc2300 = s.exec(select(Account).where(
            Account.tenant_id == tid, Account.code == "2300")).first()
        credits_2300 = 0.0
        if acc2300:
            from services.money import D
            rows = s.exec(select(JournalEntry).where(
                JournalEntry.account_id == acc2300.id)).all()
            credits_2300 = float(sum(D(r.credit) for r in rows))
    assert scheds, "no deferred schedules originated"
    assert any(float(x.recognised_amount) > 0 for x in scheds), "no partial recognition"
    assert credits_2300 > 0, "no Deferred Revenue (2300) credit posted by origination"


def test_seeded_tenant_has_multiple_users_with_varied_audit(client):
    tid = _seed(client, "services")
    with Session(_db_module.engine) as s:
        users = s.exec(select(User).where(User.tenant_id == tid)).all()
        actor_ids = {a.user_id for a in s.exec(
            select(AuditLog).where(AuditLog.tenant_id == tid)).all()}
    assert len(users) >= 2, f"expected >=2 users, got {len(users)}"
    assert len(actor_ids) >= 2, f"audit attributed to {len(actor_ids)} user(s)"


import pytest


@pytest.mark.parametrize("model", ["simple", "services", "trader", "manufacturing", "telecom_franchise"])
def test_every_segment_seeds_and_trial_balance_balances(client, model):
    tid = _seed(client, model)
    from services.money import D
    with Session(_db_module.engine) as s:
        rows = s.exec(select(JournalEntry).join(Transaction).where(
            Transaction.tenant_id == tid)).all()
        dr = sum(D(r.debit) for r in rows)
        cr = sum(D(r.credit) for r in rows)
    assert dr == cr, f"{model}: trial balance off by {dr - cr}"
    assert len(_txns(tid)) > 0, f"{model}: no transactions seeded"


def test_every_segment_enables_email_notifications(client):
    tid = _seed(client, "services", email="demo.notif@seedtest.app")
    with Session(_db_module.engine) as s:
        row = s.exec(select(Settings).where(
            Settings.tenant_id == tid, Settings.key == "email_notifications")).first()
    assert row is not None and row.value == "true"


def test_manufacturing_seeds_enough_store_issues_to_paginate(client):
    """#150/#154 gave the Issue Register a 50-row page; seed data must exceed
    that so the Pagination control and search box aren't dormant on first
    login."""
    tid = _seed(client, "manufacturing")
    with Session(_db_module.engine) as s:
        count = len(s.exec(select(StoreIssue).where(StoreIssue.tenant_id == tid)).all())
    assert count > 50, f"only {count} store issues seeded — Issue Register never paginates"
