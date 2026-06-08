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


def test_seeded_data_spans_two_fiscal_years(client):
    tid = _seed(client, "services")
    years = {t.date[:4] for t in _txns(tid)}
    assert len(years) >= 2, f"expected >=2 distinct years, got {sorted(years)}"
