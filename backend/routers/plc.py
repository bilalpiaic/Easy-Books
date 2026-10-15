"""Shop-floor PLC ingest — device registry + idempotent mill readings."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlmodel import func, select

from models_plc import PlcDevice, PlcEvent
from routers.common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from services.permissions import perm_dep
from services import plc_ingest as plc

router = APIRouter(prefix="/api/plc", tags=["plc"])

_PROTOCOLS = {"modbus_tcp", "opcua", "mqtt", "s7", "http_gateway"}


class DeviceIn(BaseModel):
    code: str
    name: str
    protocol: str = "http_gateway"
    event_type: str
    binding: dict[str, Any] = Field(default_factory=dict)
    auto_apply: Optional[bool] = None
    is_active: bool = True
    notes: Optional[str] = None


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    protocol: Optional[str] = None
    event_type: Optional[str] = None
    binding: Optional[dict[str, Any]] = None
    auto_apply: Optional[bool] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class IngestIn(BaseModel):
    idempotency_key: str
    machine_code: str
    event_type: str
    occurred_at: Optional[str] = None
    date: Optional[str] = None
    readings: dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    apply: Optional[bool] = None


class BatchIn(BaseModel):
    events: list[IngestIn]


class RejectIn(BaseModel):
    reason: Optional[str] = None


def _device_or_404(session, tenant_id: int, id: int) -> PlcDevice:
    row = session.exec(
        select(PlcDevice).where(PlcDevice.id == id, PlcDevice.tenant_id == tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Device not found")
    return row


def _event_or_404(session, tenant_id: int, id: int) -> PlcEvent:
    row = session.exec(
        select(PlcEvent).where(PlcEvent.id == id, PlcEvent.tenant_id == tenant_id)
    ).first()
    if not row:
        raise HTTPException(404, "Event not found")
    return row


def _validate_device_fields(event_type: str, protocol: str) -> None:
    if event_type not in plc.EVENT_TYPES:
        raise HTTPException(400, f"Unknown event_type; expected one of {sorted(plc.EVENT_TYPES)}")
    if protocol not in _PROTOCOLS:
        raise HTTPException(400, f"Unknown protocol; expected one of {sorted(_PROTOCOLS)}")


@router.get("/event-types", dependencies=[perm_dep("shop_floor.plc", "view")])
def list_event_types(user: CurrentUserDep, session: SessionDep):
    plc.require_shop_floor(session, user)
    return plc.event_type_catalog()


@router.get("/summary", dependencies=[perm_dep("shop_floor.plc", "view")])
def get_summary(user: CurrentUserDep, session: SessionDep):
    plc.require_shop_floor(session, user)
    return plc.summary(session, user.tenant_id)


@router.get("/devices", dependencies=[perm_dep("shop_floor.plc", "view")])
def list_devices(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    plc.require_shop_floor(session, user)
    q = select(PlcDevice).where(PlcDevice.tenant_id == user.tenant_id)
    if active_only:
        q = q.where(PlcDevice.is_active == True)  # noqa: E712
    rows = session.exec(q.order_by(PlcDevice.code)).all()
    return [plc.serialize_device(r) for r in rows]


@router.post("/devices", status_code=201, dependencies=[perm_dep("shop_floor.plc", "edit")])
def create_device(user: WriteUserDep, session: SessionDep, body: DeviceIn):
    plc.require_shop_floor(session, user)
    code = body.code.strip()
    if not code:
        raise HTTPException(400, "code is required")
    _validate_device_fields(body.event_type, body.protocol)
    dup = session.exec(
        select(PlcDevice).where(PlcDevice.tenant_id == user.tenant_id, PlcDevice.code == code)
    ).first()
    if dup:
        raise HTTPException(400, f"Device code {code} already exists")
    row = PlcDevice(
        tenant_id=user.tenant_id,
        code=code,
        name=body.name.strip() or code,
        protocol=body.protocol,
        event_type=body.event_type,
        binding=body.binding or {},
        auto_apply=body.auto_apply,
        is_active=body.is_active,
        notes=body.notes,
        created_by_id=user.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    log_audit(session, user, "create", "plc_device", row.id, {"code": code})
    session.commit()
    return plc.serialize_device(row)


@router.put("/devices/{id}", dependencies=[perm_dep("shop_floor.plc", "edit")])
def update_device(id: int, user: WriteUserDep, session: SessionDep, body: DeviceUpdate):
    plc.require_shop_floor(session, user)
    row = _device_or_404(session, user.tenant_id, id)
    if body.event_type is not None or body.protocol is not None:
        _validate_device_fields(body.event_type or row.event_type, body.protocol or row.protocol)
    if body.name is not None:
        row.name = body.name.strip() or row.name
    if body.protocol is not None:
        row.protocol = body.protocol
    if body.event_type is not None:
        row.event_type = body.event_type
    if body.binding is not None:
        row.binding = body.binding
    if body.auto_apply is not None:
        row.auto_apply = body.auto_apply
    if body.is_active is not None:
        row.is_active = body.is_active
    if body.notes is not None:
        row.notes = body.notes
    session.add(row)
    session.commit()
    session.refresh(row)
    return plc.serialize_device(row)


@router.delete("/devices/{id}", dependencies=[perm_dep("shop_floor.plc", "edit")])
def deactivate_device(id: int, user: WriteUserDep, session: SessionDep):
    plc.require_shop_floor(session, user)
    row = _device_or_404(session, user.tenant_id, id)
    row.is_active = False
    session.add(row)
    log_audit(session, user, "deactivate", "plc_device", row.id, {"code": row.code})
    session.commit()
    return {"success": True}


@router.get("/events", dependencies=[perm_dep("shop_floor.plc", "view")])
def list_events(
    user: CurrentUserDep,
    session: SessionDep,
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    machine_code: Optional[str] = None,
):
    plc.require_shop_floor(session, user)
    filters = [PlcEvent.tenant_id == user.tenant_id]
    if status:
        filters.append(PlcEvent.status == status)
    if event_type:
        filters.append(PlcEvent.event_type == event_type)
    if machine_code:
        filters.append(PlcEvent.machine_code == machine_code)
    total = session.exec(select(func.count()).select_from(PlcEvent).where(*filters)).one()
    rows = session.exec(
        select(PlcEvent).where(*filters).order_by(PlcEvent.id.desc()).offset(skip).limit(limit)
    ).all()
    return {"total": int(total or 0), "items": [plc.serialize_event(r) for r in rows]}


@router.post("/ingest", dependencies=[perm_dep("shop_floor.plc", "edit")])
def ingest_one(user: WriteUserDep, session: SessionDep, body: IngestIn):
    """Gateway / mill desk posts one machine reading.

    Authenticate with a JWT or an `eb_live_` API key created in Settings → API keys.
    Replay the same idempotency_key to get the original event (no double-count).
    """
    plc.require_shop_floor(session, user)
    out = plc.ingest(session, user, body.model_dump(), apply_now=body.apply)
    session.commit()
    return JSONResponse(out, status_code=200 if out.get("replayed") else 201)


@router.post("/ingest/batch", dependencies=[perm_dep("shop_floor.plc", "edit")])
def ingest_batch(user: WriteUserDep, session: SessionDep, body: BatchIn):
    plc.require_shop_floor(session, user)
    if not body.events:
        raise HTTPException(400, "events cannot be empty")
    if len(body.events) > 100:
        raise HTTPException(400, "Batch is capped at 100 readings")
    results = []
    for item in body.events:
        results.append(plc.ingest(session, user, item.model_dump(), apply_now=item.apply))
    session.commit()
    return {"items": results, "total": len(results)}


@router.post("/events/{id}/apply", dependencies=[perm_dep("shop_floor.plc", "edit")])
def apply_one(id: int, user: WriteUserDep, session: SessionDep):
    plc.require_shop_floor(session, user)
    event = _event_or_404(session, user.tenant_id, id)
    plc.apply_event(session, user, event)
    session.commit()
    session.refresh(event)
    return plc.serialize_event(event)


@router.post("/events/{id}/reject", dependencies=[perm_dep("shop_floor.plc", "edit")])
def reject_one(id: int, user: WriteUserDep, session: SessionDep, body: RejectIn):
    plc.require_shop_floor(session, user)
    event = _event_or_404(session, user.tenant_id, id)
    plc.reject_event(session, event, body.reason)
    session.commit()
    session.refresh(event)
    return plc.serialize_event(event)
