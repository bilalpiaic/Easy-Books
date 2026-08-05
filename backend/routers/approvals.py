"""Multi-step approval workflows (#123) + SoD / thresholds / substitutes (#269)."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlmodel import select

from models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStep,
    ApprovalSubstitute,
    ApprovalWorkflow,
    Bill,
    Invoice,
    Settings,
    User,
)
from services.approval_document_types import is_valid_document_type, list_document_types
from services.permissions import perm_dep
from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/approvals", tags=["approvals"])

SOD_SETTING_KEY = "approvals_block_self_approval"
SOD_MESSAGE = "A document cannot be approved or rejected by its submitter"


# ── schemas ──────────────────────────────────────────────────────────────────

class StepIn(BaseModel):
    step_order: int = 0
    approver_role: Optional[str] = None
    approver_user_id: Optional[int] = None
    min_amount: Optional[float] = None
    timeout_hours: Optional[int] = None


class WorkflowIn(BaseModel):
    document_type: str
    name: str
    is_active: bool = True
    steps: List[StepIn] = []


class DecisionIn(BaseModel):
    notes: Optional[str] = None


class SubstituteIn(BaseModel):
    user_id: Optional[int] = None  # defaults to current user (self-OOO)
    substitute_user_id: int
    starts_on: str
    ends_on: str
    is_active: bool = True


class SubstituteUpdate(BaseModel):
    substitute_user_id: Optional[int] = None
    starts_on: Optional[str] = None
    ends_on: Optional[str] = None
    is_active: Optional[bool] = None


# ── helpers ──────────────────────────────────────────────────────────────────

def _sod_enabled(session, tenant_id: int) -> bool:
    """Default on when unset — mid-market SoD expectation (#269)."""
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == tenant_id,
            Settings.key == SOD_SETTING_KEY,
        )
    ).first()
    return (row.value if row else "true").lower() != "false"


def _assert_sod(session, user: User, req: ApprovalRequest) -> None:
    if _sod_enabled(session, user.tenant_id) and req.requested_by_id == user.id:
        raise HTTPException(400, SOD_MESSAGE)


def _applicable_indices(steps: list[ApprovalStep], amount: float) -> list[int]:
    """Steps that apply when amount >= min_amount (null min = always)."""
    return [
        i for i, st in enumerate(steps)
        if st.min_amount is None or amount >= float(st.min_amount)
    ]


def _next_applicable_index(
    steps: list[ApprovalStep], amount: float, after_index: int
) -> Optional[int]:
    for i in _applicable_indices(steps, amount):
        if i > after_index:
            return i
    return None


def _workflow_steps(session, workflow_id: int) -> list[ApprovalStep]:
    return list(session.exec(
        select(ApprovalStep).where(ApprovalStep.workflow_id == workflow_id)
        .order_by(ApprovalStep.step_order)  # type: ignore
    ).all())


def _is_active_substitute(
    session, tenant_id: int, principal_id: int, actor_id: int
) -> bool:
    today = date.today().isoformat()
    row = session.exec(
        select(ApprovalSubstitute).where(
            ApprovalSubstitute.tenant_id == tenant_id,
            ApprovalSubstitute.user_id == principal_id,
            ApprovalSubstitute.substitute_user_id == actor_id,
            ApprovalSubstitute.is_active == True,  # noqa: E712
            ApprovalSubstitute.starts_on <= today,
            ApprovalSubstitute.ends_on >= today,
        )
    ).first()
    return row is not None


def _can_act(session, user: User, step: ApprovalStep) -> bool:
    """Whether user may act on this step (assignment / role / substitute)."""
    if step.approver_user_id is not None:
        if step.approver_user_id == user.id:
            return True
        return _is_active_substitute(
            session, user.tenant_id, step.approver_user_id, user.id
        )
    if step.approver_role:
        if user.role == step.approver_role or user.role in ("owner", "admin"):
            return True
        principals = session.exec(
            select(User).where(
                User.tenant_id == user.tenant_id,
                User.role == step.approver_role,
                User.is_active == True,  # noqa: E712
            )
        ).all()
        for p in principals:
            if _is_active_substitute(session, user.tenant_id, p.id, user.id):
                return True
        return False
    return False


