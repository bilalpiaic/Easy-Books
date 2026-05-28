"""Purchase Orders — pre-approval workflow before billing. IAS 2 control flow."""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import Bill, BillLine, PurchaseOrder, PurchaseOrderLine, SequenceCounter, Vendor
from routers.common import AdminUserDep, SessionDep, WriteUserDep, log_audit, next_number
from services.money import D, money
from services.posting import EntryInput, post_transaction
from routers.common import get_or_create_account

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"])


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
    return {**po.model_dump(), "lines": [ln.model_dump() for ln in lines]}


@router.post("", status_code=201)
def create_po(session: SessionDep, user: WriteUserDep, body: POCreate):
    if not body.lines:
        raise HTTPException(400, "At least one line is required")

    subtotal = money(sum(D(l.qty) * D(l.rate) for l in body.lines))
    number = next_number(session, user.tenant_id, "purchase_order", "PO")

    vendor_name = body.vendor_name
    if body.vendor_id and not vendor_name:
        v = session.get(Vendor, body.vendor_id)
        vendor_name = v.name if v else None

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
    po = session.exec(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == user.tenant_id
        )
    ).first()
    if not po:
        raise HTTPException(404, "Purchase order not found")
    if po.bill_id:
        raise HTTPException(400, "PO already converted to a bill")
    if po.status == "cancelled":
        raise HTTPException(400, "Cannot convert a cancelled PO")

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
        audit_entity_type="bill",
        audit_detail={"bill_number": bill_number, "po_number": po.number},
    )
    bill.transaction_id = txn.id
    session.add(bill)

    po.bill_id = bill.id
    po.status = "billed"
    session.add(po)
    log_audit(session, user, "UPDATE", "purchase_order", po_id,
              {"action": "converted_to_bill", "bill_number": bill_number})
    session.commit()
    session.refresh(bill)
    return {"bill": bill.model_dump(), "po_number": po.number}
