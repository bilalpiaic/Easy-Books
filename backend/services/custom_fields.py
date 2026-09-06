"""Tenant custom fields (`x.*`) — validate payloads, never touch GL (#372).

Values are attributes on Invoice / Bill / Customer / Product / Vendor.
`services/posting.py` must not import this module or read `custom_fields`.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, col, select

from models import CustomFieldDef

KEY_RE = re.compile(r"^x\.[a-z][a-z0-9_]*$")
ENTITIES = frozenset({"invoice", "bill", "customer", "product", "vendor"})
TYPES = frozenset({"text", "number", "date", "enum", "bool"})
MAX_DEFS = 12
MAX_TEXT = 500
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def assert_key(key: str) -> str:
    if not isinstance(key, str) or not KEY_RE.match(key):
        raise HTTPException(
            400,
            "Custom field key must match x.<lowercase_ident> (e.g. x.gate_pass_no)",
        )
    return key


def assert_entity(entity: str) -> str:
    if entity not in ENTITIES:
        raise HTTPException(400, f"entity must be one of: {', '.join(sorted(ENTITIES))}")
    return entity


def assert_type(type_name: str) -> str:
    if type_name not in TYPES:
        raise HTTPException(400, f"type must be one of: {', '.join(sorted(TYPES))}")
    return type_name


def active_defs(session: Session, tenant_id: int, entity: str) -> list[CustomFieldDef]:
    return list(
        session.exec(
            select(CustomFieldDef)
            .where(
                CustomFieldDef.tenant_id == tenant_id,
                CustomFieldDef.entity == entity,
                col(CustomFieldDef.archived_at).is_(None),
            )
            .order_by(CustomFieldDef.sort_order, CustomFieldDef.id)
        ).all()
    )


def count_active(session: Session, tenant_id: int, entity: str) -> int:
    return len(active_defs(session, tenant_id, entity))


def apply_incoming(
    session: Session,
    tenant_id: int,
    entity: str,
    incoming: Optional[dict],
    *,
    existing: Optional[dict] = None,
    skip_required: Optional[set[str]] = None,
) -> dict:
    """Create: validate incoming (default {}). Update: omit keeps existing."""
    if incoming is None and existing is not None:
        return dict(existing or {})
    out = validate_payload(
        session, tenant_id, entity, incoming or {}, skip_required=skip_required,
    )
    if existing and skip_required:
        for key in skip_required:
            if key in existing:
                out[key] = existing[key]
    return out


def validate_payload(
    session: Session,
    tenant_id: int,
    entity: str,
    data: Optional[dict],
    *,
    skip_required: Optional[set[str]] = None,
) -> dict:
    """Strip unknown keys; 400 on type / required / archived writes."""
    assert_entity(entity)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise HTTPException(400, "custom_fields must be an object")
    raw = dict(data)

    defs = list(
        session.exec(
            select(CustomFieldDef).where(
                CustomFieldDef.tenant_id == tenant_id,
                CustomFieldDef.entity == entity,
            )
        ).all()
    )
    by_key = {d.key: d for d in defs}
    archived = {d.key for d in defs if d.archived_at is not None}
    active = {d.key: d for d in defs if d.archived_at is None}

    for key in raw:
        if key in archived:
            raise HTTPException(400, f"Custom field '{key}' is archived")

    out: dict[str, Any] = {}
    for key, value in raw.items():
        defn = active.get(key)
        if defn is None:
            continue  # unknown keys stripped
        coerced = _coerce(defn, value)
        if coerced is _MISSING:
            continue
        out[key] = coerced

    skip = skip_required or set()
    for defn in active.values():
        if defn.required and defn.key not in out and defn.key not in skip:
            raise HTTPException(400, f"Custom field '{defn.label}' ({defn.key}) is required")

    return out


_MISSING = object()


def _coerce(defn: CustomFieldDef, value: Any) -> Any:
    if value is None or value == "":
        if defn.required:
            raise HTTPException(400, f"Custom field '{defn.label}' ({defn.key}) is required")
        return _MISSING

    t = defn.type
    if t == "text":
        if not isinstance(value, str):
            raise HTTPException(400, f"Custom field '{defn.key}' must be text")
        if len(value) > MAX_TEXT:
            raise HTTPException(400, f"Custom field '{defn.key}' exceeds {MAX_TEXT} characters")
        return value
    if t == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise HTTPException(400, f"Custom field '{defn.key}' must be a number")
        return float(value)
    if t == "bool":
        if isinstance(value, bool):
            return value
        if value in (0, 1):
            return bool(value)
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        raise HTTPException(400, f"Custom field '{defn.key}' must be true or false")
    if t == "date":
        if not isinstance(value, str) or not _DATE_RE.match(value):
            raise HTTPException(400, f"Custom field '{defn.key}' must be YYYY-MM-DD")
        try:
            date.fromisoformat(value)
        except ValueError:
            raise HTTPException(400, f"Custom field '{defn.key}' is not a valid date")
        return value
    if t == "enum":
        allowed = [str(v) for v in (defn.enum_values or [])]
        if not isinstance(value, str) or value not in allowed:
            raise HTTPException(
                400,
                f"Custom field '{defn.key}' must be one of: {', '.join(allowed) or '(empty enum)'}",
            )
        return value
    raise HTTPException(400, f"Custom field '{defn.key}' has unknown type '{t}'")


def fmt_def(row: CustomFieldDef) -> dict:
    return {
        "id": row.id,
        "entity": row.entity,
        "key": row.key,
        "label": row.label,
        "type": row.type,
        "enum_values": list(row.enum_values or []) if row.enum_values is not None else None,
        "required": bool(row.required),
        "show_on_form": bool(row.show_on_form),
        "show_on_print": bool(row.show_on_print),
        "show_on_list": bool(row.show_on_list),
        "sort_order": int(row.sort_order or 0),
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
