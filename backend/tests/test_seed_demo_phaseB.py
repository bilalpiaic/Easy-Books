"""Phase B: the demo seeder exercises current features (deferred / vouchers /
multi-period / multi-user). Each test seeds a tenant into the in-memory test DB
(the `client` fixture patches seed_demo.engine) and asserts an invariant."""
from datetime import date

from sqlmodel import Session, select

import db as _db_module
from models import Account, AuditLog, DeferredRevenueSchedule, JournalEntry, Transaction, User
from scripts.seed_demo import seed_one_tenant


def _seed(client, model, email=None):
    """Seed one demo tenant of `model` into the test DB; return its tenant_id."""
    email = email or f"demo.{model}@seedtest.app"
    rep = seed_one_tenant(email, f"{model.title()} Co", model)
    return rep["tenant_id"]


def _txns(tid):
    with Session(_db_module.engine) as s:
        return s.exec(select(Transaction).where(Transaction.tenant_id == tid)).all()


def test_seeded_data_spans_more_than_one_year(client):
    # Date-independent: the seeded transactions must span >400 days, which the
    # old 365-day window provably cannot — proving the 2-FY widening took effect
    # regardless of the calendar date the suite runs on.
    tid = _seed(client, "services")
    dates = sorted(t.date for t in _txns(tid))
    assert dates, "no transactions seeded"
    span_days = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days
    assert span_days > 400, f"date span only {span_days} days — not multi-year"


def test_seeded_transactions_carry_document_voucher_types(client):
    tid = _seed(client, "trader")
    with Session(_db_module.engine) as s:
        vtypes = {t.voucher_type for t in s.exec(
            select(Transaction).where(Transaction.tenant_id == tid)).all()}
    assert {"SL", "PU", "CR", "CP"}.issubset(vtypes), f"got {sorted(vtypes)}"


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
