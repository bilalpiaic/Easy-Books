"""Multi-step approval workflows (#123)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import (
    ApprovalRequest, ApprovalStep, ApprovalWorkflow, Bill, Invoice,
)
from services.permissions import perm_dep
from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


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


@router.get("/workflows")
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
        steps = session.exec(
            select(ApprovalStep).where(ApprovalStep.workflow_id == wf.id)
            .order_by(ApprovalStep.step_order)  # type: ignore
        ).all()
        out.append({
            "id": wf.id, "document_type": wf.document_type, "name": wf.name,
            "is_active": wf.is_active,
            "steps": [s.model_dump() for s in steps],
        })
    return out


@router.post("/workflows", status_code=201, dependencies=[perm_dep("settings", "edit")] if False else [])
def create_workflow(body: WorkflowIn, session: SessionDep, user: WriteUserDep):
    if body.document_type not in ("invoice", "bill", "purchase_order", "journal"):
        raise HTTPException(400, "Invalid document_type")
    wf = ApprovalWorkflow(
        tenant_id=user.tenant_id, document_type=body.document_type,
        name=body.name, is_active=body.is_active,
    )
    session.add(wf)
    session.commit()
    session.refresh(wf)
    for st in body.steps:
        session.add(ApprovalStep(workflow_id=wf.id, **st.model_dump()))
    session.commit()
    log_audit(session, user, "CREATE", "approval_workflow", wf.id, {"name": wf.name})
    session.commit()
    return {"id": wf.id}


@router.get("")
def list_pending(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(ApprovalRequest).where(
            ApprovalRequest.tenant_id == user.tenant_id,
            ApprovalRequest.status == "pending",
        ).order_by(ApprovalRequest.id.desc())  # type: ignore
    ).all()
    # Filter to requests the current user can act on
    visible = []
    for req in rows:
        steps = session.exec(
            select(ApprovalStep).where(ApprovalStep.workflow_id == req.workflow_id)
            .order_by(ApprovalStep.step_order)  # type: ignore
        ).all()
        if req.current_step >= len(steps):
            continue
        step = steps[req.current_step]
        if step.approver_user_id and step.approver_user_id != user.id:
            continue
        if step.approver_role and step.approver_role != user.role and user.role not in ("owner", "admin"):
            continue
        visible.append(req.model_dump())
    return visible


@router.get("/history")
def history(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(ApprovalRequest).where(
            ApprovalRequest.tenant_id == user.tenant_id,
            ApprovalRequest.status != "pending",
        ).order_by(ApprovalRequest.id.desc()).limit(100)  # type: ignore
    ).all()
    return [r.model_dump() for r in rows]


@router.post("/{request_id}/approve")
def approve(request_id: int, body: DecisionIn, session: SessionDep, user: WriteUserDep):
    req = session.get(ApprovalRequest, request_id)
    if not req or req.tenant_id != user.tenant_id or req.status != "pending":
        raise HTTPException(404, "Approval request not found")
    steps = session.exec(
        select(ApprovalStep).where(ApprovalStep.workflow_id == req.workflow_id)
        .order_by(ApprovalStep.step_order)  # type: ignore
    ).all()
    req.current_step += 1
    if req.current_step >= len(steps):
        req.status = "approved"
        req.resolved_at = datetime.utcnow()
        req.notes = body.notes
        _set_doc_status(session, req, "approved")
    session.add(req)
    session.commit()
    return req.model_dump()


@router.post("/{request_id}/reject")
def reject(request_id: int, body: DecisionIn, session: SessionDep, user: WriteUserDep):
    if not body.notes:
        raise HTTPException(400, "Rejection notes are required")
    req = session.get(ApprovalRequest, request_id)
    if not req or req.tenant_id != user.tenant_id or req.status != "pending":
        raise HTTPException(404, "Approval request not found")
    req.status = "rejected"
    req.resolved_at = datetime.utcnow()
    req.notes = body.notes
    _set_doc_status(session, req, "rejected")
    session.add(req)
    session.commit()
    return req.model_dump()


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
    steps = session.exec(
        select(ApprovalStep).where(ApprovalStep.workflow_id == wf.id)
        .order_by(ApprovalStep.step_order)  # type: ignore
    ).all()
    # Skip steps whose min_amount is above this document
    start = 0
    for i, st in enumerate(steps):
        if st.min_amount is not None and amount < st.min_amount:
            start = i + 1
    if start >= len(steps):
        return None
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
    )
    session.add(req)
    session.flush()
    _set_doc_status(session, req, "pending")
    return req
