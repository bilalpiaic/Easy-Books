"""In-app ops alerts — emit + refresh producers.

Staff-facing only. Customer overdue emails stay in services/overdue.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from models import (
    ApprovalRequest, ApprovalStep, ComparativeStatement, GateOutward,
    Invoice, PayrollRun, Product, PurchaseDemand, Settings, Tenant, User,
    UserAlert,
)
from services.money import D

STAFF_ROLES = ("owner", "admin", "accountant")
APPROVER_ROLES = ("owner", "admin")
REFRESH_INTERVAL = timedelta(minutes=5)
ALERTS_SETTING_KEY = "in_app_alerts"
LAST_REFRESH_KEY = "alerts_last_refresh"


def _tenant_setting(session: Session, tenant_id: int, key: str) -> str | None:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    return row.value if row else None


def _set_tenant_setting(session: Session, tenant_id: int, key: str, value: str) -> None:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    if row:
        row.value = value
        session.add(row)
    else:
        session.add(Settings(tenant_id=tenant_id, key=key, value=value))


def in_app_alerts_enabled(session: Session, tenant_id: int) -> bool:
    """Default on — only off when explicitly set to false."""
    return (_tenant_setting(session, tenant_id, ALERTS_SETTING_KEY) or "true").lower() != "false"


def _enabled_modules(session: Session, tenant_id: int) -> set[str]:
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return {"base"}
    try:
        return set(json.loads(tenant.enabled_modules or "[]"))
    except (TypeError, ValueError):
        return {"base"}


def emit_alert(
    session: Session,
    *,
    tenant_id: int,
    user_id: int,
    kind: str,
    title: str,
    dedupe_key: str,
    body: str | None = None,
    href: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    severity: str = "warning",
) -> bool:
    """Insert an alert unless (user_id, dedupe_key) already exists. Returns True if created."""
    existing = session.exec(
        select(UserAlert).where(
            UserAlert.user_id == user_id,
            UserAlert.dedupe_key == dedupe_key,
        )
    ).first()
    if existing:
        return False
    session.add(UserAlert(
        tenant_id=tenant_id,
        user_id=user_id,
        kind=kind,
        severity=severity,
        title=title,
        body=body,
        href=href,
        entity_type=entity_type,
        entity_id=entity_id,
        dedupe_key=dedupe_key,
    ))
    if kind in ("overdue_invoice", "approval_needed"):
        try:
            from services.push import fanout_push
            fanout_push(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                kind=kind,
                title=title,
                body=body or title,
                href=href,
            )
        except Exception as exc:
            print(f"[push] fanout failed: {exc}")
    return True


def _staff_users(session: Session, tenant_id: int, roles: tuple[str, ...]) -> list[User]:
    return list(session.exec(
        select(User).where(
            User.tenant_id == tenant_id,
            User.is_active == True,  # noqa: E712
            User.role.in_(roles),
        )
    ).all())


def _emit_to_users(
    session: Session,
    users: list[User],
    *,
    exclude_user_id: int | None = None,
    **kwargs,
) -> int:
    n = 0
    for u in users:
        if exclude_user_id is not None and u.id == exclude_user_id:
            continue
        if emit_alert(session, tenant_id=u.tenant_id, user_id=u.id, **kwargs):
            n += 1
    return n


def refresh_ops_alerts(
    session: Session,
    *,
    tenant_id: int | None = None,
    force: bool = False,
) -> int:
    """Scan ops conditions and emit deduped alerts. Returns count of new rows.

    When tenant_id is set, only that tenant is refreshed (and throttled unless
    force=True). When None, all tenants are refreshed (scheduler path).
    """
    if tenant_id is not None:
        tenants = [session.get(Tenant, tenant_id)]
        tenants = [t for t in tenants if t is not None]
    else:
        tenants = list(session.exec(select(Tenant)).all())

    created = 0
    now = datetime.utcnow()

    for tenant in tenants:
        tid = tenant.id
        if not in_app_alerts_enabled(session, tid):
            continue

        if not force and tenant_id is not None:
            last = _tenant_setting(session, tid, LAST_REFRESH_KEY)
            if last:
                try:
                    last_dt = datetime.fromisoformat(last)
                    if now - last_dt < REFRESH_INTERVAL:
                        continue
                except ValueError:
                    pass

        modules = _enabled_modules(session, tid)
        staff = _staff_users(session, tid, STAFF_ROLES)
        approvers = _staff_users(session, tid, APPROVER_ROLES)

        # ── Overdue invoices ──────────────────────────────────────────────
        overdue = session.exec(
            select(Invoice).where(
                Invoice.tenant_id == tid,
                Invoice.status == "overdue",
            )
        ).all()
        for inv in overdue:
            created += _emit_to_users(
                session, staff,
                kind="overdue_invoice",
                severity="critical",
                title=f"Overdue invoice {inv.number}",
                body=" · ".join(filter(None, [
                    inv.customer_name or "",
                    f"due {inv.due_date}" if inv.due_date else "",
                    f"total {inv.total}",
                ])),
                href=f"/invoices/{inv.id}",
                entity_type="invoice",
                entity_id=inv.id,
                dedupe_key=f"overdue:inv:{inv.id}",
            )

        # ── Low stock ─────────────────────────────────────────────────────
        if "inventory" in modules:
            low = session.exec(
                select(Product).where(
                    Product.tenant_id == tid,
                    Product.is_active == True,  # noqa: E712
                    Product.product_type == "stock",
                    Product.stock_qty <= Product.reorder_level,
                )
            ).all()
            for p in low:
                qty = D(p.stock_qty)
                reorder = D(p.reorder_level)
                # Skip zero-reorder products that are also at zero (noise)
                if reorder <= Decimal("0") and qty <= Decimal("0"):
                    continue
                created += _emit_to_users(
                    session, staff,
                    kind="low_stock",
                    severity="warning",
                    title=f"Low stock: {p.name}",
                    body=f"On hand {qty} · reorder at {reorder}",
                    href=f"/products/{p.id}",
                    entity_type="product",
                    entity_id=p.id,
                    dedupe_key=f"low_stock:prod:{p.id}",
                )

        # ── Pending approvals ─────────────────────────────────────────────
        if "purchase_store" in modules:
            for d in session.exec(
                select(PurchaseDemand).where(
                    PurchaseDemand.tenant_id == tid,
                    PurchaseDemand.status == "draft",
                )
            ).all():
                created += _emit_to_users(
                    session, approvers,
                    exclude_user_id=d.created_by_id,
                    kind="approval_needed",
                    severity="warning",
                    title=f"Approve purchase demand {d.number}",
                    body=d.purpose or "Awaiting approval",
                    href=f"/purchases/demands/{d.id}",
                    entity_type="purchase_demand",
                    entity_id=d.id,
                    dedupe_key=f"approval:pd:{d.id}",
                )

            for cs in session.exec(
                select(ComparativeStatement).where(
                    ComparativeStatement.tenant_id == tid,
                    ComparativeStatement.status == "draft",
                )
            ).all():
                created += _emit_to_users(
                    session, approvers,
                    exclude_user_id=cs.created_by_id,
                    kind="approval_needed",
                    severity="warning",
                    title=f"Approve comparative {cs.number}",
                    body="Vendor selection awaiting approval",
                    href=f"/purchases/comparatives/{cs.id}",
                    entity_type="comparative_statement",
                    entity_id=cs.id,
                    dedupe_key=f"approval:cs:{cs.id}",
                )

            for go in session.exec(
                select(GateOutward).where(
                    GateOutward.tenant_id == tid,
                    GateOutward.status == "draft",
                    GateOutward.source_doc_type == "scrap",
                )
            ).all():
                created += _emit_to_users(
                    session, approvers,
                    exclude_user_id=go.created_by_id,
                    kind="approval_needed",
                    severity="warning",
                    title=f"Approve scrap gate outward {go.number}",
                    body="Scrap exit awaiting approval (GL posts on approve)",
                    href=f"/store/gate-outward/{go.id}",
                    entity_type="gate_outward",
                    entity_id=go.id,
                    dedupe_key=f"approval:go:{go.id}",
                )

        if "hrm" in modules:
            for pr in session.exec(
                select(PayrollRun).where(
                    PayrollRun.tenant_id == tid,
                    PayrollRun.status == "draft",
                )
            ).all():
                created += _emit_to_users(
                    session, approvers,
                    exclude_user_id=pr.created_by_id,
                    kind="approval_needed",
                    severity="warning",
                    title=f"Approve payroll run {pr.period_start} → {pr.period_end}",
                    body=pr.notes or "Payroll run awaiting approval",
                    href=f"/payroll/{pr.id}",
                    entity_type="payroll_run",
                    entity_id=pr.id,
                    dedupe_key=f"approval:pr:{pr.id}",
                )

        # ── Generic approval-workflow inbox (#269) ────────────────────────
        for req in session.exec(
            select(ApprovalRequest).where(
                ApprovalRequest.tenant_id == tid,
                ApprovalRequest.status == "pending",
            )
        ).all():
            href = "/approvals"
            if req.document_type == "invoice":
                href = f"/invoices/{req.document_id}"
            elif req.document_type == "bill":
                href = f"/bills/{req.document_id}"
            # Notify staff who can act on the current step; exclude submitter.
            steps = session.exec(
                select(ApprovalStep).where(ApprovalStep.workflow_id == req.workflow_id)
                .order_by(ApprovalStep.step_order)  # type: ignore
            ).all()
            if req.current_step >= len(steps):
                continue
            step = steps[req.current_step]
            recipients = list(approvers)
            if step.approver_user_id:
                assigned = session.get(User, step.approver_user_id)
                if assigned and assigned.tenant_id == tid and assigned.is_active:
                    recipients = [assigned]
            elif step.approver_role:
                recipients = _staff_users(session, tid, (step.approver_role, "owner", "admin"))
            created += _emit_to_users(
                session, recipients,
                exclude_user_id=req.requested_by_id,
                kind="approval_needed",
                severity="warning",
                title=f"Approve {req.document_type} #{req.document_id}",
                body=f"Amount {req.amount} · awaiting approval",
                href=href,
                entity_type="approval_request",
                entity_id=req.id,
                dedupe_key=f"approval:req:{req.id}:step:{req.current_step}",
            )

        _set_tenant_setting(session, tid, LAST_REFRESH_KEY, now.isoformat())

    session.commit()
    return created
