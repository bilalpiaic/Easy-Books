"""Gate Inward coverage math (#137 Phase 2) — pure logic, no GL, no writes."""
from decimal import Decimal

from sqlmodel import Session, select

from models import GateInward, GateInwardLine, PurchaseOrderLine
from services.money import D


def gi_coverage(session: Session, tenant_id: int, po_id: int) -> dict[int, Decimal]:
    """po_line_id → Σ qty_received across the PO's non-cancelled Gate Inwards."""
    cov: dict[int, Decimal] = {}
    rows = session.exec(
        select(GateInwardLine)
        .join(GateInward, GateInward.id == GateInwardLine.gate_inward_id)
        .where(
            GateInward.po_id == po_id,
            GateInward.tenant_id == tenant_id,
            GateInward.status != "cancelled",
        )
    ).all()
    for line in rows:
        cov[line.po_line_id] = cov.get(line.po_line_id, D(0)) + D(line.qty_received)
    return cov


def po_fully_covered(session: Session, tenant_id: int, po_id: int) -> bool:
    """True when every PO line's qty is fully covered by non-cancelled GI lines."""
    po_lines = session.exec(
        select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po_id)
    ).all()
    if not po_lines:
        return False
    cov = gi_coverage(session, tenant_id, po_id)
    return all(cov.get(l.id, D(0)) >= D(l.qty) for l in po_lines)