def _append_decision(
    session,
    user: User,
    req: ApprovalRequest,
    action: str,
    notes: Optional[str],
) -> None:
    session.add(ApprovalDecision(
        tenant_id=user.tenant_id,
        request_id=req.id,
        actor_id=user.id,
        action=action,
        step_index=req.current_step,
        notes=notes,
    ))


def _serialize_request(req: ApprovalRequest, steps: list[ApprovalStep] | None = None) -> dict:
    data = req.model_dump()
    if steps is not None and 0 <= req.current_step < len(steps):
        st = steps[req.current_step]
        data["step"] = {
            "step_order": st.step_order,
            "approver_role": st.approver_role,
            "approver_user_id": st.approver_user_id,
            "min_amount": st.min_amount,
        }
    return data


def _validate_dates(starts_on: str, ends_on: str) -> None:
    try:
        s = date.fromisoformat(starts_on)
        e = date.fromisoformat(ends_on)
    except ValueError as exc:
        raise HTTPException(400, "starts_on and ends_on must be YYYY-MM-DD") from exc
    if e < s:
        raise HTTPException(400, "ends_on must be on or after starts_on")


def _set_doc_status(session, req: ApprovalRequest, status: str) -> None:
    if req.document_type == "invoice":
        doc = session.get(Invoice, req.document_id)
    elif req.document_type == "bill":
        doc = session.get(Bill, req.document_id)
    else:
        return
    if doc and doc.tenant_id == req.tenant_id:
        doc.approval_status = status
        if status == "rejected":
            doc.status = "draft"
        session.add(doc)


def _replace_steps(session, workflow_id: int, steps: list[StepIn]) -> None:
    existing = session.exec(
        select(ApprovalStep).where(ApprovalStep.workflow_id == workflow_id)
    ).all()
    for st in existing:
        session.delete(st)
    session.flush()
    for st in steps:
        if not st.approver_role and not st.approver_user_id:
            raise HTTPException(400, "Each step needs approver_role or approver_user_id")
        session.add(ApprovalStep(workflow_id=workflow_id, **st.model_dump()))


# ── document-type LOV ────────────────────────────────────────────────────────

@router.get("/document-types", dependencies=[perm_dep("approvals.workflows", "view")])
def document_types(session: SessionDep, user: CurrentUserDep):
    """Document Type LOV for Approval Workflows.

    Seeded from every document type available across all tenant business
    models / installed modules, plus any keys already stored on workflows
    in any tenant.
    """
    _ = user  # auth + tenant gate via dependency
    return list_document_types(session)


# ── workflows ────────────────────────────────────────────────────────────────

@router.get("/workflows", dependencies=[perm_dep("approvals.workflows", "view")])
def list_workflows(
    session: SessionDep,
    user: CurrentUserDep,
    document_type: Optional[str] = None,
):
    q = select(ApprovalWorkflow).where(ApprovalWorkflow.tenant_id == user.tenant_id)
    if document_type:
        q = q.where(ApprovalWorkflow.document_type == document_type)
    rows = session.exec(q).all()
    out = []
    for wf in rows:
        steps = _workflow_steps(session, wf.id)
        out.append({
            "id": wf.id, "document_type": wf.document_type, "name": wf.name,
            "is_active": wf.is_active,
            "steps": [s.model_dump() for s in steps],
        })
    return out


