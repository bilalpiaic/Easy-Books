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
