"""First-run demo auto-seed guard logic (scripts.autoseed_demo).

Verifies the three branches without running the real (~20s) seeder:
  - SEED_DEMO off            → does nothing
  - SEED_DEMO on, present    → skips (does NOT re-seed)
  - SEED_DEMO on, empty      → invokes the rich seeder exactly once
The `client` fixture (conftest) gives us an in-memory DB with `db.engine`
patched, which is what autoseed_demo reads.
"""
from sqlmodel import Session, select

import db as _db_module
import scripts.autoseed_demo as autoseed
from models import Tenant, User


def _make_demo_user(engine) -> None:
    with Session(engine) as s:
        t = Tenant(name="Demo Simple Co.", business_model="simple")
        s.add(t)
        s.commit()
        s.refresh(t)
        s.add(User(
            email=autoseed.DEMO_PROBE, hashed_password="x",
            full_name="Demo", tenant_id=t.id, role="owner",
        ))
        s.commit()


def _boom():  # a stand-in that fails the test if the seeder is called
    raise AssertionError("seed_all_demos should not have been called")


def test_skips_when_seed_demo_off(client, monkeypatch):
    monkeypatch.delenv("SEED_DEMO", raising=False)
    monkeypatch.setattr("scripts.seed_demo.seed_all_demos", _boom)
    autoseed.main()  # returns before touching the DB or seeder
    with Session(_db_module.engine) as s:
        assert s.exec(select(User).where(User.email == autoseed.DEMO_PROBE)).first() is None


def test_skips_when_already_present(client, monkeypatch):
    monkeypatch.setenv("SEED_DEMO", "true")
    _make_demo_user(_db_module.engine)
    monkeypatch.setattr("scripts.seed_demo.seed_all_demos", _boom)
    autoseed.main()  # demo present → must skip WITHOUT calling the seeder


def test_seeds_when_enabled_and_empty(client, monkeypatch):
    monkeypatch.setenv("SEED_DEMO", "true")
    calls = {"n": 0}

    def _stub():
        calls["n"] += 1
        return [{"email": autoseed.DEMO_PROBE}]

    monkeypatch.setattr("scripts.seed_demo.seed_all_demos", _stub)
    autoseed.main()
    assert calls["n"] == 1
