"""Textile Processing reports — rejection register, stock ledger, PPC stage analytics."""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from models import Customer, Tenant
from models_textile_processing import (
    TpGreyLot, TpKachiParchi, TpMending, TpPakkiParchi, TpProcess, TpQuality,
    TpRejectionIssueNote, TpRejectionOgp, TpStageEntry,
)
from routers.common import CurrentUserDep, SessionDep
from routers.modules import _get_enabled
from routers.textile_processing import _f, _require_tp, _ser_ogp
from services.money import D, ZERO
from services.permissions import perm_dep

router = APIRouter(prefix="/api/textile-processing/reports", tags=["textile-processing-reports"])


@router.get("/customer-rejection-register", dependencies=[perm_dep("textile.reports", "view")])
def customer_rejection_register(
    user: CurrentUserDep,
    session: SessionDep,
    customer_id: Optional[int] = None,
    lot_id: Optional[int] = None,
    quality_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    open_balance_only: bool = False,
):
    _require_tp(session, user)
    q = select(TpRejectionIssueNote).where(TpRejectionIssueNote.tenant_id == user.tenant_id)
    if customer_id:
        q = q.where(TpRejectionIssueNote.customer_id == customer_id)
    if lot_id:
        q = q.where(TpRejectionIssueNote.lot_id == lot_id)
    if quality_id:
        q = q.where(TpRejectionIssueNote.quality_id == quality_id)
    if date_from:
        q = q.where(TpRejectionIssueNote.date >= date_from)
    if date_to:
        q = q.where(TpRejectionIssueNote.date <= date_to)
    notes = session.exec(q.order_by(TpRejectionIssueNote.date.desc(), TpRejectionIssueNote.id.desc())).all()

    items = []
    for n in notes:
        bal = D(n.issued_mtr) - D(n.lifted_mtr)
        if open_balance_only and bal <= ZERO:
            continue
        if n.status == "cancelled":
            continue
        lot = session.get(TpGreyLot, n.lot_id)
        quality = session.get(TpQuality, n.quality_id)
        cust = session.get(Customer, n.customer_id)
        ogps = session.exec(
            select(TpRejectionOgp).where(
                TpRejectionOgp.rejection_issue_note_id == n.id,
                TpRejectionOgp.status == "posted",
            )
        ).all()
        items.append({
            "date": n.date,
            "note_number": n.number,
            "note_id": n.id,
            "customer_id": n.customer_id,
            "customer_name": cust.name if cust else None,
            "lot_id": n.lot_id,
            "lot_number": lot.number if lot else None,
            "quality_id": n.quality_id,
            "quality_name": quality.name if quality else None,
            "blend": quality.blend if quality else None,
            "width": quality.width if quality else None,
            "issued_mtr": _f(n.issued_mtr),
            "lifted_mtr": _f(n.lifted_mtr),
            "balance_mtr": _f(bal),
            "status": n.status,
            "ogps": [_ser_ogp(o) for o in ogps],
        })
    return {"total": len(items), "items": items}


