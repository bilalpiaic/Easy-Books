"""First-run demo data loader for standalone installs.

The standalone installers (`install-and-run.*`) call this AFTER `alembic upgrade
head` and BEFORE launching the servers. It populates the 5 fully-featured demo
companies (the rich data — customers, invoices, bills, JVs — from
`scripts.seed_demo`) so the advertised demo logins work immediately on a fresh
install, then never re-runs (it skips when the demo data is already present).

Why not just `SEED_DEMO=true`? `db.py`'s boot path only creates *empty* demo
logins (a Chart of Accounts, zero transactions). The rich data lives in
`scripts.seed_demo`, which boot never calls — so the installer runs this once.

Controlled by the SEED_DEMO env var (the installers default it to "true"):
    SEED_DEMO=true   → load demo data on first run
    SEED_DEMO=false  → clean install (no demo data)

Demo logins (all password `demo1234`):
    demo.simple@easy-books.app, demo.services@…, demo.trader@…,
    demo.manufacturing@…, demo.telecom@…
"""
from __future__ import annotations

import os

from sqlmodel import Session, select

DEMO_PROBE = "demo.simple@easy-books.app"


def main() -> None:
    if os.environ.get("SEED_DEMO", "false").lower() != "true":
        print("[autoseed] SEED_DEMO=false — clean install (no demo data)", flush=True)
        return

    # Imported here (not at module top) so a patched `db.engine` is respected
    # in tests, and so this stays cheap when SEED_DEMO is off.
    import db
    from models import User

    with Session(db.engine) as session:
        # Only a brand-new install (no users yet) is auto-seeded. autoseed runs
        # before any boot-seeding, so a fresh DB has zero users here; the moment
        # any user exists (a real signup or a prior demo load) this is an
        # existing install → skip, so updating never injects demo data.
        if session.exec(select(User)).first():
            print("[autoseed] existing install (users present) — skipping demo load", flush=True)
            return

    print("[autoseed] first run: loading demo companies (~20-30s)…", flush=True)
    from scripts.seed_demo import seed_all_demos

    reports = seed_all_demos()
    ok = sum(1 for r in reports if "error" not in r)
    print(
        f"[autoseed] done — {ok}/{len(reports)} demo companies ready "
        f"(login {DEMO_PROBE} / demo1234)",
        flush=True,
    )


if __name__ == "__main__":
    main()
