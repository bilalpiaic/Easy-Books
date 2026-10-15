"""
Shop-floor PLC ingest (#PLC mill feed).

Easy-Books never speaks Modbus/OPC-UA. A mill-side gateway (Node-RED,
Kepware, Ignition, or a small agent) reads PLC tags and POSTs normalized
JSON here. Devices map machine codes onto weaving looms, spinning frames,
processing lines, and weighbridges. Events are append-only and idempotent.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


class PlcDevice(SQLModel, table=True):
    """One physical machine / PLC tag group mapped onto a mill document."""

    __tablename__ = "plc_device"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_plc_device_code"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    code: str = Field(index=True)  # mill machine code the gateway sends
    name: str
    # Documentation only — Easy-Books does not open OT sockets.
    protocol: str = Field(default="http_gateway")  # modbus_tcp|opcua|mqtt|s7|http_gateway
    event_type: str = Field(index=True)  # weaving.production | spinning.stage | …
    # Optional defaults merged under payload.readings (readings win).
    # Examples: contract_id, spin_lot_id, stage, production_order_id, process_id,
    # ticket_id, process_code, lot_number.
    binding: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    auto_apply: Optional[bool] = Field(default=None)  # None → event-type default
    is_active: bool = Field(default=True)
    last_seen_at: Optional[datetime] = None
    last_error: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")


class PlcEvent(SQLModel, table=True):
    """One machine reading. Deduped by (tenant_id, idempotency_key)."""

    __tablename__ = "plc_event"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_plc_event_idem"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    device_id: Optional[int] = Field(default=None, foreign_key="plc_device.id", index=True)
    idempotency_key: str = Field(index=True)
    event_type: str = Field(index=True)
    machine_code: str = Field(index=True)
    occurred_at: Optional[datetime] = None
    received_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    # received | applied | error | rejected
    status: str = Field(default="received", index=True)
    result_doc_type: Optional[str] = None
    result_doc_id: Optional[int] = None
    result_number: Optional[str] = None
    error_message: Optional[str] = None
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