@router.get("/customer-stock-ledger", dependencies=[perm_dep("textile.reports", "view")])
def customer_stock_ledger(
    user: CurrentUserDep,
    session: SessionDep,
    customer_id: Optional[int] = None,
    quality_id: Optional[int] = None,
):
    """Quantitative stock ledger by customer × quality."""
    _require_tp(session, user)
    q = select(TpGreyLot).where(TpGreyLot.tenant_id == user.tenant_id)
    if customer_id:
        q = q.where(TpGreyLot.customer_id == customer_id)
    if quality_id:
        q = q.where(TpGreyLot.quality_id == quality_id)
    lots = session.exec(q.order_by(TpGreyLot.date, TpGreyLot.id)).all()

    buckets: dict[tuple[int, int], dict] = {}
    for lot in lots:
        key = (lot.customer_id, lot.quality_id)
        if key not in buckets:
            cust = session.get(Customer, lot.customer_id)
            quality = session.get(TpQuality, lot.quality_id)
            buckets[key] = {
                "customer_id": lot.customer_id,
                "customer_name": cust.name if cust else None,
                "quality_id": lot.quality_id,
                "quality_name": quality.name if quality else None,
                "blend": quality.blend if quality else None,
                "width": quality.width if quality else None,
                "grey_in_mtr": 0.0,
                "l_kami_mtr": 0.0,
                "safai_mtr": 0.0,
                "rejection_mtr": 0.0,
                "safi_under_unit_mtr": 0.0,
                "rejection_pending_lift_mtr": 0.0,
                "visible_wastage_mtr": 0.0,
                "invisible_wastage_mtr": 0.0,
                "dispatched_mtr": 0.0,
                "lots": [],
            }
        b = buckets[key]
        b["grey_in_mtr"] += _f(lot.received_mtr)
        b["safi_under_unit_mtr"] += _f(lot.ready_mtr)
        b["rejection_mtr"] += _f(lot.rejection_mtr)
        b["visible_wastage_mtr"] += _f(lot.visible_wastage_mtr)
        b["invisible_wastage_mtr"] += _f(lot.invisible_wastage_mtr)
        b["dispatched_mtr"] += _f(lot.dispatched_mtr)

        mend = session.exec(select(TpMending).where(TpMending.lot_id == lot.id)).first()
        if mend:
            b["l_kami_mtr"] += _f(mend.l_kami_mtr)
            b["safai_mtr"] += _f(mend.safai_mtr)

        rej = session.exec(
            select(TpRejectionIssueNote).where(
                TpRejectionIssueNote.lot_id == lot.id,
                TpRejectionIssueNote.status != "cancelled",
            )
        ).first()
        pending = 0.0
        if rej:
            pending = _f(D(rej.issued_mtr) - D(rej.lifted_mtr))
            b["rejection_pending_lift_mtr"] += pending

        kachi = session.exec(select(TpKachiParchi).where(TpKachiParchi.lot_id == lot.id)).first()
        pakki = session.exec(select(TpPakkiParchi).where(TpPakkiParchi.lot_id == lot.id)).first()
        b["lots"].append({
            "lot_id": lot.id,
            "lot_number": lot.number,
            "date": lot.date,
            "status": lot.status,
            "received_mtr": _f(lot.received_mtr),
            "ready_mtr": _f(lot.ready_mtr),
            "rejection_mtr": _f(lot.rejection_mtr),
            "kachi_parchi": kachi.number if kachi else None,
            "pakki_parchi": pakki.number if pakki else None,
            "rejection_pending_mtr": pending,
        })

    items = list(buckets.values())
    for b in items:
        # Closing under unit ≈ safi − wastage − dispatched (simplified)
        b["closing_under_unit_mtr"] = round(
            b["safi_under_unit_mtr"]
            - b["visible_wastage_mtr"]
            - b["invisible_wastage_mtr"]
            - b["dispatched_mtr"],
            4,
        )
    return {"total": len(items), "items": items}


