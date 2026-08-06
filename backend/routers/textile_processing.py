"""Textile Processing / Printing Unit (ballor) — grey intake, PPC, billing, inspection."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from models import (
    Account, Bill, BillLine, CreditNote, CreditNoteLine, Customer, Invoice,
    InvoiceLine, Tenant, Vendor,
)
from models_textile_processing import (
    DEFAULT_PROCESSES,
    PACKING_ITEM_TYPES,
    TpBaling, TpContractor, TpDispatch, TpGreyLot, TpGreySettlement, TpGreyThan,
    TpInspection, TpKachiParchi, TpLaborBill, TpMending, TpPakkiParchi,
    TpProcess, TpProductionOrder, TpQuality, TpRejectionIssueNote, TpRejectionOgp,
    TpSalesOrder, TpSalesOrderPackingLine, TpSalesOrderQualityLine,
    TpStageEntry, TpPacking,
)
from routers.common import (
    CurrentUserDep, SessionDep, WriteUserDep, get_or_create_account, log_audit, next_number,
)
from routers.modules import _get_enabled
from services.money import D, ZERO, money
from services.permissions import perm_dep
from services.posting import EntryInput, post_transaction
from services import textile_processing as tp_math

router = APIRouter(prefix="/api/textile-processing", tags=["textile-processing"])


def _require_tp(session: Session, user) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "textile_processing" not in _get_enabled(tenant):
        raise HTTPException(
            403,
            "The Textile Processing module is not installed. Install it from System → Apps.",
        )


def _f(v) -> float:
    return float(v) if v is not None else 0.0


def _ensure_processes(session: Session, tenant_id: int) -> None:
    existing = session.exec(
        select(TpProcess).where(TpProcess.tenant_id == tenant_id).limit(1)
    ).first()
    if not existing:
        for seq, code, name, is_billing in DEFAULT_PROCESSES:
            session.add(TpProcess(
                tenant_id=tenant_id, seq=seq, code=code, name=name,
                is_billing=is_billing, default_sale_rate=ZERO, is_active=True,
            ))
        session.flush()
        return
    # Backfill dyeing for tenants seeded before dyeing was in DEFAULT_PROCESSES
    dye = session.exec(
        select(TpProcess).where(
            TpProcess.tenant_id == tenant_id, TpProcess.code == "dyeing",
        )
    ).first()
    if not dye:
        session.add(TpProcess(
            tenant_id=tenant_id, seq=65, code="dyeing", name="Dyeing",
            is_billing=True, default_sale_rate=ZERO, is_active=True,
        ))
        session.flush()


def _tenant_ccy(session: Session, tenant_id: int) -> str:
    t = session.get(Tenant, tenant_id)
    return (t.base_currency if t else None) or "PKR"


# ── Serializers ──────────────────────────────────────────────────────────────


def _ser_quality(r: TpQuality) -> dict:
    return {
        "id": r.id, "code": r.code, "name": r.name, "blend": r.blend,
        "width": r.width, "unit": r.unit, "is_active": r.is_active,
        "fiber": r.fiber, "warp_count": r.warp_count, "weft_count": r.weft_count,
        "epi": r.epi, "ppi": r.ppi, "width_inch": r.width_inch,
    }


def _ser_process(r: TpProcess) -> dict:
    return {
        "id": r.id, "seq": r.seq, "code": r.code, "name": r.name,
        "is_billing": r.is_billing, "default_sale_rate": _f(r.default_sale_rate),
        "contractor_expense_account_id": r.contractor_expense_account_id,
        "is_active": r.is_active,
    }


def _ser_contractor(r: TpContractor) -> dict:
    return {
        "id": r.id, "code": r.code, "name": r.name, "vendor_id": r.vendor_id,
        "default_process_id": r.default_process_id, "phone": r.phone,
        "is_active": r.is_active,
    }


def _ser_so_quality_line(r: TpSalesOrderQualityLine) -> dict:
    return {
        "id": r.id, "sales_order_id": r.sales_order_id, "quality_id": r.quality_id,
        "expected_mtr": _f(r.expected_mtr), "grey_rate": _f(r.grey_rate),
        "notes": r.notes,
    }


def _ser_so_packing_line(r: TpSalesOrderPackingLine) -> dict:
    return {
        "id": r.id, "sales_order_id": r.sales_order_id, "item_type": r.item_type,
        "quality_id": r.quality_id, "process_id": r.process_id,
        "qty": _f(r.qty), "meters": _f(r.meters), "rate": _f(r.rate),
        "notes": r.notes,
    }


def _ser_so(
    r: TpSalesOrder,
    quality_lines: list | None = None,
    packing_lines: list | None = None,
) -> dict:
    d = {
        "id": r.id, "number": r.number, "customer_id": r.customer_id,
        "quality_id": r.quality_id, "date": r.date,
        "expected_mtr": _f(r.expected_mtr), "grey_rate": _f(r.grey_rate),
        "process_rates": r.process_rates or [], "status": r.status, "notes": r.notes,
    }
    if quality_lines is not None:
        d["quality_lines"] = [_ser_so_quality_line(x) for x in quality_lines]
    if packing_lines is not None:
        d["packing_lines"] = [_ser_so_packing_line(x) for x in packing_lines]
    return d


def _enrich_lot_display(session: Session, out: dict, lot: TpGreyLot) -> dict:
    """Attach party / contractor / quality / SO labels for the GREY IN form."""
    cust = session.get(Customer, lot.customer_id)
    out["party_name"] = cust.name if cust else None
    out["party_code"] = str(cust.id) if cust else None
    q = session.get(TpQuality, lot.quality_id)
    out["quality_code"] = q.code if q else None
    so = session.get(TpSalesOrder, lot.sales_order_id)
    out["sales_order_number"] = so.number if so else None
    if lot.contractor_id:
        ctr = session.get(TpContractor, lot.contractor_id)
        out["contractor_name"] = ctr.name if ctr else None
        out["contractor_code"] = ctr.code if ctr else None
    else:
        out["contractor_name"] = None
        out["contractor_code"] = None
    return out


def _ser_lot(r: TpGreyLot, thans: list | None = None) -> dict:
    d = {
        "id": r.id, "number": r.number, "sales_order_id": r.sales_order_id,
        "customer_id": r.customer_id, "quality_id": r.quality_id,
        "godown_location_id": r.godown_location_id, "date": r.date,
        "mending_date": getattr(r, "mending_date", None),
        "contractor_id": getattr(r, "contractor_id", None),
        "category": getattr(r, "category", None),
        "process_name": getattr(r, "process_name", None),
        "rate": _f(getattr(r, "rate", 0) or 0),
        "lot_no": getattr(r, "lot_no", None),
        "lot_remarks": getattr(r, "lot_remarks", None),
        "l_kami_mtr": _f(getattr(r, "l_kami_mtr", 0) or 0),
        "manual_rejection_mtr": (
            _f(r.manual_rejection_mtr)
            if getattr(r, "manual_rejection_mtr", None) is not None else None
        ),
        "rej_driver_name": getattr(r, "rej_driver_name", None),
        "rej_mobile": getattr(r, "rej_mobile", None),
        "rej_vehicle": getattr(r, "rej_vehicle", None),
        "received_mtr": _f(r.received_mtr), "than_count": r.than_count,
        "ready_mtr": _f(r.ready_mtr), "rejection_mtr": _f(r.rejection_mtr),
        "visible_wastage_mtr": _f(r.visible_wastage_mtr),
        "invisible_wastage_mtr": _f(r.invisible_wastage_mtr),
        "dispatched_mtr": _f(r.dispatched_mtr), "status": r.status, "notes": r.notes,
    }
    if thans is not None:
        d["thans"] = [
            {
                "id": t.id, "than_no": t.than_no, "meters": _f(t.meters),
                "g_kami_mtr": _f(getattr(t, "g_kami_mtr", 0) or 0),
                "rejection_mtr": _f(getattr(t, "rejection_mtr", 0) or 0),
                "cp_mtr": _f(getattr(t, "cp_mtr", 0) or 0),
                "safi_mtr": _f(getattr(t, "safi_mtr", 0) or 0),
                "des_date": getattr(t, "des_date", None),
                "width": t.width, "notes": t.notes,
            }
            for t in thans
        ]
        # Summary bands for GREY IN form
        g_kami = sum(D(getattr(t, "g_kami_mtr", 0) or 0) for t in thans)
        rej = sum(D(getattr(t, "rejection_mtr", 0) or 0) for t in thans)
        cp = sum(D(getattr(t, "cp_mtr", 0) or 0) for t in thans)
        safi = sum(D(getattr(t, "safi_mtr", 0) or 0) for t in thans)
        greigh = sum(D(t.meters) for t in thans)
        than_rej = sum(
            1 for t in thans
            if D(getattr(t, "rejection_mtr", 0) or 0) > 0
            and D(getattr(t, "safi_mtr", 0) or 0) == 0
        )
        than_cp = sum(1 for t in thans if D(getattr(t, "cp_mtr", 0) or 0) > 0)
        than_safi = sum(1 for t in thans if D(getattr(t, "safi_mtr", 0) or 0) > 0)
        manual_rej = getattr(r, "manual_rejection_mtr", None)
        d["summary"] = {
            "total_safi": {"than": than_safi, "detail_mtrs": _f(safi), "manual_mtrs": _f(safi), "variance": 0.0},
            "total_g_kami": {"than": 0, "detail_mtrs": _f(g_kami), "manual_mtrs": _f(g_kami), "variance": 0.0},
            "total_l_kami": {
                "than": 0,
                "detail_mtrs": _f(getattr(r, "l_kami_mtr", 0) or 0),
                "manual_mtrs": _f(getattr(r, "l_kami_mtr", 0) or 0),
                "variance": 0.0,
            },
            "total_rejection": {
                "than": than_rej,
                "detail_mtrs": _f(rej),
                "manual_mtrs": _f(manual_rej if manual_rej is not None else rej),
                "variance": _f(D(manual_rej if manual_rej is not None else rej) - rej),
            },
            "total_cp": {"than": than_cp, "detail_mtrs": _f(cp), "manual_mtrs": _f(cp), "variance": 0.0},
            "g_total": {
                "than": len(thans),
                "detail_mtrs": _f(greigh),
                "manual_mtrs": _f(greigh),
                "variance": 0.0,
            },
        }
    return d


def _ser_mending(r: TpMending) -> dict:
    return {
        "id": r.id, "number": r.number, "lot_id": r.lot_id, "date": r.date,
        "grey_mtr": _f(r.grey_mtr), "l_kami_mtr": _f(r.l_kami_mtr),
        "rejection_mtr": _f(r.rejection_mtr), "safai_mtr": _f(r.safai_mtr),
        "ready_mtr": _f(r.ready_mtr), "status": r.status, "notes": r.notes,
    }


def _ser_kachi(r: TpKachiParchi) -> dict:
    return {
        "id": r.id, "number": r.number, "lot_id": r.lot_id,
        "customer_id": r.customer_id, "quality_id": r.quality_id,
        "date": r.date, "meters": _f(r.meters), "than_count": r.than_count,
        "notes": r.notes,
    }


def _ser_pakki(r: TpPakkiParchi) -> dict:
    return {
        "id": r.id, "number": r.number, "lot_id": r.lot_id,
        "mending_id": r.mending_id, "customer_id": r.customer_id,
        "quality_id": r.quality_id, "date": r.date, "meters": _f(r.meters),
        "than_count": r.than_count, "notes": r.notes,
    }


def _ser_rej_note(r: TpRejectionIssueNote) -> dict:
    bal = _f(D(r.issued_mtr) - D(r.lifted_mtr))
    return {
        "id": r.id, "number": r.number, "lot_id": r.lot_id,
        "mending_id": r.mending_id, "customer_id": r.customer_id,
        "quality_id": r.quality_id, "date": r.date,
        "issued_mtr": _f(r.issued_mtr), "lifted_mtr": _f(r.lifted_mtr),
        "balance_mtr": bal, "status": r.status, "notes": r.notes,
    }


def _ser_ogp(r: TpRejectionOgp) -> dict:
    return {
        "id": r.id, "number": r.number,
        "rejection_issue_note_id": r.rejection_issue_note_id,
        "customer_id": r.customer_id, "date": r.date, "qty_mtr": _f(r.qty_mtr),
        "vehicle": r.vehicle, "challan": r.challan, "status": r.status,
        "notes": r.notes,
    }


def _ser_po(r: TpProductionOrder) -> dict:
    return {
        "id": r.id, "number": r.number, "lot_id": r.lot_id,
        "sales_order_id": r.sales_order_id, "customer_id": r.customer_id,
        "quality_id": r.quality_id, "date": r.date,
        "issued_mtr": _f(r.issued_mtr), "status": r.status, "notes": r.notes,
    }


def _ser_stage(r: TpStageEntry) -> dict:
    return {
        "id": r.id, "number": r.number,
        "production_order_id": r.production_order_id, "process_id": r.process_id,
        "lot_id": r.lot_id, "customer_id": r.customer_id, "quality_id": r.quality_id,
        "date": r.date, "input_mtr": _f(r.input_mtr), "output_mtr": _f(r.output_mtr),
        "visible_wastage_mtr": _f(r.visible_wastage_mtr),
        "invisible_wastage_mtr": _f(r.invisible_wastage_mtr),
        "loss_mtr": _f(tp_math.loss_mtr(r.visible_wastage_mtr, r.invisible_wastage_mtr)),
        "rejection_mtr": _f(r.rejection_mtr), "contractor_id": r.contractor_id,
        "labor_qty": _f(r.labor_qty), "labor_rate": _f(r.labor_rate),
        "labor_amount": _f(r.labor_amount), "started_at": r.started_at,
        "ended_at": r.ended_at, "status": r.status, "notes": r.notes,
    }


def _ser_dispatch(r: TpDispatch) -> dict:
    return {
        "id": r.id, "number": r.number,
        "production_order_id": r.production_order_id, "lot_id": r.lot_id,
        "sales_order_id": r.sales_order_id, "customer_id": r.customer_id,
        "date": r.date, "meters": _f(r.meters), "vehicle": r.vehicle,
        "challan": r.challan, "invoice_id": r.invoice_id, "status": r.status,
        "notes": r.notes,
    }


def _ser_settlement(r: TpGreySettlement) -> dict:
    return {
        "id": r.id, "number": r.number, "lot_id": r.lot_id,
        "sales_order_id": r.sales_order_id, "customer_id": r.customer_id,
        "date": r.date, "total_grey_received": _f(r.total_grey_received),
        "fresh_dispatch_mtr": _f(r.fresh_dispatch_mtr),
        "visible_wastage_mtr": _f(r.visible_wastage_mtr),
        "invisible_wastage_mtr": _f(r.invisible_wastage_mtr),
        "credit_qty_mtr": _f(r.credit_qty_mtr), "grey_rate": _f(r.grey_rate),
        "credit_value": _f(r.credit_value), "credit_note_id": r.credit_note_id,
        "wastage_invoice_id": r.wastage_invoice_id, "status": r.status,
        "notes": r.notes,
    }


def _ser_labor(r: TpLaborBill) -> dict:
    return {
        "id": r.id, "number": r.number, "contractor_id": r.contractor_id,
        "vendor_id": r.vendor_id, "date": r.date,
        "stage_entry_ids": r.stage_entry_ids or [],
        "labor_amount": _f(r.labor_amount), "bill_id": r.bill_id,
        "status": r.status, "notes": r.notes,
    }


def _ser_inspection(r: TpInspection) -> dict:
    return {
        "id": r.id, "number": r.number, "gate_inward_id": r.gate_inward_id,
        "production_order_id": r.production_order_id, "date": r.date,
        "accepted_qty": _f(r.accepted_qty), "rejected_qty": _f(r.rejected_qty),
        "hold_qty": _f(r.hold_qty), "status": r.status, "notes": r.notes,
    }


# ── Masters ──────────────────────────────────────────────────────────────────


class QualityIn(BaseModel):
    code: Optional[str] = None  # auto-built from structure when omitted
    name: Optional[str] = None
    blend: Optional[str] = None
    width: Optional[str] = None
    unit: str = "MTR"
    fiber: Optional[str] = None
    warp_count: Optional[str] = None
    weft_count: Optional[str] = None
    epi: Optional[str] = None
    ppi: Optional[str] = None
    width_inch: Optional[str] = None
    is_active: bool = True


def _resolve_quality_fields(body: QualityIn) -> dict:
    structured = tp_math.format_quality_code(
        body.fiber, body.warp_count, body.weft_count, body.epi, body.ppi, body.width_inch,
    )
    code = (body.code or "").strip() or (structured or "")
    if not code:
        raise HTTPException(
            400,
            'Provide code or structured fields (fiber, warp/weft, epi/ppi, width) '
            'e.g. CTN 60X60 40X52 45"',
        )
    name = (body.name or "").strip() or code
    width = body.width or (f'{str(body.width_inch).rstrip(chr(34))}\"' if body.width_inch else None)
    return {
        "code": code,
        "name": name,
        "blend": body.blend,
        "width": width,
        "unit": body.unit or "MTR",
        "fiber": (body.fiber or "").strip().upper() or None,
        "warp_count": body.warp_count,
        "weft_count": body.weft_count,
        "epi": body.epi,
        "ppi": body.ppi,
        "width_inch": str(body.width_inch).rstrip('"').rstrip("'") if body.width_inch else None,
        "is_active": body.is_active,
    }


class ProcessIn(BaseModel):
    seq: int = 0
    code: str
    name: str
    is_billing: bool = True
    default_sale_rate: Decimal = ZERO
    contractor_expense_account_id: Optional[int] = None
    is_active: bool = True


class ContractorIn(BaseModel):
    code: str
    name: str
    vendor_id: int
    default_process_id: Optional[int] = None
    phone: Optional[str] = None
    is_active: bool = True


@router.get("/qualities", dependencies=[perm_dep("textile.setup", "view")])
def list_qualities(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_tp(session, user)
    q = select(TpQuality).where(TpQuality.tenant_id == user.tenant_id)
    if active_only:
        q = q.where(TpQuality.is_active == True)  # noqa: E712
    return [_ser_quality(r) for r in session.exec(q.order_by(TpQuality.code)).all()]


@router.post("/qualities", status_code=201, dependencies=[perm_dep("textile.setup", "edit")])
def create_quality(user: WriteUserDep, session: SessionDep, body: QualityIn):
    _require_tp(session, user)
    fields = _resolve_quality_fields(body)
    row = TpQuality(tenant_id=user.tenant_id, **fields)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_quality(row)


@router.put("/qualities/{id}", dependencies=[perm_dep("textile.setup", "edit")])
def update_quality(id: int, user: WriteUserDep, session: SessionDep, body: QualityIn):
    _require_tp(session, user)
    row = session.exec(
        select(TpQuality).where(TpQuality.id == id, TpQuality.tenant_id == user.tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Quality not found")
    fields = _resolve_quality_fields(body)
    for k, v in fields.items():
        setattr(row, k, v)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_quality(row)


@router.delete("/qualities/{id}", dependencies=[perm_dep("textile.setup", "edit")])
def delete_quality(id: int, user: WriteUserDep, session: SessionDep):
    """Soft-delete (deactivate) a grey quality."""
    _require_tp(session, user)
    row = session.exec(
        select(TpQuality).where(TpQuality.id == id, TpQuality.tenant_id == user.tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Quality not found")
    row.is_active = False
    session.add(row)
    session.commit()
    return {"ok": True, "id": id}


@router.get("/processes", dependencies=[perm_dep("textile.setup", "view")])
def list_processes(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_tp(session, user)
    _ensure_processes(session, user.tenant_id)
    session.commit()
    q = select(TpProcess).where(TpProcess.tenant_id == user.tenant_id)
    if active_only:
        q = q.where(TpProcess.is_active == True)  # noqa: E712
    return [_ser_process(r) for r in session.exec(q.order_by(TpProcess.seq)).all()]


@router.post("/processes", status_code=201, dependencies=[perm_dep("textile.setup", "edit")])
def create_process(user: WriteUserDep, session: SessionDep, body: ProcessIn):
    _require_tp(session, user)
    row = TpProcess(
        tenant_id=user.tenant_id, seq=body.seq, code=body.code.strip(),
        name=body.name.strip(), is_billing=body.is_billing,
        default_sale_rate=D(body.default_sale_rate),
        contractor_expense_account_id=body.contractor_expense_account_id,
        is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_process(row)


@router.put("/processes/{id}", dependencies=[perm_dep("textile.setup", "edit")])
def update_process(id: int, user: WriteUserDep, session: SessionDep, body: ProcessIn):
    _require_tp(session, user)
    row = session.exec(
        select(TpProcess).where(TpProcess.id == id, TpProcess.tenant_id == user.tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Process not found")
    row.seq, row.code, row.name = body.seq, body.code.strip(), body.name.strip()
    row.is_billing = body.is_billing
    row.default_sale_rate = D(body.default_sale_rate)
    row.contractor_expense_account_id = body.contractor_expense_account_id
    row.is_active = body.is_active
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_process(row)


@router.delete("/processes/{id}", dependencies=[perm_dep("textile.setup", "edit")])
def delete_process(id: int, user: WriteUserDep, session: SessionDep):
    """Soft-delete a process (deactivate). Hard delete blocked when stage entries exist."""
    _require_tp(session, user)
    row = session.exec(
        select(TpProcess).where(TpProcess.id == id, TpProcess.tenant_id == user.tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Process not found")
    used = session.exec(
        select(TpStageEntry).where(
            TpStageEntry.tenant_id == user.tenant_id,
            TpStageEntry.process_id == id,
        ).limit(1)
    ).first()
    if used:
        row.is_active = False
        session.add(row)
        session.commit()
        return {"ok": True, "id": id, "soft": True}
    session.delete(row)
    session.commit()
    return {"ok": True, "id": id, "soft": False}


@router.get("/contractors", dependencies=[perm_dep("textile.setup", "view")])
def list_contractors(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    _require_tp(session, user)
    q = select(TpContractor).where(TpContractor.tenant_id == user.tenant_id)
    if active_only:
        q = q.where(TpContractor.is_active == True)  # noqa: E712
    return [_ser_contractor(r) for r in session.exec(q.order_by(TpContractor.code)).all()]


@router.post("/contractors", status_code=201, dependencies=[perm_dep("textile.setup", "edit")])
def create_contractor(user: WriteUserDep, session: SessionDep, body: ContractorIn):
    _require_tp(session, user)
    v = session.exec(
        select(Vendor).where(Vendor.id == body.vendor_id, Vendor.tenant_id == user.tenant_id)
    ).first()
    if not v:
        raise HTTPException(400, "Vendor not found")
    if body.default_process_id:
        proc = session.exec(
            select(TpProcess).where(
                TpProcess.id == body.default_process_id,
                TpProcess.tenant_id == user.tenant_id,
            )
        ).first()
        if not proc:
            raise HTTPException(400, "Default process not found")
    row = TpContractor(
        tenant_id=user.tenant_id, code=body.code.strip(), name=body.name.strip(),
        vendor_id=body.vendor_id, default_process_id=body.default_process_id,
        phone=body.phone, is_active=body.is_active,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_contractor(row)


@router.put("/contractors/{id}", dependencies=[perm_dep("textile.setup", "edit")])
def update_contractor(id: int, user: WriteUserDep, session: SessionDep, body: ContractorIn):
    """Update contractor including default process tagging for staging."""
    _require_tp(session, user)
    row = session.exec(
        select(TpContractor).where(
            TpContractor.id == id, TpContractor.tenant_id == user.tenant_id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Contractor not found")
    v = session.exec(
        select(Vendor).where(Vendor.id == body.vendor_id, Vendor.tenant_id == user.tenant_id)
    ).first()
    if not v:
        raise HTTPException(400, "Vendor not found")
    if body.default_process_id:
        proc = session.exec(
            select(TpProcess).where(
                TpProcess.id == body.default_process_id,
                TpProcess.tenant_id == user.tenant_id,
            )
        ).first()
        if not proc:
            raise HTTPException(400, "Default process not found")
    row.code = body.code.strip()
    row.name = body.name.strip()
    row.vendor_id = body.vendor_id
    row.default_process_id = body.default_process_id
    row.phone = body.phone
    row.is_active = body.is_active
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_contractor(row)


# ── Sales Orders ─────────────────────────────────────────────────────────────


class ProcessRateIn(BaseModel):
    process_id: int
    rate: Decimal = ZERO
    enabled: bool = True


class SoQualityLineIn(BaseModel):
    quality_id: int
    expected_mtr: Decimal = ZERO
    grey_rate: Decimal = ZERO
    notes: Optional[str] = None


class SoPackingLineIn(BaseModel):
    item_type: str = "KMZ"
    quality_id: int
    process_id: Optional[int] = None
    qty: Decimal = ZERO
    meters: Decimal = ZERO
    rate: Decimal = ZERO
    notes: Optional[str] = None


class SalesOrderIn(BaseModel):
    customer_id: int
    quality_id: Optional[int] = None  # primary; defaults to first quality_lines entry
    date: str
    expected_mtr: Decimal = ZERO
    grey_rate: Decimal = ZERO
    process_rates: list[ProcessRateIn] = Field(default_factory=list)
    quality_lines: list[SoQualityLineIn] = Field(default_factory=list)
    packing_lines: list[SoPackingLineIn] = Field(default_factory=list)
    notes: Optional[str] = None


def _so_lines(session: Session, so_id: int):
    qlines = session.exec(
        select(TpSalesOrderQualityLine).where(TpSalesOrderQualityLine.sales_order_id == so_id)
    ).all()
    plines = session.exec(
        select(TpSalesOrderPackingLine).where(TpSalesOrderPackingLine.sales_order_id == so_id)
    ).all()
    return qlines, plines


@router.get("/sales-orders", dependencies=[perm_dep("textile.sales_orders", "view")])
def list_sales_orders(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    rows = session.exec(
        select(TpSalesOrder).where(TpSalesOrder.tenant_id == user.tenant_id)
        .order_by(TpSalesOrder.id.desc())
    ).all()
    out = []
    for r in rows:
        ql, pl = _so_lines(session, r.id)
        out.append(_ser_so(r, ql, pl))
    return out


@router.post("/sales-orders", status_code=201, dependencies=[perm_dep("textile.sales_orders", "edit")])
def create_sales_order(user: WriteUserDep, session: SessionDep, body: SalesOrderIn):
    _require_tp(session, user)
    cust = session.exec(
        select(Customer).where(Customer.id == body.customer_id, Customer.tenant_id == user.tenant_id)
    ).first()
    if not cust:
        raise HTTPException(400, "Customer not found")

    quality_lines = list(body.quality_lines)
    if not quality_lines and body.quality_id:
        quality_lines = [SoQualityLineIn(
            quality_id=body.quality_id,
            expected_mtr=body.expected_mtr,
            grey_rate=body.grey_rate,
        )]
    if not quality_lines:
        raise HTTPException(400, "At least one grey quality line is required")

    for ql in quality_lines:
        q = session.exec(
            select(TpQuality).where(
                TpQuality.id == ql.quality_id, TpQuality.tenant_id == user.tenant_id,
            )
        ).first()
        if not q:
            raise HTTPException(400, f"Quality {ql.quality_id} not found")

    for pl in body.packing_lines:
        itype = (pl.item_type or "KMZ").strip().upper()
        if itype not in PACKING_ITEM_TYPES:
            raise HTTPException(
                400,
                f"Invalid packing item_type '{pl.item_type}'. "
                f"Use one of: {', '.join(PACKING_ITEM_TYPES)}",
            )
        q = session.exec(
            select(TpQuality).where(
                TpQuality.id == pl.quality_id, TpQuality.tenant_id == user.tenant_id,
            )
        ).first()
        if not q:
            raise HTTPException(400, f"Packing quality {pl.quality_id} not found")
        if pl.process_id:
            proc = session.exec(
                select(TpProcess).where(
                    TpProcess.id == pl.process_id, TpProcess.tenant_id == user.tenant_id,
                )
            ).first()
            if not proc:
                raise HTTPException(400, f"Process {pl.process_id} not found")

    primary = quality_lines[0]
    primary_qid = body.quality_id or primary.quality_id
    expected = D(body.expected_mtr) if body.expected_mtr else money(
        sum(D(ql.expected_mtr) for ql in quality_lines)
    )
    grey_rate = D(body.grey_rate) if body.grey_rate else D(primary.grey_rate)

    number = next_number(session, user.tenant_id, "tp_sales_order", "SO", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = TpSalesOrder(
        tenant_id=user.tenant_id, number=number, customer_id=body.customer_id,
        quality_id=primary_qid, date=body.date,
        expected_mtr=expected, grey_rate=grey_rate,
        process_rates=[pr.model_dump(mode="json") for pr in body.process_rates],
        status="open", notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    session.flush()
    for ql in quality_lines:
        session.add(TpSalesOrderQualityLine(
            tenant_id=user.tenant_id, sales_order_id=row.id,
            quality_id=ql.quality_id, expected_mtr=D(ql.expected_mtr),
            grey_rate=D(ql.grey_rate), notes=ql.notes,
        ))
    for pl in body.packing_lines:
        session.add(TpSalesOrderPackingLine(
            tenant_id=user.tenant_id, sales_order_id=row.id,
            item_type=(pl.item_type or "KMZ").strip().upper(),
            quality_id=pl.quality_id, process_id=pl.process_id,
            qty=D(pl.qty), meters=D(pl.meters), rate=D(pl.rate), notes=pl.notes,
        ))
    session.commit()
    session.refresh(row)
    log_audit(session, user, "create", "tp_sales_order", row.id, {"number": number})
    session.commit()
    ql, pl = _so_lines(session, row.id)
    return _ser_so(row, ql, pl)


@router.get("/sales-orders/{id}", dependencies=[perm_dep("textile.sales_orders", "view")])
def get_sales_order(id: int, user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    row = session.exec(
        select(TpSalesOrder).where(TpSalesOrder.id == id, TpSalesOrder.tenant_id == user.tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Sales order not found")
    ql, pl = _so_lines(session, row.id)
    return _ser_so(row, ql, pl)


# ── Grey Lots + Kachi Parchi ─────────────────────────────────────────────────


class ThanIn(BaseModel):
    than_no: str
    meters: Decimal
    g_kami_mtr: Decimal = ZERO
    rejection_mtr: Decimal = ZERO
    cp_mtr: Decimal = ZERO
    safi_mtr: Optional[Decimal] = None  # computed when omitted
    des_date: Optional[str] = None
    width: Optional[str] = None
    notes: Optional[str] = None


class GreyLotIn(BaseModel):
    sales_order_id: int
    date: str
    quality_id: Optional[int] = None  # which SO grey quality this lot is for
    godown_location_id: Optional[int] = None
    mending_date: Optional[str] = None
    contractor_id: Optional[int] = None
    category: Optional[str] = None
    process_name: Optional[str] = None
    rate: Optional[Decimal] = None
    lot_no: Optional[str] = None
    lot_remarks: Optional[str] = None
    l_kami_mtr: Decimal = ZERO
    manual_rejection_mtr: Optional[Decimal] = None
    rej_driver_name: Optional[str] = None
    rej_mobile: Optional[str] = None
    rej_vehicle: Optional[str] = None
    thans: list[ThanIn] = Field(default_factory=list)
    notes: Optional[str] = None


@router.get("/lots", dependencies=[perm_dep("textile.lots", "view")])
def list_lots(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    rows = session.exec(
        select(TpGreyLot).where(TpGreyLot.tenant_id == user.tenant_id)
        .order_by(TpGreyLot.id.desc())
    ).all()
    return [_ser_lot(r) for r in rows]


@router.post("/lots", status_code=201, dependencies=[perm_dep("textile.lots", "edit")])
def create_lot(user: WriteUserDep, session: SessionDep, body: GreyLotIn):
    _require_tp(session, user)
    so = session.exec(
        select(TpSalesOrder).where(
            TpSalesOrder.id == body.sales_order_id,
            TpSalesOrder.tenant_id == user.tenant_id,
        )
    ).first()
    if not so:
        raise HTTPException(400, "Sales order not found")
    if not body.thans:
        raise HTTPException(400, "At least one than line is required")

    quality_id = body.quality_id or so.quality_id
    qlines, _ = _so_lines(session, so.id)
    allowed = {so.quality_id} | {ql.quality_id for ql in qlines}
    if quality_id not in allowed:
        raise HTTPException(400, "quality_id is not on this sales order")

    if body.contractor_id:
        from models_textile_processing import TpContractor
        c = session.exec(
            select(TpContractor).where(
                TpContractor.id == body.contractor_id,
                TpContractor.tenant_id == user.tenant_id,
            )
        ).first()
        if not c:
            raise HTTPException(400, "Contractor not found")

    received = money(sum(D(t.meters) for t in body.thans))
    intake_rej = money(sum(D(t.rejection_mtr or 0) for t in body.thans))
    intake_safi = ZERO
    number = next_number(session, user.tenant_id, "tp_grey_lot", "LOT", fmt="{prefix}-{YYYY}-{seq:04d}")
    rate = D(body.rate) if body.rate is not None else D(so.grey_rate or 0)
    lot = TpGreyLot(
        tenant_id=user.tenant_id, number=number, sales_order_id=so.id,
        customer_id=so.customer_id, quality_id=quality_id,
        godown_location_id=body.godown_location_id, date=body.date,
        mending_date=body.mending_date,
        contractor_id=body.contractor_id,
        category=(body.category or None),
        process_name=(body.process_name or None),
        rate=rate,
        lot_no=(body.lot_no or None),
        lot_remarks=(body.lot_remarks or None),
        l_kami_mtr=D(body.l_kami_mtr or 0),
        manual_rejection_mtr=body.manual_rejection_mtr,
        rej_driver_name=body.rej_driver_name,
        rej_mobile=body.rej_mobile,
        rej_vehicle=body.rej_vehicle,
        received_mtr=received, than_count=len(body.thans),
        rejection_mtr=intake_rej, status="received",
        notes=body.notes, created_by_id=user.id,
    )
    session.add(lot)
    session.flush()
    for t in body.thans:
        try:
            safi = D(t.safi_mtr) if t.safi_mtr is not None else tp_math.than_safi_mtr(
                t.meters,
                t.rejection_mtr or ZERO,
                t.g_kami_mtr or ZERO,
                t.cp_mtr or ZERO,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        intake_safi += safi
        session.add(TpGreyThan(
            tenant_id=user.tenant_id, lot_id=lot.id, than_no=t.than_no.strip(),
            meters=D(t.meters),
            g_kami_mtr=D(t.g_kami_mtr or 0),
            rejection_mtr=D(t.rejection_mtr or 0),
            cp_mtr=D(t.cp_mtr or 0),
            safi_mtr=safi,
            des_date=t.des_date,
            width=t.width, notes=t.notes,
        ))
    # Seed ready_mtr from intake safi (mending can still refine later)
    lot.ready_mtr = money(intake_safi)
    session.add(lot)
    # Auto-issue Kachi Parchi on receipt
    kp_num = next_number(session, user.tenant_id, "tp_kachi_parchi", "KP", fmt="{prefix}-{YYYY}-{seq:04d}")
    kachi = TpKachiParchi(
        tenant_id=user.tenant_id, number=kp_num, lot_id=lot.id,
        customer_id=lot.customer_id, quality_id=lot.quality_id, date=body.date,
        meters=received, than_count=len(body.thans), created_by_id=user.id,
    )
    session.add(kachi)

    # Memo custodial GL — customer-owned grey on hand (mirrors manufacturing GRN pair)
    if received > ZERO:
        custodial = get_or_create_account(
            session, user.tenant_id, "1210", "Customer Goods on Hand", "Asset",
        )
        liability = get_or_create_account(
            session, user.tenant_id, "2150", "Customer Goods Liability", "Liability",
        )
        # Memo valuation at SO grey_rate (qty visibility; not owned inventory)
        memo_val = money(received * D(so.grey_rate)) if D(so.grey_rate) > ZERO else ZERO
        if memo_val > ZERO:
            post_transaction(
                session, user,
                date=body.date,
                description=f"{number} — grey receipt (custodial)",
                voucher_type="JV",
                entries=[
                    EntryInput(account_id=custodial.id, debit=memo_val, customer_id=so.customer_id),
                    EntryInput(account_id=liability.id, credit=memo_val, customer_id=so.customer_id),
                ],
                reference=number,
            )
            # Mark memo accounts
            if not custodial.is_memo:
                custodial.is_memo = True
                session.add(custodial)
            if not liability.is_memo:
                liability.is_memo = True
                session.add(liability)

    session.commit()
    session.refresh(lot)
    thans = session.exec(select(TpGreyThan).where(TpGreyThan.lot_id == lot.id)).all()
    out = _enrich_lot_display(session, _ser_lot(lot, thans), lot)
    out["kachi_parchi"] = _ser_kachi(kachi)
    return out


@router.get("/lots/{id}", dependencies=[perm_dep("textile.lots", "view")])
def get_lot(id: int, user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    lot = session.exec(
        select(TpGreyLot).where(TpGreyLot.id == id, TpGreyLot.tenant_id == user.tenant_id)
    ).first()
    if not lot:
        raise HTTPException(404, "Lot not found")
    thans = session.exec(select(TpGreyThan).where(TpGreyThan.lot_id == lot.id)).all()
    out = _enrich_lot_display(session, _ser_lot(lot, thans), lot)
    kachi = session.exec(
        select(TpKachiParchi).where(TpKachiParchi.lot_id == lot.id)
    ).first()
    if kachi:
        out["kachi_parchi"] = _ser_kachi(kachi)
    mend = session.exec(select(TpMending).where(TpMending.lot_id == lot.id)).first()
    if mend:
        out["mending"] = _ser_mending(mend)
    pakki = session.exec(select(TpPakkiParchi).where(TpPakkiParchi.lot_id == lot.id)).first()
    if pakki:
        out["pakki_parchi"] = _ser_pakki(pakki)
    rej = session.exec(
        select(TpRejectionIssueNote).where(TpRejectionIssueNote.lot_id == lot.id)
    ).first()
    if rej:
        out["rejection_note"] = _ser_rej_note(rej)
    return out


@router.get("/kachi-parchis", dependencies=[perm_dep("textile.lots", "view")])
def list_kachi(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    rows = session.exec(
        select(TpKachiParchi).where(TpKachiParchi.tenant_id == user.tenant_id)
        .order_by(TpKachiParchi.id.desc())
    ).all()
    return [_ser_kachi(r) for r in rows]


def _print_party_names(session: Session, customer_id: int, quality_id: int) -> dict:
    cust = session.get(Customer, customer_id)
    qual = session.get(TpQuality, quality_id)
    return {
        "customer_name": cust.name if cust else str(customer_id),
        "quality_code": qual.code if qual else str(quality_id),
        "quality_name": qual.name if qual else "",
    }


@router.get("/kachi-parchis/{id}", dependencies=[perm_dep("textile.lots", "view")])
def get_kachi(id: int, user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    row = session.exec(
        select(TpKachiParchi).where(
            TpKachiParchi.id == id, TpKachiParchi.tenant_id == user.tenant_id
        )
    ).first()
    if not row:
        raise HTTPException(404, "Kachi Parchi not found")
    out = _ser_kachi(row)
    out.update(_print_party_names(session, row.customer_id, row.quality_id))
    lot = session.get(TpGreyLot, row.lot_id)
    if lot:
        out["lot_number"] = lot.number
        thans = session.exec(select(TpGreyThan).where(TpGreyThan.lot_id == lot.id)).all()
        out["thans"] = [
            {
                "than_no": t.than_no, "meters": _f(t.meters),
                "rejection_mtr": _f(getattr(t, "rejection_mtr", 0) or 0),
                "safi_mtr": _f(getattr(t, "safi_mtr", 0) or 0),
            }
            for t in thans
        ]
    return out


# ── Mending → Pakki + Rejection Note ─────────────────────────────────────────


class MendingIn(BaseModel):
    lot_id: int
    date: str
    l_kami_mtr: Decimal = ZERO
    rejection_mtr: Decimal = ZERO
    safai_mtr: Decimal = ZERO
    notes: Optional[str] = None


@router.get("/mendings", dependencies=[perm_dep("textile.mending", "view")])
def list_mendings(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    rows = session.exec(
        select(TpMending).where(TpMending.tenant_id == user.tenant_id)
        .order_by(TpMending.id.desc())
    ).all()
    return [_ser_mending(r) for r in rows]


@router.post("/mendings", status_code=201, dependencies=[perm_dep("textile.mending", "edit")])
def create_mending(user: WriteUserDep, session: SessionDep, body: MendingIn):
    _require_tp(session, user)
    lot = session.exec(
        select(TpGreyLot).where(TpGreyLot.id == body.lot_id, TpGreyLot.tenant_id == user.tenant_id)
    ).first()
    if not lot:
        raise HTTPException(400, "Lot not found")
    existing = session.exec(
        select(TpMending).where(TpMending.lot_id == lot.id, TpMending.tenant_id == user.tenant_id)
    ).first()
    if existing:
        raise HTTPException(400, "Mending already exists for this lot")
    try:
        ready = tp_math.ready_mtr(lot.received_mtr, body.l_kami_mtr, body.rejection_mtr, body.safai_mtr)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    number = next_number(session, user.tenant_id, "tp_mending", "MD", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = TpMending(
        tenant_id=user.tenant_id, number=number, lot_id=lot.id, date=body.date,
        grey_mtr=D(lot.received_mtr), l_kami_mtr=D(body.l_kami_mtr),
        rejection_mtr=D(body.rejection_mtr), safai_mtr=D(body.safai_mtr),
        ready_mtr=ready, status="draft", notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    lot.status = "mending"
    session.add(lot)
    session.commit()
    session.refresh(row)
    return _ser_mending(row)


@router.patch("/mendings/{id}/post", dependencies=[perm_dep("textile.mending", "edit")])
def post_mending(id: int, user: WriteUserDep, session: SessionDep):
    _require_tp(session, user)
    mend = session.exec(
        select(TpMending).where(TpMending.id == id, TpMending.tenant_id == user.tenant_id)
    ).first()
    if not mend:
        raise HTTPException(404, "Mending not found")
    if mend.status != "draft":
        raise HTTPException(400, f"Mending is already {mend.status}")
    lot = session.get(TpGreyLot, mend.lot_id)
    if not lot or lot.tenant_id != user.tenant_id:
        raise HTTPException(404, "Lot not found")

    mend.status = "posted"
    lot.ready_mtr = D(mend.ready_mtr)
    lot.rejection_mtr = D(mend.rejection_mtr)
    lot.status = "ready"
    session.add(mend)
    session.add(lot)

    # Pakki Parchi — Safi grey under unit responsibility
    pakki_num = next_number(session, user.tenant_id, "tp_pakki_parchi", "PP", fmt="{prefix}-{YYYY}-{seq:04d}")
    pakki = TpPakkiParchi(
        tenant_id=user.tenant_id, number=pakki_num, lot_id=lot.id,
        mending_id=mend.id, customer_id=lot.customer_id, quality_id=lot.quality_id,
        date=mend.date, meters=D(mend.ready_mtr), than_count=lot.than_count,
        created_by_id=user.id,
    )
    session.add(pakki)

    rej_note = None
    if D(mend.rejection_mtr) > ZERO:
        rn_num = next_number(
            session, user.tenant_id, "tp_rej_note", "RN", fmt="{prefix}-{YYYY}-{seq:04d}"
        )
        rej_note = TpRejectionIssueNote(
            tenant_id=user.tenant_id, number=rn_num, lot_id=lot.id,
            mending_id=mend.id, customer_id=lot.customer_id, quality_id=lot.quality_id,
            date=mend.date, issued_mtr=D(mend.rejection_mtr), lifted_mtr=ZERO,
            status="issued", created_by_id=user.id,
        )
        session.add(rej_note)

    session.commit()
    session.refresh(mend)
    session.refresh(pakki)
    out = _ser_mending(mend)
    out["pakki_parchi"] = _ser_pakki(pakki)
    if rej_note:
        session.refresh(rej_note)
        out["rejection_note"] = _ser_rej_note(rej_note)
    return out


@router.get("/pakki-parchis", dependencies=[perm_dep("textile.lots", "view")])
def list_pakki(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    rows = session.exec(
        select(TpPakkiParchi).where(TpPakkiParchi.tenant_id == user.tenant_id)
        .order_by(TpPakkiParchi.id.desc())
    ).all()
    return [_ser_pakki(r) for r in rows]


@router.get("/pakki-parchis/{id}", dependencies=[perm_dep("textile.lots", "view")])
def get_pakki(id: int, user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    row = session.exec(
        select(TpPakkiParchi).where(
            TpPakkiParchi.id == id, TpPakkiParchi.tenant_id == user.tenant_id
        )
    ).first()
    if not row:
        raise HTTPException(404, "Pakki Parchi not found")
    out = _ser_pakki(row)
    out.update(_print_party_names(session, row.customer_id, row.quality_id))
    lot = session.get(TpGreyLot, row.lot_id)
    if lot:
        out["lot_number"] = lot.number
    mend = session.get(TpMending, row.mending_id)
    if mend:
        out["mending"] = _ser_mending(mend)
    return out


# ── Rejection Issue Note + OGP ───────────────────────────────────────────────


class OgpIn(BaseModel):
    rejection_issue_note_id: int
    date: str
    qty_mtr: Decimal
    vehicle: Optional[str] = None
    challan: Optional[str] = None
    notes: Optional[str] = None


@router.get("/rejection-notes", dependencies=[perm_dep("textile.rejection", "view")])
def list_rej_notes(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    rows = session.exec(
        select(TpRejectionIssueNote).where(TpRejectionIssueNote.tenant_id == user.tenant_id)
        .order_by(TpRejectionIssueNote.id.desc())
    ).all()
    return [_ser_rej_note(r) for r in rows]


@router.get("/rejection-notes/{id}", dependencies=[perm_dep("textile.rejection", "view")])
def get_rej_note(id: int, user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    row = session.exec(
        select(TpRejectionIssueNote).where(
            TpRejectionIssueNote.id == id,
            TpRejectionIssueNote.tenant_id == user.tenant_id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Rejection note not found")
    out = _ser_rej_note(row)
    ogps = session.exec(
        select(TpRejectionOgp).where(
            TpRejectionOgp.rejection_issue_note_id == row.id,
            TpRejectionOgp.status == "posted",
        )
    ).all()
    out["ogps"] = [_ser_ogp(o) for o in ogps]
    return out


@router.patch("/rejection-notes/{id}/cancel", dependencies=[perm_dep("textile.rejection", "edit")])
def cancel_rej_note(id: int, user: WriteUserDep, session: SessionDep):
    _require_tp(session, user)
    row = session.exec(
        select(TpRejectionIssueNote).where(
            TpRejectionIssueNote.id == id,
            TpRejectionIssueNote.tenant_id == user.tenant_id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Rejection note not found")
    if D(row.lifted_mtr) > ZERO:
        raise HTTPException(400, "Cannot cancel note with posted OGPs")
    if row.status == "cancelled":
        raise HTTPException(400, "Already cancelled")
    row.status = "cancelled"
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_rej_note(row)


@router.get("/rejection-ogps", dependencies=[perm_dep("textile.rejection", "view")])
def list_ogps(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    rows = session.exec(
        select(TpRejectionOgp).where(TpRejectionOgp.tenant_id == user.tenant_id)
        .order_by(TpRejectionOgp.id.desc())
    ).all()
    return [_ser_ogp(r) for r in rows]


@router.get("/rejection-ogps/{id}", dependencies=[perm_dep("textile.rejection", "view")])
def get_ogp(id: int, user: CurrentUserDep, session: SessionDep):
    """Grey Rej Outward (OGP) detail for printout."""
    _require_tp(session, user)
    row = session.exec(
        select(TpRejectionOgp).where(
            TpRejectionOgp.id == id, TpRejectionOgp.tenant_id == user.tenant_id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Grey Rej Outward not found")
    out = _ser_ogp(row)
    cust = session.get(Customer, row.customer_id)
    out["customer_name"] = cust.name if cust else str(row.customer_id)
    note = session.get(TpRejectionIssueNote, row.rejection_issue_note_id)
    if note:
        out["rejection_note"] = _ser_rej_note(note)
        out.update(_print_party_names(session, note.customer_id, note.quality_id))
        lot = session.get(TpGreyLot, note.lot_id)
        if lot:
            out["lot_number"] = lot.number
    return out


@router.post("/rejection-ogps", status_code=201, dependencies=[perm_dep("textile.rejection", "edit")])
def create_ogp(user: WriteUserDep, session: SessionDep, body: OgpIn):
    _require_tp(session, user)
    note = session.exec(
        select(TpRejectionIssueNote).where(
            TpRejectionIssueNote.id == body.rejection_issue_note_id,
            TpRejectionIssueNote.tenant_id == user.tenant_id,
        )
    ).first()
    if not note:
        raise HTTPException(400, "Rejection issue note not found")
    if note.status == "cancelled":
        raise HTTPException(400, "Rejection note is cancelled")
    try:
        bal = tp_math.rej_note_balance(note.issued_mtr, note.lifted_mtr)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    qty = D(body.qty_mtr)
    if qty <= ZERO:
        raise HTTPException(400, "qty_mtr must be > 0")
    if qty > bal:
        raise HTTPException(400, f"OGP qty {qty} exceeds note balance {bal}")
    number = next_number(session, user.tenant_id, "tp_rej_ogp", "OGP", fmt="{prefix}-{YYYY}-{seq:04d}")
    ogp = TpRejectionOgp(
        tenant_id=user.tenant_id, number=number,
        rejection_issue_note_id=note.id, customer_id=note.customer_id,
        date=body.date, qty_mtr=qty, vehicle=body.vehicle, challan=body.challan,
        status="posted", notes=body.notes, created_by_id=user.id,
    )
    session.add(ogp)
    note.lifted_mtr = money(D(note.lifted_mtr) + qty)
    note.status = tp_math.rej_note_status(note.issued_mtr, note.lifted_mtr)
    session.add(note)
    session.commit()
    session.refresh(ogp)
    return _ser_ogp(ogp)


# ── Production Order + Stages ────────────────────────────────────────────────


class ProductionOrderIn(BaseModel):
    lot_id: int
    date: str
    notes: Optional[str] = None


@router.get("/production-orders", dependencies=[perm_dep("textile.production", "view")])
def list_pos(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    rows = session.exec(
        select(TpProductionOrder).where(TpProductionOrder.tenant_id == user.tenant_id)
        .order_by(TpProductionOrder.id.desc())
    ).all()
    return [_ser_po(r) for r in rows]


@router.post("/production-orders", status_code=201, dependencies=[perm_dep("textile.production", "edit")])
def create_po(user: WriteUserDep, session: SessionDep, body: ProductionOrderIn):
    _require_tp(session, user)
    lot = session.exec(
        select(TpGreyLot).where(TpGreyLot.id == body.lot_id, TpGreyLot.tenant_id == user.tenant_id)
    ).first()
    if not lot:
        raise HTTPException(400, "Lot not found")
    pakki = session.exec(
        select(TpPakkiParchi).where(TpPakkiParchi.lot_id == lot.id)
    ).first()
    if not pakki:
        raise HTTPException(400, "Production Order requires a Pakki Parchi (post mending first)")
    if D(lot.ready_mtr) <= ZERO:
        raise HTTPException(400, "Lot has no Safi/ready meters")
    existing = session.exec(
        select(TpProductionOrder).where(
            TpProductionOrder.lot_id == lot.id, TpProductionOrder.tenant_id == user.tenant_id
        )
    ).first()
    if existing:
        raise HTTPException(400, "Production Order already exists for this lot")
    number = next_number(session, user.tenant_id, "tp_prod_order", "TPO", fmt="{prefix}-{YYYY}-{seq:04d}")
    po = TpProductionOrder(
        tenant_id=user.tenant_id, number=number, lot_id=lot.id,
        sales_order_id=lot.sales_order_id, customer_id=lot.customer_id,
        quality_id=lot.quality_id, date=body.date, issued_mtr=D(lot.ready_mtr),
        status="released", notes=body.notes, created_by_id=user.id,
    )
    session.add(po)
    lot.status = "in_process"
    session.add(lot)
    session.commit()
    session.refresh(po)
    return _ser_po(po)


@router.get("/production-orders/{id}", dependencies=[perm_dep("textile.production", "view")])
def get_po(id: int, user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    po = session.exec(
        select(TpProductionOrder).where(
            TpProductionOrder.id == id, TpProductionOrder.tenant_id == user.tenant_id
        )
    ).first()
    if not po:
        raise HTTPException(404, "Production order not found")
    out = _ser_po(po)
    stages = session.exec(
        select(TpStageEntry).where(TpStageEntry.production_order_id == po.id)
        .order_by(TpStageEntry.id)
    ).all()
    out["stages"] = [_ser_stage(s) for s in stages]
    return out


class StageIn(BaseModel):
    production_order_id: int
    process_id: int
    date: str
    input_mtr: Decimal
    output_mtr: Decimal
    visible_wastage_mtr: Decimal = ZERO
    invisible_wastage_mtr: Decimal = ZERO
    rejection_mtr: Decimal = ZERO
    contractor_id: Optional[int] = None
    labor_qty: Decimal = ZERO
    labor_rate: Decimal = ZERO
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    notes: Optional[str] = None
    skip_balance_check: bool = False


@router.get("/stages", dependencies=[perm_dep("textile.stages", "view")])
def list_stages(
    user: CurrentUserDep, session: SessionDep,
    lot_id: Optional[int] = None, production_order_id: Optional[int] = None,
):
    _require_tp(session, user)
    q = select(TpStageEntry).where(TpStageEntry.tenant_id == user.tenant_id)
    if lot_id:
        q = q.where(TpStageEntry.lot_id == lot_id)
    if production_order_id:
        q = q.where(TpStageEntry.production_order_id == production_order_id)
    return [_ser_stage(r) for r in session.exec(q.order_by(TpStageEntry.id.desc())).all()]


@router.post("/stages", status_code=201, dependencies=[perm_dep("textile.stages", "edit")])
def create_stage(user: WriteUserDep, session: SessionDep, body: StageIn):
    _require_tp(session, user)
    _ensure_processes(session, user.tenant_id)
    po = session.exec(
        select(TpProductionOrder).where(
            TpProductionOrder.id == body.production_order_id,
            TpProductionOrder.tenant_id == user.tenant_id,
        )
    ).first()
    if not po:
        raise HTTPException(400, "Production order not found")
    if po.status in ("cancelled", "dispatched"):
        raise HTTPException(400, f"Cannot add stage to {po.status} production order")
    proc = session.exec(
        select(TpProcess).where(
            TpProcess.id == body.process_id, TpProcess.tenant_id == user.tenant_id
        )
    ).first()
    if not proc:
        raise HTTPException(400, "Process not found")

    # Stage machine: prior active process (by seq) must be completed or unused
    prior = session.exec(
        select(TpProcess).where(
            TpProcess.tenant_id == user.tenant_id,
            TpProcess.is_active == True,  # noqa: E712
            TpProcess.seq < proc.seq,
        ).order_by(TpProcess.seq.desc())
    ).first()
    if prior:
        done = session.exec(
            select(TpStageEntry).where(
                TpStageEntry.production_order_id == po.id,
                TpStageEntry.process_id == prior.id,
                TpStageEntry.status == "completed",
            )
        ).first()
        # Allow skip: if SO process_rates marks prior as disabled, skip gate
        so = session.get(TpSalesOrder, po.sales_order_id)
        rates = {int(r.get("process_id")): r for r in (so.process_rates or [])} if so else {}
        prior_enabled = rates.get(prior.id, {}).get("enabled", True) if prior.id in rates else True
        if prior_enabled and not done:
            # If process_rates empty, still require sequential completion of any prior that exists as stage OR first stage
            any_rates = bool(rates)
            if not any_rates or prior_enabled:
                # Soft gate: only block if there is a prior completed stage chain started
                any_stage = session.exec(
                    select(TpStageEntry).where(
                        TpStageEntry.production_order_id == po.id,
                        TpStageEntry.status == "completed",
                    ).limit(1)
                ).first()
                if any_stage and not done:
                    raise HTTPException(
                        400,
                        f"Complete prior process '{prior.name}' before '{proc.name}'",
                    )

    if not body.skip_balance_check and not tp_math.stage_balance_ok(
        body.input_mtr, body.output_mtr,
        body.visible_wastage_mtr, body.invisible_wastage_mtr,
    ):
        raise HTTPException(
            400,
            "Stage balance failed: input_mtr must equal output + visible + invisible wastage",
        )

    labor_amount = money(D(body.labor_qty) * D(body.labor_rate))
    number = next_number(session, user.tenant_id, "tp_stage", "ST", fmt="{prefix}-{YYYY}-{seq:04d}")
    stage = TpStageEntry(
        tenant_id=user.tenant_id, number=number, production_order_id=po.id,
        process_id=proc.id, lot_id=po.lot_id, customer_id=po.customer_id,
        quality_id=po.quality_id, date=body.date,
        input_mtr=D(body.input_mtr), output_mtr=D(body.output_mtr),
        visible_wastage_mtr=D(body.visible_wastage_mtr),
        invisible_wastage_mtr=D(body.invisible_wastage_mtr),
        rejection_mtr=D(body.rejection_mtr), contractor_id=body.contractor_id,
        labor_qty=D(body.labor_qty), labor_rate=D(body.labor_rate),
        labor_amount=labor_amount, started_at=body.started_at, ended_at=body.ended_at,
        status="completed", notes=body.notes, created_by_id=user.id,
    )
    session.add(stage)

    lot = session.get(TpGreyLot, po.lot_id)
    if lot:
        lot.visible_wastage_mtr = money(D(lot.visible_wastage_mtr) + D(body.visible_wastage_mtr))
        lot.invisible_wastage_mtr = money(D(lot.invisible_wastage_mtr) + D(body.invisible_wastage_mtr))
        session.add(lot)
    if po.status == "released":
        po.status = "in_process"
        session.add(po)

    session.commit()
    session.refresh(stage)
    return _ser_stage(stage)


class StageContractorIn(BaseModel):
    contractor_id: Optional[int] = None
    labor_qty: Optional[Decimal] = None
    labor_rate: Optional[Decimal] = None
    notes: Optional[str] = None


@router.patch("/stages/{id}", dependencies=[perm_dep("textile.stages", "edit")])
def update_stage_contractor(id: int, user: WriteUserDep, session: SessionDep, body: StageContractorIn):
    """Update contractor tagging / labor on a completed stage entry."""
    _require_tp(session, user)
    stage = session.exec(
        select(TpStageEntry).where(
            TpStageEntry.id == id, TpStageEntry.tenant_id == user.tenant_id,
        )
    ).first()
    if not stage:
        raise HTTPException(404, "Stage entry not found")
    if stage.status == "cancelled":
        raise HTTPException(400, "Cannot update a cancelled stage")
    if body.contractor_id is not None:
        if body.contractor_id:
            c = session.exec(
                select(TpContractor).where(
                    TpContractor.id == body.contractor_id,
                    TpContractor.tenant_id == user.tenant_id,
                )
            ).first()
            if not c:
                raise HTTPException(400, "Contractor not found")
        stage.contractor_id = body.contractor_id or None
    if body.labor_qty is not None:
        stage.labor_qty = D(body.labor_qty)
    if body.labor_rate is not None:
        stage.labor_rate = D(body.labor_rate)
    if body.labor_qty is not None or body.labor_rate is not None:
        stage.labor_amount = money(D(stage.labor_qty) * D(stage.labor_rate))
    if body.notes is not None:
        stage.notes = body.notes
    session.add(stage)
    session.commit()
    session.refresh(stage)
    return _ser_stage(stage)


@router.get("/lots/{id}/timeline", dependencies=[perm_dep("textile.production", "view")])
def lot_timeline(id: int, user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    lot = session.exec(
        select(TpGreyLot).where(TpGreyLot.id == id, TpGreyLot.tenant_id == user.tenant_id)
    ).first()
    if not lot:
        raise HTTPException(404, "Lot not found")
    events: list[dict[str, Any]] = []
    kachi = session.exec(select(TpKachiParchi).where(TpKachiParchi.lot_id == lot.id)).first()
    if kachi:
        events.append({"type": "kachi_parchi", "date": kachi.date, "data": _ser_kachi(kachi)})
    mend = session.exec(select(TpMending).where(TpMending.lot_id == lot.id)).first()
    if mend:
        events.append({"type": "mending", "date": mend.date, "data": _ser_mending(mend)})
    pakki = session.exec(select(TpPakkiParchi).where(TpPakkiParchi.lot_id == lot.id)).first()
    if pakki:
        events.append({"type": "pakki_parchi", "date": pakki.date, "data": _ser_pakki(pakki)})
    rej = session.exec(
        select(TpRejectionIssueNote).where(TpRejectionIssueNote.lot_id == lot.id)
    ).first()
    if rej:
        events.append({"type": "rejection_note", "date": rej.date, "data": _ser_rej_note(rej)})
        for o in session.exec(
            select(TpRejectionOgp).where(TpRejectionOgp.rejection_issue_note_id == rej.id)
        ).all():
            events.append({"type": "rejection_ogp", "date": o.date, "data": _ser_ogp(o)})
    po = session.exec(
        select(TpProductionOrder).where(TpProductionOrder.lot_id == lot.id)
    ).first()
    if po:
        events.append({"type": "production_order", "date": po.date, "data": _ser_po(po)})
        for s in session.exec(
            select(TpStageEntry).where(TpStageEntry.production_order_id == po.id).order_by(TpStageEntry.id)
        ).all():
            events.append({"type": "stage", "date": s.date, "data": _ser_stage(s)})
    for d in session.exec(select(TpDispatch).where(TpDispatch.lot_id == lot.id)).all():
        events.append({"type": "dispatch", "date": d.date, "data": _ser_dispatch(d)})
    sett = session.exec(select(TpGreySettlement).where(TpGreySettlement.lot_id == lot.id)).first()
    if sett:
        events.append({"type": "settlement", "date": sett.date, "data": _ser_settlement(sett)})
    return {
        "lot": _ser_lot(lot),
        "events": events,
        "rollups": {
            "visible_wastage_mtr": _f(lot.visible_wastage_mtr),
            "invisible_wastage_mtr": _f(lot.invisible_wastage_mtr),
            "dispatched_mtr": _f(lot.dispatched_mtr),
            "ready_mtr": _f(lot.ready_mtr),
        },
    }


# ── Packing / Baling / Dispatch ──────────────────────────────────────────────


class PackingIn(BaseModel):
    production_order_id: int
    date: str
    meters: Decimal
    pieces: int = 0
    item_type: Optional[str] = None  # KMZ|SHL|DPT|2PC|3PC|OTHER
    quality_id: Optional[int] = None
    process_id: Optional[int] = None
    notes: Optional[str] = None


class BalingIn(BaseModel):
    production_order_id: int
    date: str
    meters: Decimal
    bale_count: int = 0
    notes: Optional[str] = None


class DispatchIn(BaseModel):
    production_order_id: int
    date: str
    meters: Decimal
    vehicle: Optional[str] = None
    challan: Optional[str] = None
    notes: Optional[str] = None
    create_invoice: bool = True


@router.post("/packing", status_code=201, dependencies=[perm_dep("textile.dispatch", "edit")])
def create_packing(user: WriteUserDep, session: SessionDep, body: PackingIn):
    _require_tp(session, user)
    po = session.exec(
        select(TpProductionOrder).where(
            TpProductionOrder.id == body.production_order_id,
            TpProductionOrder.tenant_id == user.tenant_id,
        )
    ).first()
    if not po:
        raise HTTPException(400, "Production order not found")
    item_type = (body.item_type or "").strip().upper() or None
    if item_type and item_type not in PACKING_ITEM_TYPES:
        raise HTTPException(
            400,
            f"Invalid packing item_type. Use one of: {', '.join(PACKING_ITEM_TYPES)}",
        )
    number = next_number(session, user.tenant_id, "tp_packing", "PK", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = TpPacking(
        tenant_id=user.tenant_id, number=number, production_order_id=po.id,
        lot_id=po.lot_id, date=body.date, meters=D(body.meters),
        pieces=body.pieces, item_type=item_type,
        quality_id=body.quality_id or po.quality_id,
        process_id=body.process_id, notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    lot = session.get(TpGreyLot, po.lot_id)
    if lot:
        lot.status = "packed"
        session.add(lot)
    session.commit()
    session.refresh(row)
    return {
        "id": row.id, "number": row.number, "production_order_id": row.production_order_id,
        "lot_id": row.lot_id, "date": row.date, "meters": _f(row.meters),
        "pieces": row.pieces, "item_type": row.item_type,
        "quality_id": row.quality_id, "process_id": row.process_id, "notes": row.notes,
    }


@router.post("/baling", status_code=201, dependencies=[perm_dep("textile.dispatch", "edit")])
def create_baling(user: WriteUserDep, session: SessionDep, body: BalingIn):
    _require_tp(session, user)
    po = session.exec(
        select(TpProductionOrder).where(
            TpProductionOrder.id == body.production_order_id,
            TpProductionOrder.tenant_id == user.tenant_id,
        )
    ).first()
    if not po:
        raise HTTPException(400, "Production order not found")
    number = next_number(session, user.tenant_id, "tp_baling", "BL", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = TpBaling(
        tenant_id=user.tenant_id, number=number, production_order_id=po.id,
        lot_id=po.lot_id, date=body.date, meters=D(body.meters),
        bale_count=body.bale_count, notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {
        "id": row.id, "number": row.number, "production_order_id": row.production_order_id,
        "lot_id": row.lot_id, "date": row.date, "meters": _f(row.meters),
        "bale_count": row.bale_count, "notes": row.notes,
    }


def _create_process_invoice(
    session: Session, user, so: TpSalesOrder, customer: Customer,
    dispatch: TpDispatch, billed_mtr: Decimal,
) -> Invoice:
    ccy = _tenant_ccy(session, user.tenant_id)
    lines_data = []
    subtotal = ZERO
    processes = {
        p.id: p for p in session.exec(
            select(TpProcess).where(TpProcess.tenant_id == user.tenant_id)
        ).all()
    }
    rates = so.process_rates or []
    if rates:
        for pr in rates:
            if not pr.get("enabled", True):
                continue
            pid = int(pr["process_id"])
            rate = D(pr.get("rate", 0))
            proc = processes.get(pid)
            if not proc or not proc.is_billing:
                continue
            amt = money(billed_mtr * rate)
            if amt <= ZERO and rate <= ZERO:
                continue
            lines_data.append((proc.name, billed_mtr, rate, amt))
            subtotal = money(subtotal + amt)
    else:
        # Fallback: all billing processes at default rate
        for proc in sorted(processes.values(), key=lambda p: p.seq):
            if not proc.is_billing:
                continue
            rate = D(proc.default_sale_rate)
            if rate <= ZERO:
                continue
            amt = money(billed_mtr * rate)
            lines_data.append((proc.name, billed_mtr, rate, amt))
            subtotal = money(subtotal + amt)

    if not lines_data:
        # Single line processing charge placeholder at grey_rate * 0 — use sum of defaults 0 → minimal line
        lines_data.append(("Processing charges", billed_mtr, ZERO, ZERO))

    inv_num = next_number(session, user.tenant_id, "invoice", "INV", fmt="{prefix}-{YYYY}-{seq:04d}")
    ar = get_or_create_account(session, user.tenant_id, "1100", "Accounts Receivable", "Asset")
    rev = get_or_create_account(session, user.tenant_id, "4150", "Processing Revenue", "Revenue")

    inv = Invoice(
        tenant_id=user.tenant_id, number=inv_num, customer_id=customer.id,
        customer_name=customer.name, issue_date=dispatch.date, due_date=dispatch.date,
        description=f"Process charges for dispatch {dispatch.number}",
        subtotal=subtotal, gst_rate=ZERO, gst_amount=ZERO, total=subtotal,
        currency=ccy, exchange_rate=D("1"), status="open",
        ar_account_id=ar.id, revenue_account_id=rev.id, created_by_id=user.id,
    )
    session.add(inv)
    session.flush()
    for desc, qty, rate, amt in lines_data:
        session.add(InvoiceLine(
            invoice_id=inv.id, description=desc, qty=qty, unit="MTR",
            rate=rate, amount=amt,
        ))
    if subtotal > ZERO:
        txn = post_transaction(
            session, user,
            date=dispatch.date,
            description=f"Invoice {inv_num} — process charges",
            voucher_type="SL",
            entries=[
                EntryInput(account_id=ar.id, debit=subtotal, customer_id=customer.id),
                EntryInput(account_id=rev.id, credit=subtotal),
            ],
            reference=inv_num,
        )
        inv.transaction_id = txn.id
        session.add(inv)
    return inv


@router.get("/dispatches", dependencies=[perm_dep("textile.dispatch", "view")])
def list_dispatches(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    rows = session.exec(
        select(TpDispatch).where(TpDispatch.tenant_id == user.tenant_id)
        .order_by(TpDispatch.id.desc())
    ).all()
    return [_ser_dispatch(r) for r in rows]


@router.post("/dispatches", status_code=201, dependencies=[perm_dep("textile.dispatch", "edit")])
def create_dispatch(user: WriteUserDep, session: SessionDep, body: DispatchIn):
    _require_tp(session, user)
    po = session.exec(
        select(TpProductionOrder).where(
            TpProductionOrder.id == body.production_order_id,
            TpProductionOrder.tenant_id == user.tenant_id,
        )
    ).first()
    if not po:
        raise HTTPException(400, "Production order not found")
    lot = session.get(TpGreyLot, po.lot_id)
    if not lot:
        raise HTTPException(400, "Lot not found")
    meters = D(body.meters)
    if meters <= ZERO:
        raise HTTPException(400, "meters must be > 0")
    # Cap: cannot dispatch more than ready − cumulative wastage − already dispatched
    max_out = D(lot.ready_mtr) - D(lot.visible_wastage_mtr) - D(lot.invisible_wastage_mtr) - D(lot.dispatched_mtr)
    if meters > max_out + Decimal("0.01"):
        raise HTTPException(
            400,
            f"Cannot dispatch {meters} MTR — max remaining is {money(max_out)}",
        )
    number = next_number(session, user.tenant_id, "tp_dispatch", "FD", fmt="{prefix}-{YYYY}-{seq:04d}")
    disp = TpDispatch(
        tenant_id=user.tenant_id, number=number, production_order_id=po.id,
        lot_id=lot.id, sales_order_id=po.sales_order_id, customer_id=po.customer_id,
        date=body.date, meters=meters, vehicle=body.vehicle, challan=body.challan,
        status="posted", notes=body.notes, created_by_id=user.id,
    )
    session.add(disp)
    session.flush()

    lot.dispatched_mtr = money(D(lot.dispatched_mtr) + meters)
    lot.status = "dispatched"
    session.add(lot)
    po.status = "dispatched"
    session.add(po)

    if body.create_invoice:
        so = session.get(TpSalesOrder, po.sales_order_id)
        cust = session.get(Customer, po.customer_id)
        if so and cust:
            inv = _create_process_invoice(session, user, so, cust, disp, meters)
            disp.invoice_id = inv.id
            session.add(disp)

    session.commit()
    session.refresh(disp)
    return _ser_dispatch(disp)


# ── Labor bills ──────────────────────────────────────────────────────────────


class LaborBillIn(BaseModel):
    contractor_id: int
    date: str
    stage_entry_ids: list[int] = Field(default_factory=list)
    notes: Optional[str] = None


@router.get("/labor-bills", dependencies=[perm_dep("textile.labor", "view")])
def list_labor_bills(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    rows = session.exec(
        select(TpLaborBill).where(TpLaborBill.tenant_id == user.tenant_id)
        .order_by(TpLaborBill.id.desc())
    ).all()
    return [_ser_labor(r) for r in rows]


@router.post("/labor-bills", status_code=201, dependencies=[perm_dep("textile.labor", "edit")])
def create_labor_bill(user: WriteUserDep, session: SessionDep, body: LaborBillIn):
    _require_tp(session, user)
    contractor = session.exec(
        select(TpContractor).where(
            TpContractor.id == body.contractor_id,
            TpContractor.tenant_id == user.tenant_id,
        )
    ).first()
    if not contractor:
        raise HTTPException(400, "Contractor not found")
    if not body.stage_entry_ids:
        raise HTTPException(400, "stage_entry_ids required")
    stages = session.exec(
        select(TpStageEntry).where(
            TpStageEntry.tenant_id == user.tenant_id,
            TpStageEntry.id.in_(body.stage_entry_ids),  # type: ignore[attr-defined]
        )
    ).all()
    if len(stages) != len(set(body.stage_entry_ids)):
        raise HTTPException(400, "One or more stage entries not found")
    amount = money(sum(D(s.labor_amount) for s in stages))
    if amount <= ZERO:
        raise HTTPException(400, "Labor amount is zero")
    vendor = session.get(Vendor, contractor.vendor_id)
    if not vendor or vendor.tenant_id != user.tenant_id:
        raise HTTPException(400, "Vendor not found")

    ccy = _tenant_ccy(session, user.tenant_id)
    bill_num = next_number(session, user.tenant_id, "bill", "BILL", fmt="{prefix}-{YYYY}-{seq:04d}")
    from services.module_integration import resolve_tp_expense_account
    ap = get_or_create_account(session, user.tenant_id, "2000", "Accounts Payable", "Liability")
    exp = resolve_tp_expense_account(session, user.tenant_id, "contractor")

    bill = Bill(
        tenant_id=user.tenant_id, number=bill_num, vendor_id=vendor.id,
        vendor_name=vendor.name, bill_date=body.date, due_date=body.date,
        description=f"Contractor labor — {contractor.name}",
        subtotal=amount, gst_rate=ZERO, gst_amount=ZERO, total=amount,
        currency=ccy, exchange_rate=D("1"), status="open",
        ap_account_id=ap.id, expense_account_id=exp.id, created_by_id=user.id,
    )
    session.add(bill)
    session.flush()
    session.add(BillLine(
        bill_id=bill.id, description=f"Labor — {contractor.name}",
        qty=D("1"), unit="lot", rate=amount, amount=amount,
    ))
    txn = post_transaction(
        session, user,
        date=body.date,
        description=f"Bill {bill_num} — contractor labor",
        voucher_type="PU",
        entries=[
            EntryInput(account_id=exp.id, debit=amount),
            EntryInput(account_id=ap.id, credit=amount, vendor_id=vendor.id),
        ],
        reference=bill_num,
    )
    bill.transaction_id = txn.id
    session.add(bill)

    number = next_number(session, user.tenant_id, "tp_labor_bill", "LB", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = TpLaborBill(
        tenant_id=user.tenant_id, number=number, contractor_id=contractor.id,
        vendor_id=vendor.id, date=body.date,
        stage_entry_ids=list(body.stage_entry_ids), labor_amount=amount,
        bill_id=bill.id, status="posted", notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_labor(row)


# ── Grey Settlement ──────────────────────────────────────────────────────────


class SettlementIn(BaseModel):
    lot_id: int
    date: str
    recognize_visible_wastage: bool = True
    visible_wastage_rate: Decimal = ZERO
    notes: Optional[str] = None


@router.get("/settlements", dependencies=[perm_dep("textile.settlement", "view")])
def list_settlements(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    rows = session.exec(
        select(TpGreySettlement).where(TpGreySettlement.tenant_id == user.tenant_id)
        .order_by(TpGreySettlement.id.desc())
    ).all()
    return [_ser_settlement(r) for r in rows]


@router.post("/settlements", status_code=201, dependencies=[perm_dep("textile.settlement", "edit")])
def create_settlement(user: WriteUserDep, session: SessionDep, body: SettlementIn):
    _require_tp(session, user)
    lot = session.exec(
        select(TpGreyLot).where(TpGreyLot.id == body.lot_id, TpGreyLot.tenant_id == user.tenant_id)
    ).first()
    if not lot:
        raise HTTPException(400, "Lot not found")
    existing = session.exec(
        select(TpGreySettlement).where(
            TpGreySettlement.lot_id == lot.id, TpGreySettlement.tenant_id == user.tenant_id
        )
    ).first()
    if existing:
        raise HTTPException(400, "Settlement already exists for this lot")
    so = session.get(TpSalesOrder, lot.sales_order_id)
    if not so:
        raise HTTPException(400, "Sales order not found")
    cust = session.get(Customer, lot.customer_id)
    if not cust:
        raise HTTPException(400, "Customer not found")

    # Baseline: raw receipt (total grey received) per locked plan decision
    try:
        credit_qty, credit_value = tp_math.settlement_credit(
            lot.received_mtr, lot.dispatched_mtr,
            lot.visible_wastage_mtr, lot.invisible_wastage_mtr, so.grey_rate,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    from services.module_integration import resolve_tp_expense_account
    ccy = _tenant_ccy(session, user.tenant_id)
    ar = get_or_create_account(session, user.tenant_id, "1100", "Accounts Receivable", "Asset")
    # Grey credit reduces processing/sales revenue (or a dedicated grey-credit contra)
    rev = get_or_create_account(session, user.tenant_id, "4150", "Processing Revenue", "Revenue")
    waste_rev = get_or_create_account(session, user.tenant_id, "4160", "Wastage Sales Revenue", "Revenue")
    shrink_exp = resolve_tp_expense_account(session, user.tenant_id, "shrinkage")

    number = next_number(session, user.tenant_id, "tp_settlement", "GS", fmt="{prefix}-{YYYY}-{seq:04d}")
    sett = TpGreySettlement(
        tenant_id=user.tenant_id, number=number, lot_id=lot.id,
        sales_order_id=so.id, customer_id=cust.id, date=body.date,
        total_grey_received=D(lot.received_mtr),
        fresh_dispatch_mtr=D(lot.dispatched_mtr),
        visible_wastage_mtr=D(lot.visible_wastage_mtr),
        invisible_wastage_mtr=D(lot.invisible_wastage_mtr),
        credit_qty_mtr=credit_qty, grey_rate=D(so.grey_rate),
        credit_value=credit_value, status="posted", notes=body.notes,
        created_by_id=user.id,
    )
    session.add(sett)
    session.flush()

    # Credit Note at grey_rate for credit_qty
    if credit_value > ZERO:
        cn_num = next_number(session, user.tenant_id, "credit_note", "CN", fmt="{prefix}-{YYYY}-{seq:04d}")
        cn = CreditNote(
            tenant_id=user.tenant_id, number=cn_num, customer_id=cust.id,
            customer_name=cust.name, issue_date=body.date,
            description=f"Grey return credit — lot {lot.number}",
            subtotal=credit_value, gst_amount=ZERO, total=credit_value,
            currency=ccy, exchange_rate=D("1"), status="posted",
            ar_account_id=ar.id, revenue_account_id=rev.id,
        )
        session.add(cn)
        session.flush()
        session.add(CreditNoteLine(
            credit_note_id=cn.id,
            description=f"Grey credit {credit_qty} MTR @ {so.grey_rate}",
            qty=credit_qty, unit="MTR", rate=D(so.grey_rate), amount=credit_value,
        ))
        txn = post_transaction(
            session, user,
            date=body.date,
            description=f"Credit Note {cn_num} — grey settlement",
            voucher_type="CN",
            entries=[
                EntryInput(account_id=rev.id, debit=credit_value),
                EntryInput(account_id=ar.id, credit=credit_value, customer_id=cust.id),
            ],
            reference=cn_num,
        )
        cn.transaction_id = txn.id
        session.add(cn)
        sett.credit_note_id = cn.id

    # Invisible shrinkage expense (memo recognition via JE Dr expense / Cr contra-memo revenue=0)
    # Charge unit: Dr Shrinkage Expense / Cr Processing Revenue (yield variance) for invisible × grey_rate
    invis_val = money(D(lot.invisible_wastage_mtr) * D(so.grey_rate))
    if invis_val > ZERO:
        post_transaction(
            session, user,
            date=body.date,
            description=f"Process shrinkage — lot {lot.number}",
            voucher_type="JV",
            entries=[
                EntryInput(account_id=shrink_exp.id, debit=invis_val),
                EntryInput(account_id=rev.id, credit=invis_val),
            ],
            reference=sett.number,
        )

    # Visible wastage → sales revenue when recognized
    if body.recognize_visible_wastage and D(lot.visible_wastage_mtr) > ZERO:
        rate = D(body.visible_wastage_rate) if D(body.visible_wastage_rate) > ZERO else D(so.grey_rate)
        waste_amt = money(D(lot.visible_wastage_mtr) * rate)
        if waste_amt > ZERO:
            inv_num = next_number(session, user.tenant_id, "invoice", "INV", fmt="{prefix}-{YYYY}-{seq:04d}")
            inv = Invoice(
                tenant_id=user.tenant_id, number=inv_num, customer_id=cust.id,
                customer_name=cust.name, issue_date=body.date, due_date=body.date,
                description=f"Visible wastage sales — lot {lot.number}",
                subtotal=waste_amt, gst_rate=ZERO, gst_amount=ZERO, total=waste_amt,
                currency=ccy, exchange_rate=D("1"), status="open",
                ar_account_id=ar.id, revenue_account_id=waste_rev.id,
                created_by_id=user.id,
            )
            session.add(inv)
            session.flush()
            session.add(InvoiceLine(
                invoice_id=inv.id,
                description=f"Visible wastage {lot.visible_wastage_mtr} MTR",
                qty=D(lot.visible_wastage_mtr), unit="MTR", rate=rate, amount=waste_amt,
            ))
            txn = post_transaction(
                session, user,
                date=body.date,
                description=f"Invoice {inv_num} — wastage sales",
                voucher_type="SL",
                entries=[
                    EntryInput(account_id=ar.id, debit=waste_amt, customer_id=cust.id),
                    EntryInput(account_id=waste_rev.id, credit=waste_amt),
                ],
                reference=inv_num,
            )
            inv.transaction_id = txn.id
            session.add(inv)
            sett.wastage_invoice_id = inv.id

    lot.status = "closed"
    session.add(lot)
    so.status = "closed"
    session.add(so)
    session.add(sett)
    session.commit()
    session.refresh(sett)
    return _ser_settlement(sett)


# ── Inspection (Phase 4) ─────────────────────────────────────────────────────


class InspectionIn(BaseModel):
    gate_inward_id: int
    date: str
    accepted_qty: Decimal = ZERO
    rejected_qty: Decimal = ZERO
    hold_qty: Decimal = ZERO
    production_order_id: Optional[int] = None
    notes: Optional[str] = None


@router.get("/inspections", dependencies=[perm_dep("textile.inspection", "view")])
def list_inspections(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    rows = session.exec(
        select(TpInspection).where(TpInspection.tenant_id == user.tenant_id)
        .order_by(TpInspection.id.desc())
    ).all()
    return [_ser_inspection(r) for r in rows]


@router.post("/inspections", status_code=201, dependencies=[perm_dep("textile.inspection", "edit")])
def create_inspection(user: WriteUserDep, session: SessionDep, body: InspectionIn):
    _require_tp(session, user)
    from models import GateInward
    gi = session.exec(
        select(GateInward).where(
            GateInward.id == body.gate_inward_id,
            GateInward.tenant_id == user.tenant_id,
        )
    ).first()
    if not gi:
        raise HTTPException(400, "Gate Inward not found")
    number = next_number(session, user.tenant_id, "tp_inspection", "INSP", fmt="{prefix}-{YYYY}-{seq:04d}")
    acc, rej, hold = D(body.accepted_qty), D(body.rejected_qty), D(body.hold_qty)
    if rej > ZERO and acc <= ZERO and hold <= ZERO:
        status = "rejected"
    elif acc > ZERO and (rej > ZERO or hold > ZERO):
        status = "partial"
    elif acc > ZERO:
        status = "accepted"
    else:
        status = "draft"
    row = TpInspection(
        tenant_id=user.tenant_id, number=number, gate_inward_id=gi.id,
        production_order_id=body.production_order_id, date=body.date,
        accepted_qty=acc, rejected_qty=rej, hold_qty=hold, status=status,
        notes=body.notes, created_by_id=user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser_inspection(row)


# ── Dashboard KPIs ───────────────────────────────────────────────────────────


@router.get("/dashboard", dependencies=[perm_dep("textile.reports", "view")])
def dashboard(user: CurrentUserDep, session: SessionDep):
    _require_tp(session, user)
    tid = user.tenant_id
    lots = session.exec(select(TpGreyLot).where(TpGreyLot.tenant_id == tid)).all()
    open_rej = session.exec(
        select(TpRejectionIssueNote).where(
            TpRejectionIssueNote.tenant_id == tid,
            TpRejectionIssueNote.status.in_(["issued", "partially_lifted"]),  # type: ignore[attr-defined]
        )
    ).all()
    in_proc = [l for l in lots if l.status == "in_process"]
    return {
        "kpis": {
            "lots_total": len(lots),
            "lots_in_process": len(in_proc),
            "lots_ready": sum(1 for l in lots if l.status == "ready"),
            "received_mtr": sum(_f(l.received_mtr) for l in lots),
            "ready_mtr": sum(_f(l.ready_mtr) for l in lots),
            "rejection_pending_mtr": sum(
                _f(D(n.issued_mtr) - D(n.lifted_mtr)) for n in open_rej
            ),
            "visible_wastage_mtr": sum(_f(l.visible_wastage_mtr) for l in lots),
            "invisible_wastage_mtr": sum(_f(l.invisible_wastage_mtr) for l in lots),
        }
    }