@router.post(
    "/workflows",
    status_code=201,
    dependencies=[perm_dep("approvals.workflows", "edit")],
)
def create_workflow(body: WorkflowIn, session: SessionDep, user: WriteUserDep):
    if not is_valid_document_type(session, body.document_type):
        raise HTTPException(400, "Invalid document_type")
    if not body.steps:
        raise HTTPException(400, "At least one step is required")
    wf = ApprovalWorkflow(
        tenant_id=user.tenant_id, document_type=body.document_type,
        name=body.name, is_active=body.is_active,
    )
    session.add(wf)
    session.commit()
    session.refresh(wf)
    _replace_steps(session, wf.id, body.steps)
    session.commit()
    log_audit(session, user, "CREATE", "approval_workflow", wf.id, {"name": wf.name})
    session.commit()
    return {"id": wf.id}


@router.put("/workflows/{workflow_id}", dependencies=[perm_dep("approvals.workflows", "edit")])
def update_workflow(
    workflow_id: int, body: WorkflowIn, session: SessionDep, user: WriteUserDep
):
    wf = session.get(ApprovalWorkflow, workflow_id)
    if not wf or wf.tenant_id != user.tenant_id:
        raise HTTPException(404, "Workflow not found")
    if not is_valid_document_type(session, body.document_type):
        raise HTTPException(400, "Invalid document_type")
    if not body.steps:
        raise HTTPException(400, "At least one step is required")
    wf.document_type = body.document_type
    wf.name = body.name
    wf.is_active = body.is_active
    session.add(wf)
    _replace_steps(session, wf.id, body.steps)
    log_audit(session, user, "UPDATE", "approval_workflow", wf.id, {"name": wf.name})
    session.commit()
    return {"id": wf.id}


@router.delete("/workflows/{workflow_id}", dependencies=[perm_dep("approvals.workflows", "edit")])
def delete_workflow(workflow_id: int, session: SessionDep, user: WriteUserDep):
    wf = session.get(ApprovalWorkflow, workflow_id)
    if not wf or wf.tenant_id != user.tenant_id:
        raise HTTPException(404, "Workflow not found")
    pending = session.exec(
        select(ApprovalRequest).where(
            ApprovalRequest.workflow_id == wf.id,
            ApprovalRequest.status == "pending",
        )
    ).first()
    if pending:
        raise HTTPException(400, "Cannot delete a workflow with pending requests")
    for st in _workflow_steps(session, wf.id):
        session.delete(st)
    session.delete(wf)
    log_audit(session, user, "DELETE", "approval_workflow", workflow_id, {})
    session.commit()
    return {"ok": True}


# ── substitutes ──────────────────────────────────────────────────────────────

@router.get("/substitutes", dependencies=[perm_dep("approvals", "view")])
def list_substitutes(session: SessionDep, user: CurrentUserDep):
    q = select(ApprovalSubstitute).where(ApprovalSubstitute.tenant_id == user.tenant_id)
    if user.role not in ("owner", "admin"):
        q = q.where(or_(
            ApprovalSubstitute.user_id == user.id,
            ApprovalSubstitute.substitute_user_id == user.id,
        ))
    rows = session.exec(q.order_by(ApprovalSubstitute.id.desc())).all()  # type: ignore
    return [r.model_dump() for r in rows]


@router.get("/substitutes/me", dependencies=[perm_dep("approvals", "view")])
def list_my_substitutes(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(ApprovalSubstitute).where(
            ApprovalSubstitute.tenant_id == user.tenant_id,
            ApprovalSubstitute.user_id == user.id,
        ).order_by(ApprovalSubstitute.id.desc())  # type: ignore
    ).all()
    return [r.model_dump() for r in rows]