@router.get("/ppc-stage", dependencies=[perm_dep("textile.reports", "view")])
def ppc_stage_report(
    user: CurrentUserDep,
    session: SessionDep,
    process_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    quality_id: Optional[int] = None,
    lot_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    group_by: str = "stage",  # lot|quality|customer|stage
):
    _require_tp(session, user)
    q = select(TpStageEntry).where(
        TpStageEntry.tenant_id == user.tenant_id,
        TpStageEntry.status == "completed",
    )
    if process_id:
        q = q.where(TpStageEntry.process_id == process_id)
    if customer_id:
        q = q.where(TpStageEntry.customer_id == customer_id)
    if quality_id:
        q = q.where(TpStageEntry.quality_id == quality_id)
    if lot_id:
        q = q.where(TpStageEntry.lot_id == lot_id)
    if date_from:
        q = q.where(TpStageEntry.date >= date_from)
    if date_to:
        q = q.where(TpStageEntry.date <= date_to)
    stages = session.exec(q.order_by(TpStageEntry.date, TpStageEntry.id)).all()

    processes = {
        p.id: p for p in session.exec(
            select(TpProcess).where(TpProcess.tenant_id == user.tenant_id)
        ).all()
    }
    qualities = {
        qq.id: qq for qq in session.exec(
            select(TpQuality).where(TpQuality.tenant_id == user.tenant_id)
        ).all()
    }
    customers = {
        c.id: c for c in session.exec(
            select(Customer).where(Customer.tenant_id == user.tenant_id)
        ).all()
    }
    lots = {
        l.id: l for l in session.exec(
            select(TpGreyLot).where(TpGreyLot.tenant_id == user.tenant_id)
        ).all()
    }

    rows = []
    for s in stages:
        proc = processes.get(s.process_id)
        qual = qualities.get(s.quality_id)
        cust = customers.get(s.customer_id)
        lot = lots.get(s.lot_id)
        rows.append({
            "id": s.id,
            "number": s.number,
            "date": s.date,
            "process_id": s.process_id,
            "process_code": proc.code if proc else None,
            "process_name": proc.name if proc else None,
            "lot_id": s.lot_id,
            "lot_number": lot.number if lot else None,
            "customer_id": s.customer_id,
            "customer_name": cust.name if cust else None,
            "quality_id": s.quality_id,
            "quality_name": qual.name if qual else None,
            "blend": qual.blend if qual else None,
            "width": qual.width if qual else None,
            "input_mtr": _f(s.input_mtr),
            "output_mtr": _f(s.output_mtr),
            "visible_wastage_mtr": _f(s.visible_wastage_mtr),
            "invisible_wastage_mtr": _f(s.invisible_wastage_mtr),
            "labor_amount": _f(s.labor_amount),
        })

    # Aggregate
    agg: dict[str, dict] = defaultdict(lambda: {
        "input_mtr": 0.0, "output_mtr": 0.0,
        "visible_wastage_mtr": 0.0, "invisible_wastage_mtr": 0.0,
        "labor_amount": 0.0, "count": 0, "key": None, "label": None,
    })
    for r in rows:
        if group_by == "lot":
            key, label = str(r["lot_id"]), r["lot_number"]
        elif group_by == "quality":
            key = str(r["quality_id"])
            label = f"{r['quality_name']} / {r['blend'] or '-'} / {r['width'] or '-'}"
        elif group_by == "customer":
            key, label = str(r["customer_id"]), r["customer_name"]
        else:
            key, label = str(r["process_id"]), r["process_name"]
        a = agg[key]
        a["key"] = key
        a["label"] = label
        a["input_mtr"] += r["input_mtr"]
        a["output_mtr"] += r["output_mtr"]
        a["visible_wastage_mtr"] += r["visible_wastage_mtr"]
        a["invisible_wastage_mtr"] += r["invisible_wastage_mtr"]
        a["labor_amount"] += r["labor_amount"]
        a["count"] += 1

    return {
        "group_by": group_by,
        "total": len(rows),
        "items": rows,
        "aggregates": list(agg.values()),
    }


@router.get("/lot-register", dependencies=[perm_dep("textile.reports", "view")])
def lot_register(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    lots = session.exec(
        select(TpGreyLot).where(TpGreyLot.tenant_id == user.tenant_id)
        .order_by(TpGreyLot.date.desc())
    ).all()
    items = []
    for lot in lots:
        cust = session.get(Customer, lot.customer_id)
        qual = session.get(TpQuality, lot.quality_id)
        items.append({
            "id": lot.id,
            "number": lot.number,
            "date": lot.date,
            "status": lot.status,
            "customer_name": cust.name if cust else None,
            "quality_name": qual.name if qual else None,
            "blend": qual.blend if qual else None,
            "width": qual.width if qual else None,
            "received_mtr": _f(lot.received_mtr),
            "ready_mtr": _f(lot.ready_mtr),
            "rejection_mtr": _f(lot.rejection_mtr),
            "visible_wastage_mtr": _f(lot.visible_wastage_mtr),
            "invisible_wastage_mtr": _f(lot.invisible_wastage_mtr),
            "dispatched_mtr": _f(lot.dispatched_mtr),
        })
    return {"total": len(items), "items": items}
