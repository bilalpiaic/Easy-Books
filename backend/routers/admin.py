"""Admin-only maintenance endpoints: load/remove the demo sample data.

Demo tenants are SEPARATE from the caller's own tenant, so loading them never
touches the user's real books. The seeder (scripts.seed_demo) is idempotent.
Imported lazily to avoid a db <-> scripts.seed_demo import cycle.
"""
from fastapi import APIRouter
from sqlmodel import SQLModel, select

from models import Tenant, User
from .common import AdminUserDep, SessionDep, log_audit

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/demo/seed")
def seed_demo(session: SessionDep, user: AdminUserDep):
    """Create the demo companies (login: each email / demo1234) with rich data.

    Idempotent — safe to call multiple times. Each call returns a per-tenant
    report dict that includes the 'email' key so the caller can confirm which
    tenants were created/updated.
    """
    from scripts.seed_demo import seed_all_demos  # lazy: avoids import cycle
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
    from models import ComparativeStatement
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