@router.post(
    "/substitutes",
    status_code=201,
    dependencies=[perm_dep("approvals", "edit")],
)
def create_substitute(body: SubstituteIn, session: SessionDep, user: WriteUserDep):
    principal_id = body.user_id if body.user_id is not None else user.id
    if principal_id != user.id and user.role not in ("owner", "admin"):
        raise HTTPException(403, "Only admin/owner can set substitutes for others")
    if principal_id == body.substitute_user_id:
        raise HTTPException(400, "Cannot designate yourself as your own substitute")
    _validate_dates(body.starts_on, body.ends_on)
    for uid in (principal_id, body.substitute_user_id):
        u = session.get(User, uid)
        if not u or u.tenant_id != user.tenant_id or not u.is_active:
            raise HTTPException(400, "Invalid user for this tenant")
    row = ApprovalSubstitute(
        tenant_id=user.tenant_id,
        user_id=principal_id,
        substitute_user_id=body.substitute_user_id,
        starts_on=body.starts_on,
        ends_on=body.ends_on,
        is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row.model_dump()


@router.put("/substitutes/{sub_id}", dependencies=[perm_dep("approvals", "edit")])
def update_substitute(
    sub_id: int, body: SubstituteUpdate, session: SessionDep, user: WriteUserDep
):
    row = session.get(ApprovalSubstitute, sub_id)
    if not row or row.tenant_id != user.tenant_id:
        raise HTTPException(404, "Substitute not found")
    if row.user_id != user.id and user.role not in ("owner", "admin"):
        raise HTTPException(403, "Only admin/owner can edit substitutes for others")
    data = body.model_dump(exclude_unset=True)
    if "substitute_user_id" in data and data["substitute_user_id"] == row.user_id:
        raise HTTPException(400, "Cannot designate yourself as your own substitute")
    starts = data.get("starts_on", row.starts_on)
    ends = data.get("ends_on", row.ends_on)
    _validate_dates(starts, ends)
    if "substitute_user_id" in data:
        u = session.get(User, data["substitute_user_id"])
        if not u or u.tenant_id != user.tenant_id or not u.is_active:
            raise HTTPException(400, "Invalid substitute user")
    for k, v in data.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row.model_dump()


@router.delete("/substitutes/{sub_id}", dependencies=[perm_dep("approvals", "edit")])
def delete_substitute(sub_id: int, session: SessionDep, user: WriteUserDep):
    row = session.get(ApprovalSubstitute, sub_id)
    if not row or row.tenant_id != user.tenant_id:
        raise HTTPException(404, "Substitute not found")
    if row.user_id != user.id and user.role not in ("owner", "admin"):
        raise HTTPException(403, "Only admin/owner can delete substitutes for others")
    session.delete(row)
    session.commit()
    return {"ok": True}


# ── inbox / history / act ────────────────────────────────────────────────────

@router.get("", dependencies=[perm_dep("approvals", "view")])
def list_pending(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(ApprovalRequest).where(
            ApprovalRequest.tenant_id == user.tenant_id,
            ApprovalRequest.status == "pending",
        ).order_by(ApprovalRequest.id.desc())  # type: ignore
    ).all()
    sod_on = _sod_enabled(session, user.tenant_id)
    visible = []
    for req in rows:
        if sod_on and req.requested_by_id == user.id:
            continue
        steps = _workflow_steps(session, req.workflow_id)
        if req.current_step >= len(steps):
            continue
        step = steps[req.current_step]
        if not _can_act(session, user, step):
            continue
        visible.append(_serialize_request(req, steps))
    return visible


@router.get("/history", dependencies=[perm_dep("approvals", "view")])
def history(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(ApprovalRequest).where(
            ApprovalRequest.tenant_id == user.tenant_id,
            ApprovalRequest.status != "pending",
        ).order_by(ApprovalRequest.id.desc()).limit(100)  # type: ignore
    ).all()
    return [r.model_dump() for r in rows]


@router.get("/{request_id}/decisions", dependencies=[perm_dep("approvals", "view")])
def list_decisions(request_id: int, session: SessionDep, user: CurrentUserDep):
    req = session.get(ApprovalRequest, request_id)
    if not req or req.tenant_id != user.tenant_id:
        raise HTTPException(404, "Approval request not found")
    rows = session.exec(
        select(ApprovalDecision).where(
            ApprovalDecision.request_id == request_id,
            ApprovalDecision.tenant_id == user.tenant_id,
        ).order_by(ApprovalDecision.id)  # type: ignore
    ).all()
    return [r.model_dump() for r in rows]


@router.post("/{request_id}/approve", dependencies=[perm_dep("approvals", "edit")])
def approve(request_id: int, body: DecisionIn, session: SessionDep, user: WriteUserDep):
    req = session.get(ApprovalRequest, request_id)
    if not req or req.tenant_id != user.tenant_id or req.status != "pending":
        raise HTTPException(404, "Approval request not found")
    _assert_sod(session, user, req)
    steps = _workflow_steps(session, req.workflow_id)
    if req.current_step >= len(steps):
        raise HTTPException(400, "Approval request has no current step")
    step = steps[req.current_step]
    if not _can_act(session, user, step):
        raise HTTPException(403, "You are not an approver for this step")
    _append_decision(session, user, req, "approve", body.notes)
    nxt = _next_applicable_index(steps, float(req.amount or 0), req.current_step)
    if nxt is None:
        req.status = "approved"
        req.resolved_at = datetime.utcnow()
        req.notes = body.notes
        _set_doc_status(session, req, "approved")
    else:
        req.current_step = nxt
    session.add(req)
    session.commit()
    session.refresh(req)
    return _serialize_request(req, steps)


@router.post("/{request_id}/reject", dependencies=[perm_dep("approvals", "edit")])
def reject(request_id: int, body: DecisionIn, session: SessionDep, user: WriteUserDep):
    if not body.notes:
        raise HTTPException(400, "Rejection notes are required")
    req = session.get(ApprovalRequest, request_id)
    if not req or req.tenant_id != user.tenant_id or req.status != "pending":
        raise HTTPException(404, "Approval request not found")
    _assert_sod(session, user, req)
    steps = _workflow_steps(session, req.workflow_id)
    if req.current_step >= len(steps):
        raise HTTPException(400, "Approval request has no current step")
    step = steps[req.current_step]
    if not _can_act(session, user, step):
        raise HTTPException(403, "You are not an approver for this step")
    _append_decision(session, user, req, "reject", body.notes)
    req.status = "rejected"
    req.resolved_at = datetime.utcnow()
    req.notes = body.notes
    _set_doc_status(session, req, "rejected")
    session.add(req)
    session.commit()
    session.refresh(req)
    return req.model_dump()


def submit_document(session, user, document_type: str, document_id: int, amount: float):
    """Create ApprovalRequest if an active workflow exists; else no-op.

    When a request is created, sets the document's approval_status to 'pending'.
    """
    wf = session.exec(
        select(ApprovalWorkflow).where(
            ApprovalWorkflow.tenant_id == user.tenant_id,
            ApprovalWorkflow.document_type == document_type,
            ApprovalWorkflow.is_active == True,  # noqa: E712
        )
    ).first()
    if not wf:
        return None
    steps = _workflow_steps(session, wf.id)
    applicable = _applicable_indices(steps, float(amount))
    if not applicable:
        return None
    start = applicable[0]
    # Avoid duplicate pending requests for the same document
    existing = session.exec(
        select(ApprovalRequest).where(
            ApprovalRequest.tenant_id == user.tenant_id,
            ApprovalRequest.document_type == document_type,
            ApprovalRequest.document_id == document_id,
            ApprovalRequest.status == "pending",
        )
    ).first()
    if existing:
        return existing
    req = ApprovalRequest(
        tenant_id=user.tenant_id, workflow_id=wf.id,
        document_type=document_type, document_id=document_id,
        current_step=start, requested_by_id=user.id,
        amount=float(amount),
    )
    session.add(req)
    session.flush()
    _set_doc_status(session, req, "pending")
    return req
