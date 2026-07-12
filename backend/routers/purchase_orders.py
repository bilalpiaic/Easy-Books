"""Purchase Orders — pre-approval workflow before billing. IAS 2 control flow."""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import (
    Bill,
    BillLine,
    ComparativeStatement,
    PurchaseDemand,
    PurchaseOrder,
    PurchaseOrderLine,
    SequenceCounter,
    Settings,
    Tenant,
    Vendor,
)
from routers.common import AdminUserDep, SessionDep, WriteUserDep, log_audit, next_number
from services.money import D, money
from services.posting import EntryInput, post_transaction
from routers.common import get_or_create_account
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"], dependencies=[perm_dep("purchase_orders")])


class POLineCreate(BaseModel):
    product_id: Optional[int] = None
    description: str
    qty: Decimal = Decimal("1")
    unit: Optional[str] = None
    rate: Decimal = Decimal("0")


class POCreate(BaseModel):
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    order_date: str
    expected_date: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    lines: List[POLineCreate] = []
    demand_id: Optional[int] = None
    comparative_id: Optional[int] = None


class BillConvert(BaseModel):
    bill_date: str
    due_date: str


@router.get("")
def list_pos(
    session: SessionDep, user: WriteUserDep,
    status: Optional[str] = None, skip: int = 0, limit: int = 50,
):
    q = select(PurchaseOrder).where(PurchaseOrder.tenant_id == user.tenant_id)
    if status:
        q = q.where(PurchaseOrder.status == status)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(PurchaseOrder.order_date.desc()).offset(skip).limit(limit)).all()
    return {"total": total, "items": items}


@router.get("/{po_id}")
def get_po(session: SessionDep, user: WriteUserDep, po_id: int):
    po = session.exec(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == user.tenant_id
        )
    ).first()
    if not po:
        raise HTTPException(404, "Purchase order not found")
    lines = session.exec(
        select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po_id)
    ).all()
    out = {**po.model_dump(), "lines": [ln.model_dump() for ln in lines]}

    from services.gate import gi_coverage
    out["gi_coverage"] = {
        str(k): str(v) for k, v in gi_coverage(session, user.tenant_id, po.id).items()
    }
    out["gate_required"] = _gate_required(session, user.tenant_id)
    return out


def _chain_required(session, tenant_id: int) -> bool:
    """True when purchase_store is installed AND require_purchase_chain isn't 'false'."""
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return False
    from routers.modules import _get_enabled
    if "purchase_store" not in _get_enabled(tenant):
        return False
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == tenant_id, Settings.key == "require_purchase_chain"
        )
    ).first()
    return not (row and str(row.value).strip().lower() == "false")


def _gate_required(session, tenant_id: int) -> bool:
    """True when purchase_store is installed AND require_gate_inward isn't 'false'."""
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return False
    from routers.modules import _get_enabled
    if "purchase_store" not in _get_enabled(tenant):
        return False
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == tenant_id, Settings.key == "require_gate_inward"
        )
    ).first()
    return not (row and str(row.value).strip().lower() == "false")


@router.post("", status_code=201)
def create_po(session: SessionDep, user: WriteUserDep, body: POCreate):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")

    if body.demand_id:
        demand = session.exec(
            select(PurchaseDemand).where(
                PurchaseDemand.id == body.demand_id,
                PurchaseDemand.tenant_id == user.tenant_id,
            )
        ).first()
        if not demand:
            raise HTTPException(400, "demand_id does not reference a demand in this tenant")

    if body.comparative_id:
        cs = session.exec(
            select(ComparativeStatement).where(
                ComparativeStatement.id == body.comparative_id,
                ComparativeStatement.tenant_id == user.tenant_id,
                ComparativeStatement.status.in_(["approved", "converted"]),
            )
        ).first()
        if not cs:
            raise HTTPException(400, "comparative_id does not reference an approved comparative")
        if body.demand_id and cs.demand_id != body.demand_id:
            raise HTTPException(400, "comparative_id belongs to a different demand")
    elif _chain_required(session, user.tenant_id):
        raise HTTPException(
            400,
            "This company requires purchases to go through Demand → Comparative approval. "
            "Create a demand, compare quotations, then convert the comparative to a PO "
            "(or disable 'Require purchase chain' in Settings).",
        )

    subtotal = money(sum(D(l.qty) * D(l.rate) for l in body.lines))
    number = next_number(session, user.tenant_id, "purchase_order", "PO")

    vendor_name = body.vendor_name
    if body.vendor_id:
        v = session.exec(
            select(Vendor).where(Vendor.id == body.vendor_id, Vendor.tenant_id == user.tenant_id)
        ).first()
        if not v:
            raise HTTPException(400, "Vendor not found for this tenant")
        if not vendor_name:
            vendor_name = v.name

    po = PurchaseOrder(
        tenant_id=user.tenant_id,
        number=number,
        vendor_id=body.vendor_id,
        vendor_name=vendor_name,
        order_date=body.order_date,
        expected_date=body.expected_date,
        description=body.description,
        notes=body.notes,
        subtotal=subtotal,
        total=subtotal,
        status="draft",
        demand_id=body.demand_id,
        comparative_id=body.comparative_id,
    )
    session.add(po)
    session.flush()

    for l in body.lines:
        session.add(
            PurchaseOrderLine(
                po_id=po.id,
                product_id=l.product_id,
                description=l.description,
                qty=D(l.qty),
                unit=l.unit,
                rate=D(l.rate),
                amount=money(D(l.qty) * D(l.rate)),
            )
        )

    log_audit(session, user, "CREATE", "purchase_order", None, {"number": number})
    session.commit()
    session.refresh(po)
    return po


