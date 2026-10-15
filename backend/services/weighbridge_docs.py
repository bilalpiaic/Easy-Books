"""Shared weighbridge attach for every stock-movement form.

Tickets stay memo/ops (no GL). Stock documents pull vehicle / lot / weights
from a completed (or weighed-in) ticket via WbDocLink so we do not grow a
new FK column on wb_ticket for each form.

Pickable tickets are module-gated. Attach is tenant-scoped and direction-
checked against WB_STOCK_FORMS.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from models_weighbridge import WbDocLink, WbTicket


@dataclass(frozen=True)
class StockFormDef:
    key: str
    direction: str  # inbound | outbound
    label: str
    ticket_fk: str | None = None  # optional legacy column on WbTicket


WB_STOCK_FORMS: dict[str, StockFormDef] = {
    "gate_inward": StockFormDef("gate_inward", "inbound", "Gate Inward", "gate_inward_id"),
    "gate_outward": StockFormDef("gate_outward", "outbound", "Gate Outward"),
    "grey_lot": StockFormDef("grey_lot", "inbound", "Grey Inward"),
    "invoice": StockFormDef("invoice", "outbound", "Sales Invoice", "invoice_id"),
    "bill": StockFormDef("bill", "inbound", "Vendor Bill"),
    "rejection_ogp": StockFormDef("rejection_ogp", "outbound", "Rejection OGP"),
    "tp_dispatch": StockFormDef("tp_dispatch", "outbound", "Fresh Dispatch"),
    "sp_bale_receipt": StockFormDef(
        "sp_bale_receipt", "inbound", "Bale Receipt", "sp_bale_receipt_id",
    ),
    "wv_yarn_inward": StockFormDef("wv_yarn_inward", "inbound", "Yarn Inward"),
    "wv_dispatch": StockFormDef("wv_dispatch", "outbound", "Weaving Dispatch"),
    "sp_yarn_dispatch": StockFormDef("sp_yarn_dispatch", "outbound", "Yarn Dispatch"),
}

PICKABLE_STATUSES = frozenset({"weighed_in", "completed"})
_STAMP_KEYS = ("invoice", "bill")


def form_or_400(doc_type: str) -> StockFormDef:
    form = WB_STOCK_FORMS.get(doc_type)
    if form is None:
        raise HTTPException(
            400,
            f"Unknown stock form {doc_type!r}; expected one of {sorted(WB_STOCK_FORMS)}",
        )
    return form


def attach_if_any(
    session: Session,
    user: Any,
    ticket_id: int | None,
    doc_type: str,
    doc_id: int,
    *,
    stamp_row: Any = None,
    extra_fks: Optional[dict[str, int]] = None,
) -> WbTicket | None:
    """No-op when ticket_id is missing. Otherwise link + optional Studio stamp."""
    if not ticket_id:
        return None
    return attach_ticket(
        session, user, ticket_id, doc_type, doc_id,
        stamp_row=stamp_row, extra_fks=extra_fks,
    )


def attach_ticket(
    session: Session,
    user: Any,
    ticket_id: int,
    doc_type: str,
    doc_id: int,
    *,
    stamp_row: Any = None,
    extra_fks: Optional[dict[str, int]] = None,
) -> WbTicket:
    form = form_or_400(doc_type)
    if not doc_id:
        raise HTTPException(400, "doc_id is required")
    ticket = session.exec(
        select(WbTicket).where(
            WbTicket.id == ticket_id, WbTicket.tenant_id == user.tenant_id,
        )
    ).first()
    if not ticket:
        raise HTTPException(404, "Weighbridge ticket not found")
    if ticket.status == "cancelled":
        raise HTTPException(400, "Cannot attach a cancelled weighbridge ticket")
    if ticket.status not in PICKABLE_STATUSES:
        raise HTTPException(
            400, "Attach a weighed-in or completed ticket (draft tickets have no scale data)",
        )
    if ticket.direction != form.direction:
        raise HTTPException(
            400,
            f"{form.label} takes {form.direction} weighbridge tickets "
            f"(this ticket is {ticket.direction})",
        )

    existing = session.exec(
        select(WbDocLink).where(
            WbDocLink.tenant_id == user.tenant_id,
            WbDocLink.ticket_id == ticket.id,
            WbDocLink.doc_type == doc_type,
            WbDocLink.doc_id == doc_id,
        )
    ).first()
    if existing is None:
        session.add(WbDocLink(
            tenant_id=user.tenant_id,
            ticket_id=ticket.id,
            doc_type=doc_type,
            doc_id=doc_id,
            created_by_id=getattr(user, "id", None),
        ))

    if form.ticket_fk and getattr(ticket, form.ticket_fk, None) in (None, 0):
        setattr(ticket, form.ticket_fk, doc_id)
    for col, val in (extra_fks or {}).items():
        if hasattr(ticket, col) and getattr(ticket, col) in (None, 0):
            setattr(ticket, col, val)
    session.add(ticket)

    if stamp_row is not None and doc_type in _STAMP_KEYS:
        _stamp_gate_pass(stamp_row, ticket)
        session.add(stamp_row)
    return ticket


def links_for_doc(session: Session, tenant_id: int, doc_type: str, doc_id: int) -> list[WbTicket]:
    form_or_400(doc_type)
    link_ids = session.exec(
        select(WbDocLink.ticket_id).where(
            WbDocLink.tenant_id == tenant_id,
            WbDocLink.doc_type == doc_type,
            WbDocLink.doc_id == doc_id,
        )
    ).all()
    if not link_ids:
        return []
    rows = session.exec(
        select(WbTicket).where(
            WbTicket.tenant_id == tenant_id,
            WbTicket.id.in_(list(link_ids)),
        ).order_by(WbTicket.id.desc())
    ).all()
    return list(rows)


def merge_ticket_custom_fields(
    session: Session,
    user: Any,
    ticket_id: int | None,
    existing: dict | None,
) -> dict:
    """Fill x.gate_pass_no / x.lot_ref before Studio required-field checks."""
    cf = dict(existing or {})
    if not ticket_id:
        return cf
    ticket = session.exec(
        select(WbTicket).where(
            WbTicket.id == ticket_id, WbTicket.tenant_id == user.tenant_id,
        )
    ).first()
    if not ticket:
        return cf
    if not cf.get("x.gate_pass_no"):
        cf["x.gate_pass_no"] = ticket.number
    if ticket.lot_ref and not cf.get("x.lot_ref"):
        cf["x.lot_ref"] = ticket.lot_ref
    return cf


def _stamp_gate_pass(row: Any, ticket: WbTicket) -> None:
    """Merge ticket # / lot onto invoice or bill custom_fields (no GL)."""
    cf = dict(getattr(row, "custom_fields", None) or {})
    cf["x.gate_pass_no"] = ticket.number
    if ticket.lot_ref and not cf.get("x.lot_ref"):
        cf["x.lot_ref"] = ticket.lot_ref
    row.custom_fields = cf
