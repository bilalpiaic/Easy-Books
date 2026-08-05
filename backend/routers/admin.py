"""Admin-only maintenance endpoints: load/remove the demo sample data.

Demo tenants are SEPARATE from the caller's own tenant, so loading them never
touches the user's real books. The seeder (scripts.seed_demo) is idempotent.
Imported lazily to avoid a db <-> scripts.seed_demo import cycle.

Cloud UI (Vercel) should POST with `{ "email": "demo.…@easy-books.app" }` so
each tenant is seeded in its own request; omit `email` for a full local seed.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import SQLModel, select

from models import Tenant, User
from .common import AdminUserDep, SessionDep, log_audit

router = APIRouter(prefix="/api/admin", tags=["admin"])


class DemoSeedBody(BaseModel):
    email: Optional[str] = None


@router.get("/demo/status")
def demo_status(session: SessionDep, user: AdminUserDep):
    """Catalog of QA demo companies + whether each has rich seed data."""
    from scripts.seed_demo import demo_tenant_status  # lazy: avoids import cycle

    return {"tenants": demo_tenant_status(session)}


@router.post("/demo/seed")
def seed_demo(
    session: SessionDep,
    user: AdminUserDep,
    body: Optional[DemoSeedBody] = None,
):
    """Create demo companies (login: each email / demo1234) with rich data.

    Idempotent. Pass `email` to seed one DEMO_TENANTS entry (preferred on
    serverless). Omit `email` to run `seed_all_demos()` (local / tests).
    """
    from scripts.seed_demo import (  # lazy: avoids import cycle
        DEMO_TENANTS,
        seed_all_demos,
        seed_one_tenant,
    )

    target = (body.email if body else None) or None
    if target:
        target = target.strip().lower()
        match = next(
            ((e, c, m) for e, c, m in DEMO_TENANTS if e.lower() == target),
            None,
        )
        if not match:
            raise HTTPException(
                400,
                f"Unknown demo email. Expected one of: "
                f"{', '.join(e for e, _, _ in DEMO_TENANTS)}",
            )
        email, company, model = match
        try:
            report = seed_one_tenant(email, company, model)
        except Exception as exc:
            raise HTTPException(500, f"Seed failed for {email}: {exc}") from exc
        log_audit(session, user, "demo_seed", "system", None, {"email": email, "count": 1})
        session.commit()
        return {"tenants": [report]}

    reports = seed_all_demos()
    log_audit(session, user, "demo_seed", "system", None, {"count": len(reports)})
    session.commit()
    return {"tenants": reports}


@router.delete("/demo/seed")
def purge_demo(session: SessionDep, user: AdminUserDep):
    """Remove the demo companies and every row scoped to them.

    Rows are deleted in reverse dependency order (FK children first) using
    SQLModel.metadata.sorted_tables so no FK constraint violations occur.
    The caller's own tenant is never touched. The email list is derived from
    the seeder's DEMO_TENANTS so seed and purge can never drift apart.
    """
    from scripts.seed_demo import DEMO_TENANTS  # lazy: avoids import cycle
    from models import ComparativeStatement, Reconciliation, ReconciliationLine
    from models_healthcare import HcBed

    demo_emails = [email for email, _, _ in DEMO_TENANTS]
    demo_users = session.exec(select(User).where(User.email.in_(demo_emails))).all()
    tenant_ids = sorted({u.tenant_id for u in demo_users})
    removed = 0
    for tid in tenant_ids:
        # Null the FK-cycle back-pointers (excluded from sorted_tables via
        # use_alter) so the referenced rows can be deleted first under
        # Postgres FK enforcement.
        for table, col in (
            (ComparativeStatement.__table__, "po_id"),
            (HcBed.__table__, "current_admission_id"),
        ):
            session.execute(
                table.update().where(table.c.tenant_id == tid).values(**{col: None})
            )
        # ReconciliationLine has neither tenant_id nor ON DELETE CASCADE, so
        # the generic tenant_id sweep below never reaches it — delete via its
        # parent reconciliation first or the parent/journalentry deletes fail
        # under Postgres FK enforcement.
        session.execute(
            ReconciliationLine.__table__.delete().where(
                ReconciliationLine.__table__.c.reconciliation_id.in_(
                    select(Reconciliation.__table__.c.id).where(
                        Reconciliation.__table__.c.tenant_id == tid
                    )
                )
            )
        )
        # Delete all tenant-scoped child rows in reverse FK order.
        for table in reversed(SQLModel.metadata.sorted_tables):
            if "tenant_id" in table.c:
                session.execute(table.delete().where(table.c.tenant_id == tid))
        # Delete the tenant itself.
        session.execute(
            Tenant.__table__.delete().where(Tenant.__table__.c.id == tid)
        )
        removed += 1
    log_audit(session, user, "demo_purge", "system", None, {"removed": removed})
    session.commit()
    return {"removed_tenants": removed}