@router.patch("/{po_id}/approve", dependencies=[])
def approve_po(session: SessionDep, user: AdminUserDep, po_id: int):
    po = session.exec(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == user.tenant_id
        )
    ).first()
    if not po:
        raise HTTPException(404)
    if po.status != "draft":
        raise HTTPException(400, f"Cannot approve a PO with status '{po.status}'")
    po.status = "approved"
    session.add(po)
    log_audit(session, user, "UPDATE", "purchase_order", po_id, {"action": "approved"})
    session.commit()
    return {"success": True, "status": "approved"}


@router.post("/{po_id}/convert-to-bill", status_code=201)
def convert_to_bill(session: SessionDep, user: WriteUserDep, po_id: int, body: BillConvert):
    # Row-locked fetch: two concurrent converts must not both observe
    # bill_id is None and double-bill the PO (idiom: routers/gate_outward.py:172).
    po = session.exec(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == user.tenant_id
        ).with_for_update()
    ).first()
    if not po:
        raise HTTPException(404, "Purchase order not found")
    if po.bill_id:
        raise HTTPException(400, "PO already converted to a bill")
    if po.status == "cancelled":
        raise HTTPException(400, "Cannot convert a cancelled PO")

    if _gate_required(session, user.tenant_id):
        from services.gate import po_fully_covered
        if not po_fully_covered(session, user.tenant_id, po.id):
            raise HTTPException(
                400,
                "This company requires goods to pass the gate before billing. "
                "Record Gate Inward entries covering every PO line "
                "(or disable 'Require gate inward' in Settings).",
            )

    po_lines = session.exec(
        select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po_id)
    ).all()

    ap_acc = get_or_create_account(session, user.tenant_id, "2000", "Accounts Payable", "Liability")
    exp_acc = get_or_create_account(session, user.tenant_id, "5000", "General Expenses", "Expense")

    bill_number = next_number(session, user.tenant_id, "bill", "BILL")

    bill = Bill(
        tenant_id=user.tenant_id,
        number=bill_number,
        vendor_id=po.vendor_id,
        vendor_name=po.vendor_name,
        bill_date=body.bill_date,
        due_date=body.due_date,
        description=po.description or f"From PO {po.number}",
        notes=po.notes,
        subtotal=po.subtotal,
        gst_rate=D("0"),
        gst_amount=D("0"),
        total=po.total,
        status="draft",
        ap_account_id=ap_acc.id,
        expense_account_id=exp_acc.id,
    )
    session.add(bill)
    session.flush()

    for poline in po_lines:
        session.add(
            BillLine(
                bill_id=bill.id,
                product_id=poline.product_id,
                description=poline.description,
                qty=poline.qty,
                unit=poline.unit,
                rate=poline.rate,
                amount=poline.amount,
            )
        )

    # Post GL: Dr Expense / Cr AP
    entries = [
        EntryInput(account_id=exp_acc.id, debit=po.total),
        EntryInput(account_id=ap_acc.id, credit=po.total),
    ]
    txn = post_transaction(
        session, user,
        date=body.bill_date,
        description=f"Bill from PO {po.number}",
        entries=entries,
        voucher_type="PR",
        audit_entity_type="bill",
        audit_detail={"bill_number": bill_number, "po_number": po.number},
    )
    bill.transaction_id = txn.id
    session.add(bill)

    po.bill_id = bill.id
    po.status = "billed"
    session.add(po)

    from models import GateInward
    for gi in session.exec(
        select(GateInward).where(
            GateInward.po_id == po.id,
            GateInward.tenant_id == user.tenant_id,
            GateInward.status == "open",
        )
    ).all():
        gi.status = "billed"
        session.add(gi)

    log_audit(session, user, "UPDATE", "purchase_order", po_id,
              {"action": "converted_to_bill", "bill_number": bill_number})
    session.commit()
    session.refresh(bill)
    return {"bill": bill.model_dump(), "po_number": po.number}
