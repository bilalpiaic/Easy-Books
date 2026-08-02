"""Multi-entity consolidation API (IFRS 10) — #255."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import ConsolidationElimination, ConsolidationMember, ConsolidationRun, Tenant
from services.consolidation import (
    ConsolError,
    build_statements,
    eligible_tenants,
    ensure_parent_member,
    list_members,
    period_is_locked,
    post_run,
    propose_eliminations,
    snapshot_member,
    user_can_access_tenant,
    void_run,
)
from services.money import money
from services.permissions import perm_dep
from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/consolidation", tags=["consolidation"])


def _http(exc: ConsolError) -> HTTPException:
    return HTTPException(exc.status_code, exc.message)


def _member_out(session, m: ConsolidationMember) -> dict:
    t = session.get(Tenant, m.member_tenant_id)
    return {
        "id": m.id,
        "holding_tenant_id": m.holding_tenant_id,
        "member_tenant_id": m.member_tenant_id,
        "tenant_name": (t.name if t else None) or f"Tenant {m.member_tenant_id}",
        "relationship": m.relationship,
        "ownership_pct": float(m.ownership_pct or 0),
        "label": m.label,
        "is_active": m.is_active,
        "ic_ar_code": m.ic_ar_code,
        "ic_ap_code": m.ic_ap_code,
        "created_at": m.created_at,
    }


def _run_out(r: ConsolidationRun, *, include_package: bool = False) -> dict:
    out = {
        "id": r.id,
        "holding_tenant_id": r.holding_tenant_id,
        "name": r.name,
        "period_start": r.period_start,
        "period_end": r.period_end,
        "status": r.status,
        "notes": r.notes,
        "posted_at": r.posted_at,
        "posted_by_id": r.posted_by_id,
        "voided_at": r.voided_at,
        "voided_by_id": r.voided_by_id,
        "created_at": r.created_at,
        "created_by_id": r.created_by_id,
    }
    if include_package:
        out["package"] = r.package_json
    return out


def _elim_out(e: ConsolidationElimination) -> dict:
    return {
        "id": e.id,
        "run_id": e.run_id,
        "kind": e.kind,
        "description": e.description,
        "account_code": e.account_code,
        "account_name": e.account_name,
        "account_type": e.account_type,
        "debit": float(e.debit or 0),
        "credit": float(e.credit or 0),
        "member_tenant_id": e.member_tenant_id,
        "sort_order": e.sort_order,
    }


def _get_run(session, user, run_id: int) -> ConsolidationRun:
    r = session.get(ConsolidationRun, run_id)
    if not r or r.holding_tenant_id != user.tenant_id:
        raise HTTPException(404, "Consolidation run not found")
    return r


# ── Members (entity graph) ───────────────────────────────────────────────────

class MemberIn(BaseModel):
    member_tenant_id: int
    relationship: str = "subsidiary"  # parent|subsidiary|associate
    ownership_pct: float = 100
    label: Optional[str] = None
    ic_ar_code: Optional[str] = None
    ic_ap_code: Optional[str] = None
    is_active: bool = True


class MemberPatch(BaseModel):
    relationship: Optional[str] = None
    ownership_pct: Optional[float] = None
    label: Optional[str] = None
    ic_ar_code: Optional[str] = None
    ic_ap_code: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/members", dependencies=[perm_dep("consolidation", "view")])
def get_members(session: SessionDep, user: CurrentUserDep):
    ensure_parent_member(session, user.tenant_id)
    return [_member_out(session, m) for m in list_members(session, user.tenant_id)]


@router.get("/eligible-tenants", dependencies=[perm_dep("consolidation", "view")])
def get_eligible(session: SessionDep, user: CurrentUserDep):
    return eligible_tenants(session, user)


@router.post("/members", status_code=201, dependencies=[perm_dep("consolidation", "edit")])
def add_member(body: MemberIn, session: SessionDep, user: WriteUserDep):
    ensure_parent_member(session, user.tenant_id)
    rel = (body.relationship or "subsidiary").lower()
    if rel not in ("parent", "subsidiary", "associate"):
        raise HTTPException(400, "relationship must be parent, subsidiary, or associate")
    if body.member_tenant_id == user.tenant_id and rel != "parent":
        raise HTTPException(400, "Holding company must use relationship=parent")
    if body.member_tenant_id != user.tenant_id and rel == "parent":
        raise HTTPException(400, "Only the holding tenant can be relationship=parent")
    if not user_can_access_tenant(session, user.id, body.member_tenant_id):
        raise HTTPException(403, "You must be a member of that tenant to add it")
    pct = money(body.ownership_pct)
    if pct < 0 or pct > 100:
        raise HTTPException(400, "ownership_pct must be 0–100")
    existing = session.exec(
        select(ConsolidationMember).where(
            ConsolidationMember.holding_tenant_id == user.tenant_id,
            ConsolidationMember.member_tenant_id == body.member_tenant_id,
        )
    ).first()
    if existing:
        raise HTTPException(400, "Member already in the entity graph")
    t = session.get(Tenant, body.member_tenant_id)
    m = ConsolidationMember(
        holding_tenant_id=user.tenant_id,
        member_tenant_id=body.member_tenant_id,
        relationship=rel,
        ownership_pct=pct,
        label=body.label or (t.name if t else None),
        is_active=body.is_active,
        ic_ar_code=body.ic_ar_code,
        ic_ap_code=body.ic_ap_code,
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    log_audit(session, user, "CREATE", "consolidation_member", m.id, {
        "member_tenant_id": m.member_tenant_id, "relationship": m.relationship,
    })
    return _member_out(session, m)


@router.patch("/members/{member_id}", dependencies=[perm_dep("consolidation", "edit")])
def patch_member(member_id: int, body: MemberPatch, session: SessionDep, user: WriteUserDep):
    m = session.get(ConsolidationMember, member_id)
    if not m or m.holding_tenant_id != user.tenant_id:
        raise HTTPException(404, "Member not found")
    if m.member_tenant_id == user.tenant_id and body.relationship and body.relationship != "parent":
        raise HTTPException(400, "Holding member must stay relationship=parent")
    if body.relationship is not None:
        rel = body.relationship.lower()
        if rel not in ("parent", "subsidiary", "associate"):
            raise HTTPException(400, "Invalid relationship")
        m.relationship = rel
    if body.ownership_pct is not None:
        pct = money(body.ownership_pct)
        if pct < 0 or pct > 100:
            raise HTTPException(400, "ownership_pct must be 0–100")
        m.ownership_pct = pct
    if body.label is not None:
        m.label = body.label
    if body.ic_ar_code is not None:
        m.ic_ar_code = body.ic_ar_code or None
    if body.ic_ap_code is not None:
        m.ic_ap_code = body.ic_ap_code or None
    if body.is_active is not None:
        if m.member_tenant_id == user.tenant_id and not body.is_active:
            raise HTTPException(400, "Cannot deactivate the parent entity")
        m.is_active = body.is_active
    session.add(m)
    session.commit()
    session.refresh(m)
    return _member_out(session, m)


@router.delete("/members/{member_id}", status_code=204, dependencies=[perm_dep("consolidation", "edit")])
def delete_member(member_id: int, session: SessionDep, user: WriteUserDep):
    m = session.get(ConsolidationMember, member_id)
    if not m or m.holding_tenant_id != user.tenant_id:
        raise HTTPException(404, "Member not found")
    if m.member_tenant_id == user.tenant_id:
        raise HTTPException(400, "Cannot remove the parent entity")
    session.delete(m)
    session.commit()
    return None


# ── Runs ─────────────────────────────────────────────────────────────────────

class RunIn(BaseModel):
    period_start: str
    period_end: str
    name: Optional[str] = None
    notes: Optional[str] = None


class ManualElimIn(BaseModel):
    description: str = ""
    account_code: str
    account_name: str = ""
    account_type: str = "Equity"
    debit: float = 0
    credit: float = 0
    member_tenant_id: Optional[int] = None


@router.get("/runs", dependencies=[perm_dep("consolidation", "view")])
def list_runs(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(ConsolidationRun)
        .where(ConsolidationRun.holding_tenant_id == user.tenant_id)
        .order_by(ConsolidationRun.id.desc())  # type: ignore
    ).all()
    return [_run_out(r) for r in rows]


@router.post("/runs", status_code=201, dependencies=[perm_dep("consolidation", "edit")])
def create_run(body: RunIn, session: SessionDep, user: WriteUserDep):
    if not body.period_start or not body.period_end:
        raise HTTPException(400, "period_start and period_end are required")
    if body.period_end < body.period_start:
        raise HTTPException(400, "period_end must be on/after period_start")
    ensure_parent_member(session, user.tenant_id)
    r = ConsolidationRun(
        holding_tenant_id=user.tenant_id,
        name=body.name or f"Consolidation {body.period_start} → {body.period_end}",
        period_start=body.period_start,
        period_end=body.period_end,
        notes=body.notes,
        status="draft",
        created_by_id=user.id,
    )
    session.add(r)
    session.commit()
    session.refresh(r)
    log_audit(session, user, "CREATE", "consolidation_run", r.id, {
        "period_start": r.period_start, "period_end": r.period_end,
    })
    return _run_out(r)


@router.get("/runs/{run_id}", dependencies=[perm_dep("consolidation", "view")])
def get_run(run_id: int, session: SessionDep, user: CurrentUserDep):
    r = _get_run(session, user, run_id)
    return _run_out(r, include_package=True)


@router.get("/runs/{run_id}/statements", dependencies=[perm_dep("consolidation", "view")])
def get_statements(run_id: int, session: SessionDep, user: CurrentUserDep):
    r = _get_run(session, user, run_id)
    if r.status == "posted" and r.package_json:
        return r.package_json
    return build_statements(session, r)


@router.get("/runs/{run_id}/eliminations", dependencies=[perm_dep("consolidation", "view")])
def get_elims(run_id: int, session: SessionDep, user: CurrentUserDep):
    _get_run(session, user, run_id)
    rows = session.exec(
        select(ConsolidationElimination)
        .where(ConsolidationElimination.run_id == run_id)
        .order_by(ConsolidationElimination.sort_order, ConsolidationElimination.id)
    ).all()
    return [_elim_out(e) for e in rows]


@router.post("/runs/{run_id}/propose", dependencies=[perm_dep("consolidation", "edit")])
def propose(run_id: int, session: SessionDep, user: WriteUserDep):
    r = _get_run(session, user, run_id)
    members = [m for m in list_members(session, user.tenant_id) if m.is_active]
    snaps = [snapshot_member(session, m, r.period_start, r.period_end) for m in members]
    try:
        lines = propose_eliminations(session, r, snaps)
    except ConsolError as e:
        raise _http(e)
    log_audit(session, user, "PROPOSE", "consolidation_run", r.id, {"lines": len(lines)})
    return [_elim_out(e) for e in lines]


@router.post(
    "/runs/{run_id}/eliminations",
    status_code=201,
    dependencies=[perm_dep("consolidation", "edit")],
)
def add_manual_elim(run_id: int, body: ManualElimIn, session: SessionDep, user: WriteUserDep):
    r = _get_run(session, user, run_id)
    if r.status != "draft":
        raise HTTPException(400, "Can only edit eliminations on a draft run")
    debit, credit = money(body.debit), money(body.credit)
    if (debit > 0 and credit > 0) or (debit == 0 and credit == 0):
        raise HTTPException(400, "Provide exactly one of debit or credit > 0")
    atype = body.account_type or "Equity"
    if atype not in ("Asset", "Liability", "Equity", "Revenue", "Expense"):
        raise HTTPException(400, "Invalid account_type")
    e = ConsolidationElimination(
        holding_tenant_id=user.tenant_id,
        run_id=r.id,
        kind="manual",
        description=body.description or "Manual elimination",
        account_code=body.account_code,
        account_name=body.account_name or body.account_code,
        account_type=atype,
        debit=debit,
        credit=credit,
        member_tenant_id=body.member_tenant_id,
        sort_order=999,
    )
    session.add(e)
    session.commit()
    session.refresh(e)
    return _elim_out(e)


@router.delete(
    "/runs/{run_id}/eliminations/{elim_id}",
    status_code=204,
    dependencies=[perm_dep("consolidation", "edit")],
)
def delete_elim(run_id: int, elim_id: int, session: SessionDep, user: WriteUserDep):
    r = _get_run(session, user, run_id)
    if r.status != "draft":
        raise HTTPException(400, "Can only edit eliminations on a draft run")
    e = session.get(ConsolidationElimination, elim_id)
    if not e or e.run_id != run_id or e.holding_tenant_id != user.tenant_id:
        raise HTTPException(404, "Elimination not found")
    session.delete(e)
    session.commit()
    return None


@router.post("/runs/{run_id}/post", dependencies=[perm_dep("consolidation", "edit")])
def post(run_id: int, session: SessionDep, user: WriteUserDep):
    r = _get_run(session, user, run_id)
    locked = period_is_locked(session, user.tenant_id, r.period_start, r.period_end)
    try:
        r = post_run(session, r, user)
    except ConsolError as e:
        raise _http(e)
    log_audit(session, user, "POST", "consolidation_run", r.id, {
        "locked_period_override": locked and user.role in ("owner", "admin"),
    })
    return _run_out(r, include_package=True)


@router.post("/runs/{run_id}/void", dependencies=[perm_dep("consolidation", "edit")])
def void(run_id: int, session: SessionDep, user: WriteUserDep):
    r = _get_run(session, user, run_id)
    try:
        r = void_run(session, r, user)
    except ConsolError as e:
        raise _http(e)
    log_audit(session, user, "VOID", "consolidation_run", r.id, {})
    return _run_out(r)
