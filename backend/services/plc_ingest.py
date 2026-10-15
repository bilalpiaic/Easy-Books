"""Normalize mill PLC/gateway readings onto weaving / spinning / processing / weighbridge docs.

The cloud never polls OT networks. A shop-floor gateway POSTs JSON; this
module records an idempotent PlcEvent and, when auto-apply is on, writes
the matching mill document.

GL-posting verticals (spinning stages, processing PPC) default to
supervisor Apply. Memo verticals (weaving production, weighbridge weigh)
auto-record.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, func, select

from models import Tenant, User
from models_plc import PlcDevice, PlcEvent
from models_spinning import STAGE_ORDER, SpConeOutput, SpMachine, SpOperator, SpShift, SpSpinLot, SpStageEntry
from models_textile_processing import TpProcess, TpProductionOrder, TpStageEntry
from models_weaving import WvContract, WvLoom, WvOperator as WvOp, WvProduction, WvShift
from models_weighbridge import WbTicket
from routers.common import next_number
from routers.modules import _get_enabled
from routers.weighbridge import _apply_weigh
from services.money import D, ZERO, money
from services import spinning_calc as sp_calc
from services import spinning_posting
from services import weaving_calc as wv_calc
from services import textile_processing as tp_math


MILL_MODULES = (
    "weaving",
    "spinning",
    "textile_processing",
    "production",
    "weighbridge",
)

EVENT_TYPES: dict[str, dict[str, Any]] = {
    "weaving.production": {
        "module": "weaving",
        "label": "Loom production",
        "auto_apply": True,
        "gl": False,
        "doc": "wv_production",
    },
    "spinning.stage": {
        "module": "spinning",
        "label": "Spinning stage (opening→winding)",
        "auto_apply": False,
        "gl": True,
        "doc": "sp_stage_entry",
    },
    "spinning.cone_output": {
        "module": "spinning",
        "label": "Cone output (draft until approved)",
        "auto_apply": True,
        "gl": False,
        "doc": "sp_cone_output",
    },
    "textile.stage": {
        "module": "textile_processing",
        "label": "Processing PPC stage",
        "auto_apply": False,
        "gl": False,
        "doc": "tp_stage_entry",
    },
    "weighbridge.weigh": {
        "module": "weighbridge",
        "label": "Weighbridge first/second weigh",
        "auto_apply": True,
        "gl": False,
        "doc": "wb_ticket",
    },
    "manufacturing.output": {
        "module": "production",
        "label": "Work-centre counter (review only)",
        "auto_apply": False,
        "gl": True,
        "doc": None,
    },
}

_PROTOCOLS = {"modbus_tcp", "opcua", "mqtt", "s7", "http_gateway"}


def require_shop_floor(session: Session, user: User) -> list[str]:
    tenant = session.get(Tenant, user.tenant_id)
    enabled = _get_enabled(tenant) if tenant else []
    if "shop_floor" not in enabled:
        raise HTTPException(
            403,
            "Install PLC Shop Floor from Add-ons to use this feed.",
        )
    return enabled


def event_type_catalog() -> list[dict[str, Any]]:
    return [{"key": k, **v} for k, v in EVENT_TYPES.items()]


def _dec(val: Any, default: Decimal = ZERO) -> Decimal:
    if val is None or val == "":
        return default
    try:
        return D(val)
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(400, f"Invalid numeric reading: {val!r}")


def _int(val: Any) -> Optional[int]:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _str(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def _date_from(payload: dict, occurred_at: Optional[datetime]) -> str:
    readings = payload.get("readings") or {}
    raw = readings.get("date") or payload.get("date")
    if raw:
        return str(raw)[:10]
    if occurred_at:
        return occurred_at.date().isoformat()
    return date.today().isoformat()


def _occurred(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _readings(event: PlcEvent, device: Optional[PlcDevice]) -> dict:
    payload = event.payload or {}
    merged = dict(device.binding or {}) if device else {}
    extra = payload.get("readings") if isinstance(payload.get("readings"), dict) else {}
    merged.update(extra)
    return merged


def _device_for(session: Session, tenant_id: int, code: str) -> Optional[PlcDevice]:
    return session.exec(
        select(PlcDevice).where(
            PlcDevice.tenant_id == tenant_id,
            PlcDevice.code == code,
            PlcDevice.is_active == True,  # noqa: E712
        )
    ).first()


def _should_auto_apply(device: Optional[PlcDevice], event_type: str) -> bool:
    meta = EVENT_TYPES[event_type]
    if device is not None and device.auto_apply is not None:
        return bool(device.auto_apply)
    return bool(meta["auto_apply"])


def serialize_device(d: PlcDevice) -> dict:
    return {
        "id": d.id,
        "code": d.code,
        "name": d.name,
        "protocol": d.protocol,
        "event_type": d.event_type,
        "binding": d.binding or {},
        "auto_apply": d.auto_apply,
        "is_active": d.is_active,
        "last_seen_at": d.last_seen_at.isoformat() + "Z" if d.last_seen_at else None,
        "last_error": d.last_error,
        "notes": d.notes,
        "created_at": d.created_at.isoformat() + "Z" if d.created_at else None,
    }


def serialize_event(e: PlcEvent, *, replayed: bool = False) -> dict:
    return {
        "id": e.id,
        "device_id": e.device_id,
        "idempotency_key": e.idempotency_key,
        "event_type": e.event_type,
        "machine_code": e.machine_code,
        "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        "received_at": e.received_at.isoformat() + "Z" if e.received_at else None,
        "payload": e.payload or {},
        "status": e.status,
        "result_doc_type": e.result_doc_type,
        "result_doc_id": e.result_doc_id,
        "result_number": e.result_number,
        "error_message": e.error_message,
        "replayed": replayed,
    }


def ingest(
    session: Session,
    user: User,
    body: dict,
    *,
    apply_now: Optional[bool] = None,
) -> dict:
    """Store one reading. Replay of the same idempotency_key returns the original."""
    event_type = _str(body.get("event_type"))
    if event_type not in EVENT_TYPES:
        raise HTTPException(400, f"Unknown event_type; expected one of {sorted(EVENT_TYPES)}")
    machine_code = _str(body.get("machine_code"))
    if not machine_code:
        raise HTTPException(400, "machine_code is required")
    idem = _str(body.get("idempotency_key"))
    if not idem:
        raise HTTPException(400, "idempotency_key is required")
    if len(idem) > 200:
        raise HTTPException(400, "idempotency_key is too long (max 200)")

    readings = body.get("readings")
    if readings is not None and not isinstance(readings, dict):
        raise HTTPException(400, "readings must be an object")

    existing = session.exec(
        select(PlcEvent).where(
            PlcEvent.tenant_id == user.tenant_id,
            PlcEvent.idempotency_key == idem,
        )
    ).first()
    if existing:
        return serialize_event(existing, replayed=True)

    device = _device_for(session, user.tenant_id, machine_code)
    payload = {
        "readings": readings or {},
        "date": body.get("date"),
        "notes": body.get("notes"),
    }
    event = PlcEvent(
        tenant_id=user.tenant_id,
        device_id=device.id if device else None,
        idempotency_key=idem,
        event_type=event_type,
        machine_code=machine_code,
        occurred_at=_occurred(body.get("occurred_at")),
        payload=payload,
        status="received",
        created_by_id=user.id,
    )
    session.add(event)
    if device:
        device.last_seen_at = datetime.utcnow()
        device.last_error = None
        session.add(device)
    session.flush()

    do_apply = _should_auto_apply(device, event_type) if apply_now is None else apply_now
    if do_apply:
        try:
            apply_event(session, user, event)
        except HTTPException as exc:
            event.status = "error"
            event.error_message = str(exc.detail)
            if device:
                device.last_error = event.error_message
                session.add(device)
            session.add(event)
    return serialize_event(event)


def apply_event(session: Session, user: User, event: PlcEvent) -> PlcEvent:
    if event.status == "applied":
        return event
    if event.status == "rejected":
        raise HTTPException(400, "Rejected events cannot be applied")
    if event.event_type not in EVENT_TYPES:
        raise HTTPException(400, f"Unknown event_type {event.event_type}")

    device = session.get(PlcDevice, event.device_id) if event.device_id else None
    if device is None:
        device = _device_for(session, user.tenant_id, event.machine_code)

    enabled = require_shop_floor(session, user)
    needed = EVENT_TYPES[event.event_type]["module"]
    if needed not in enabled:
        raise HTTPException(400, f"Module '{needed}' is not installed")

    handler = {
        "weaving.production": _apply_weaving_production,
        "spinning.stage": _apply_spinning_stage,
        "spinning.cone_output": _apply_cone_output,
        "textile.stage": _apply_textile_stage,
        "weighbridge.weigh": _apply_weighbridge,
        "manufacturing.output": _apply_manufacturing_output,
    }[event.event_type]
    doc_type, doc_id, number = handler(session, user, event, device)
    event.status = "applied"
    event.error_message = None
    event.result_doc_type = doc_type
    event.result_doc_id = doc_id
    event.result_number = number
    session.add(event)
    if device:
        device.last_error = None
        device.last_seen_at = datetime.utcnow()
        session.add(device)
    return event


def reject_event(session: Session, event: PlcEvent, reason: Optional[str]) -> PlcEvent:
    if event.status == "applied":
        raise HTTPException(400, "Cannot reject an event that already wrote a mill document")
    event.status = "rejected"
    event.error_message = (reason or "Rejected by operator").strip()[:500]
    session.add(event)
    return event


def _note(event: PlcEvent, extra: Optional[str] = None) -> str:
    parts = [f"PLC {event.machine_code} #{event.id}"]
    if extra:
        parts.append(extra)
    payload_note = (event.payload or {}).get("notes")
    if payload_note:
        parts.append(str(payload_note))
    return " — ".join(parts)[:500]


def _lookup_code(session: Session, model, tenant_id: int, code: Optional[str]):
    if not code:
        return None
    return session.exec(
        select(model).where(model.tenant_id == tenant_id, model.code == code)
    ).first()


def _apply_weaving_production(session, user, event, device) -> tuple[str, int, str]:
    r = _readings(event, device)
    contract = None
    cid = _int(r.get("contract_id"))
    if cid:
        contract = session.exec(
            select(WvContract).where(WvContract.id == cid, WvContract.tenant_id == user.tenant_id)
        ).first()
    if contract is None and r.get("contract_number"):
        contract = session.exec(
            select(WvContract).where(
                WvContract.tenant_id == user.tenant_id,
                WvContract.number == str(r["contract_number"]),
            )
        ).first()
    if contract is None:
        raise HTTPException(400, "Weaving production needs contract_id or contract_number (device binding or reading)")

    loom = None
    lid = _int(r.get("loom_id"))
    if lid:
        loom = session.exec(
            select(WvLoom).where(WvLoom.id == lid, WvLoom.tenant_id == user.tenant_id)
        ).first()
    if loom is None:
        loom = _lookup_code(session, WvLoom, user.tenant_id, event.machine_code)
        if loom is None:
            loom = _lookup_code(session, WvLoom, user.tenant_id, _str(r.get("loom_code")))

    shift = None
    sid = _int(r.get("shift_id"))
    if sid:
        shift = session.get(WvShift, sid)
    if shift is None:
        shift = _lookup_code(session, WvShift, user.tenant_id, _str(r.get("shift_code")))

    operator = None
    oid = _int(r.get("operator_id"))
    if oid:
        operator = session.get(WvOp, oid)
    if operator is None:
        operator = _lookup_code(session, WvOp, user.tenant_id, _str(r.get("operator_code")))

    warp = _dec(r.get("warp_yarn_kg"))
    weft = _dec(r.get("weft_yarn_kg"))
    grey = _dec(r.get("grey_meters"))
    if grey <= ZERO:
        raise HTTPException(400, "grey_meters must be greater than zero")
    total = money(warp + weft)
    eff = (
        money(_dec(r["efficiency_pct"]))
        if r.get("efficiency_pct") is not None and r.get("efficiency_pct") != ""
        else money(wv_calc.production_efficiency_pct(grey, contract.contract_meters))
    )
    charges = (
        money(_dec(r["weaving_charges"]))
        if r.get("weaving_charges") is not None and r.get("weaving_charges") != ""
        else wv_calc.weaving_charges(grey, contract.weaving_rate)
    )
    num = next_number(session, user.tenant_id, "wv_production", "WP", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = WvProduction(
        tenant_id=user.tenant_id,
        number=num,
        contract_id=contract.id,
        loom_id=loom.id if loom else None,
        shift_id=shift.id if shift else None,
        operator_id=operator.id if operator else None,
        date=_date_from(event.payload, event.occurred_at),
        warp_yarn_kg=money(warp),
        weft_yarn_kg=money(weft),
        total_yarn_kg=total,
        grey_meters=money(grey),
        efficiency_pct=eff,
        weaving_charges=charges,
        notes=_note(event),
        created_by_id=user.id,
        source="plc",
        plc_event_id=event.id,
    )
    session.add(row)
    session.flush()
    return "wv_production", row.id, row.number


def _spin_lot(session, user, r) -> SpSpinLot:
    lid = _int(r.get("spin_lot_id"))
    lot = None
    if lid:
        lot = session.exec(
            select(SpSpinLot).where(SpSpinLot.id == lid, SpSpinLot.tenant_id == user.tenant_id)
        ).first()
    if lot is None and r.get("lot_number"):
        lot = session.exec(
            select(SpSpinLot).where(
                SpSpinLot.tenant_id == user.tenant_id,
                SpSpinLot.number == str(r["lot_number"]),
            )
        ).first()
    if lot is None:
        raise HTTPException(400, "Spinning feed needs spin_lot_id or lot_number")
    return lot


def _spin_machine(session, user, event, r) -> Optional[SpMachine]:
    mid = _int(r.get("machine_id"))
    if mid:
        return session.exec(
            select(SpMachine).where(SpMachine.id == mid, SpMachine.tenant_id == user.tenant_id)
        ).first()
    return _lookup_code(session, SpMachine, user.tenant_id, event.machine_code) or _lookup_code(
        session, SpMachine, user.tenant_id, _str(r.get("machine_code"))
    )


def _apply_spinning_stage(session, user, event, device) -> tuple[str, int, str]:
    r = _readings(event, device)
    lot = _spin_lot(session, user, r)
    stage = _str(r.get("stage"))
    if stage not in STAGE_ORDER:
        raise HTTPException(400, f"stage must be one of {STAGE_ORDER}")
    input_kg = _dec(r.get("input_kg"))
    output_kg = _dec(r.get("output_kg"))
    if input_kg <= ZERO or output_kg <= ZERO:
        raise HTTPException(400, "input_kg and output_kg must be greater than zero")
    waste_kg = _dec(r.get("waste_kg"))
    yld = sp_calc.stage_yield_pct(input_kg, output_kg)
    machine = _spin_machine(session, user, event, r)
    shift = None
    if _int(r.get("shift_id")):
        shift = session.get(SpShift, _int(r.get("shift_id")))
    if shift is None:
        shift = _lookup_code(session, SpShift, user.tenant_id, _str(r.get("shift_code")))
    operator = None
    if _int(r.get("operator_id")):
        operator = session.get(SpOperator, _int(r.get("operator_id")))
    if operator is None:
        operator = _lookup_code(session, SpOperator, user.tenant_id, _str(r.get("operator_code")))

    num = next_number(session, user.tenant_id, "sp_stage_entry", "SE", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = SpStageEntry(
        tenant_id=user.tenant_id,
        number=num,
        spin_lot_id=lot.id,
        stage=stage,
        date=_date_from(event.payload, event.occurred_at),
        input_kg=input_kg,
        output_kg=output_kg,
        waste_kg=waste_kg,
        yield_pct=yld,
        machine_id=machine.id if machine else None,
        shift_id=shift.id if shift else None,
        operator_id=operator.id if operator else None,
        labour_cost=_dec(r.get("labour_cost")),
        overhead_cost=_dec(r.get("overhead_cost")),
        notes=_note(event),
        created_by_id=user.id,
        source="plc",
        plc_event_id=event.id,
    )
    session.add(row)
    session.flush()
    spinning_posting.post_stage_entry(session, user, row)
    return "sp_stage_entry", row.id, row.number


def _apply_cone_output(session, user, event, device) -> tuple[str, int, str]:
    r = _readings(event, device)
    lot = _spin_lot(session, user, r)
    net_kg = _dec(r.get("net_kg"))
    if net_kg <= ZERO:
        raise HTTPException(400, "net_kg must be greater than zero")
    cones = _int(r.get("cones_count")) or 0
    machine = _spin_machine(session, user, event, r)
    num = next_number(session, user.tenant_id, "sp_cone_output", "CO", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = SpConeOutput(
        tenant_id=user.tenant_id,
        number=num,
        spin_lot_id=lot.id,
        date=_date_from(event.payload, event.occurred_at),
        cones_count=cones,
        net_kg=net_kg,
        quality_grade=_str(r.get("quality_grade")),
        lot_no=_str(r.get("lot_no")),
        machine_id=machine.id if machine else None,
        notes=_note(event),
        created_by_id=user.id,
        source="plc",
        plc_event_id=event.id,
    )
    session.add(row)
    session.flush()
    return "sp_cone_output", row.id, row.number


def _apply_textile_stage(session, user, event, device) -> tuple[str, int, str]:
    r = _readings(event, device)
    po = None
    pid = _int(r.get("production_order_id"))
    if pid:
        po = session.exec(
            select(TpProductionOrder).where(
                TpProductionOrder.id == pid, TpProductionOrder.tenant_id == user.tenant_id
            )
        ).first()
    if po is None and r.get("production_order_number"):
        po = session.exec(
            select(TpProductionOrder).where(
                TpProductionOrder.tenant_id == user.tenant_id,
                TpProductionOrder.number == str(r["production_order_number"]),
            )
        ).first()
    if po is None:
        raise HTTPException(400, "Processing stage needs production_order_id or production_order_number")
    if po.status in ("cancelled", "dispatched"):
        raise HTTPException(400, f"Cannot add stage to {po.status} production order")

    proc = None
    proc_id = _int(r.get("process_id"))
    if proc_id:
        proc = session.exec(
            select(TpProcess).where(TpProcess.id == proc_id, TpProcess.tenant_id == user.tenant_id)
        ).first()
    if proc is None:
        proc = _lookup_code(session, TpProcess, user.tenant_id, _str(r.get("process_code")))
    if proc is None:
        raise HTTPException(400, "Processing stage needs process_id or process_code")

    input_mtr = _dec(r.get("input_mtr"))
    output_mtr = _dec(r.get("output_mtr"))
    vis = _dec(r.get("visible_wastage_mtr"))
    invis = _dec(r.get("invisible_wastage_mtr"))
    if input_mtr <= ZERO:
        raise HTTPException(400, "input_mtr must be greater than zero")
    if not tp_math.stage_balance_ok(input_mtr, output_mtr, vis, invis):
        raise HTTPException(400, "Stage balance failed: input_mtr must equal output + visible + invisible wastage")

    labor_qty = _dec(r.get("labor_qty"))
    labor_rate = _dec(r.get("labor_rate"))
    number = next_number(session, user.tenant_id, "tp_stage", "ST", fmt="{prefix}-{YYYY}-{seq:04d}")
    row = TpStageEntry(
        tenant_id=user.tenant_id,
        number=number,
        production_order_id=po.id,
        process_id=proc.id,
        lot_id=po.lot_id,
        customer_id=po.customer_id,
        quality_id=po.quality_id,
        date=_date_from(event.payload, event.occurred_at),
        input_mtr=input_mtr,
        output_mtr=output_mtr,
        visible_wastage_mtr=vis,
        invisible_wastage_mtr=invis,
        rejection_mtr=_dec(r.get("rejection_mtr")),
        labor_qty=labor_qty,
        labor_rate=labor_rate,
        labor_amount=money(labor_qty * labor_rate),
        status="completed",
        notes=_note(event),
        created_by_id=user.id,
        source="plc",
        plc_event_id=event.id,
    )
    session.add(row)
    if po.status == "released":
        po.status = "in_process"
        session.add(po)
    session.flush()
    return "tp_stage_entry", row.id, row.number


def _apply_weighbridge(session, user, event, device) -> tuple[str, int, str]:
    r = _readings(event, device)
    ticket = None
    tid = _int(r.get("ticket_id"))
    if tid:
        ticket = session.exec(
            select(WbTicket).where(WbTicket.id == tid, WbTicket.tenant_id == user.tenant_id)
        ).first()
    vehicle = _str(r.get("vehicle_no"))
    if ticket is None and vehicle:
        ticket = session.exec(
            select(WbTicket)
            .where(
                WbTicket.tenant_id == user.tenant_id,
                WbTicket.vehicle_no == vehicle,
                WbTicket.status.in_(["draft", "weighed_in"]),  # type: ignore[attr-defined]
            )
            .order_by(WbTicket.id.desc())
        ).first()

    now = datetime.utcnow()
    kind = _str(r.get("kind")) or _str(r.get("first_weigh_kind"))
    kg = r.get("kg")
    if kg is None:
        if kind == "tare":
            kg = r.get("tare_kg")
        else:
            kg = r.get("gross_kg")
            if kind is None:
                kind = "gross"

    if ticket is None:
        if not vehicle:
            raise HTTPException(400, "Weighbridge weigh needs ticket_id or vehicle_no")
        num = next_number(session, user.tenant_id, "wb_ticket", "WB", fmt="{prefix}-{YYYY}-{seq:04d}")
        ticket = WbTicket(
            tenant_id=user.tenant_id,
            number=num,
            ticket_date=_date_from(event.payload, event.occurred_at),
            direction=_str(r.get("direction")) or "inbound",
            vehicle_no=vehicle,
            driver_name=_str(r.get("driver_name")),
            party_type=_str(r.get("party_type")) or "other",
            party_name=_str(r.get("party_name")),
            commodity=_str(r.get("commodity")),
            lot_ref=_str(r.get("lot_ref")),
            notes=_note(event),
            status="draft",
            created_by_id=user.id,
            source="plc",
            plc_event_id=event.id,
        )
        session.add(ticket)
        session.flush()

    gross = r.get("gross_kg")
    tare = r.get("tare_kg")
    if gross and tare:
        ticket.gross_kg = money(_dec(gross))
        ticket.tare_kg = money(_dec(tare))
        ticket.net_kg = money(abs(wv_calc.net_kg(ticket.gross_kg, ticket.tare_kg)))
        ticket.first_weigh_kind = ticket.first_weigh_kind or "gross"
        ticket.first_weigh_at = ticket.first_weigh_at or now
        ticket.second_weigh_at = now
        ticket.operator_id = user.id
        ticket.status = "completed"
        ticket.source = "plc"
        ticket.plc_event_id = event.id
        session.add(ticket)
        session.flush()
        return "wb_ticket", ticket.id, ticket.number

    if kind not in ("gross", "tare") or kg is None:
        raise HTTPException(400, "Weighbridge weigh needs kind=gross|tare and kg (or both gross_kg and tare_kg)")
    _apply_weigh(ticket, kind, _dec(kg), now=now, operator_id=user.id)
    ticket.source = "plc"
    ticket.plc_event_id = event.id
    session.add(ticket)
    session.flush()
    return "wb_ticket", ticket.id, ticket.number


def _apply_manufacturing_output(_session, _user, _event, _device) -> tuple[str, int, str]:
    raise HTTPException(
        400,
        "Manufacturing work-centre counters are stored for review in v1. "
        "Complete the production order on the Manufacturing floor — PLC does not post GL.",
    )


def summary(session: Session, tenant_id: int) -> dict:
    today = date.today().isoformat()
    devices = session.exec(
        select(func.count()).select_from(PlcDevice).where(
            PlcDevice.tenant_id == tenant_id, PlcDevice.is_active == True  # noqa: E712
        )
    ).one()
    pending = session.exec(
        select(func.count()).select_from(PlcEvent).where(
            PlcEvent.tenant_id == tenant_id, PlcEvent.status.in_(["received", "error"])  # type: ignore[attr-defined]
        )
    ).one()
    applied_today = session.exec(
        select(func.count()).select_from(PlcEvent).where(
            PlcEvent.tenant_id == tenant_id,
            PlcEvent.status == "applied",
            PlcEvent.received_at >= datetime.combine(date.today(), datetime.min.time()),
        )
    ).one()
    return {
        "devices": int(devices or 0),
        "pending": int(pending or 0),
        "applied_today": int(applied_today or 0),
        "today": today,
        "event_types": event_type_catalog(),
    }
