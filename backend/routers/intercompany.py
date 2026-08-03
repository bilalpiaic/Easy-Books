"""Intercompany counterparties + reconciliation API (#261)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from services.intercompany import list_counterparties, recon_report
from services.permissions import perm_dep
from .common import CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/intercompany", tags=["intercompany"])


@router.get("/counterparties")
def get_counterparties(session: SessionDep, user: CurrentUserDep):
    """ConsolidationMember tenants available as IC counterparties for current tenant."""
    return list_counterparties(session, user.tenant_id)


@router.get("/recon", dependencies=[perm_dep("consolidation", "view")])
def get_recon(
    session: SessionDep,
    user: CurrentUserDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str = "",
):
    """IC AR vs AP reconciliation for the current (holding) tenant's entity graph."""
    return recon_report(session, user.tenant_id, skip=skip, limit=limit, q=q)
