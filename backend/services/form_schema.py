"""Tenant form schema — hide / require overlay with API enforcement (#373).

Shipped React forms read this JSON; document POST/PUT apply the same rules.
CSS-only hiding is not a security boundary.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from models import FormSchema, User
from services.custom_fields import KEY_RE, assert_entity

ROLES = frozenset({"*", "owner", "admin", "accountant", "viewer"})
CFG_KEYS = frozenset({"visible", "required", "order", "readonly"})

LOCKED_FIELDS: dict[str, frozenset[str]] = {
    "invoice": frozenset({
        "issue_date", "due_date", "customer_id",
        "subtotal", "gst_amount", "total",
        "qty", "rate", "amount",
    }),
    "bill": frozenset({
        "bill_date", "due_date", "vendor_id",
        "subtotal", "gst_amount", "total",
        "qty", "rate", "amount",
    }),
    "customer": frozenset({"name"}),
    "vendor": frozenset({"name"}),
    "product": frozenset({"name"}),
}

CORE_FIELDS: dict[str, frozenset[str]] = {
    "invoice": LOCKED_FIELDS["invoice"] | frozenset({
        "notes", "description", "internal_memo", "discount_pct",
        "analytic_account_id", "analytic_2_id", "analytic_3_id",
        "assigned_to_id", "payment_term_id", "gst_rate",
        "currency", "exchange_rate", "ar_account_id", "revenue_account_id",
        "payment_mode", "buyer_ntn", "buyer_cnic",
        "is_intercompany", "ic_counterparty_tenant_id", "customer_name",
    }),
    "bill": LOCKED_FIELDS["bill"] | frozenset({
        "notes", "description", "internal_memo", "discount_pct",
        "analytic_account_id", "analytic_2_id", "analytic_3_id",
        "payment_term_id", "gst_rate", "currency", "exchange_rate",
        "ap_account_id", "expense_account_id",
        "is_intercompany", "ic_counterparty_tenant_id", "vendor_name",
    }),
    "customer": LOCKED_FIELDS["customer"] | frozenset({
        "email", "phone", "address", "ntn", "cnic", "gstin", "state_code",
        "payment_term_id", "opening_balance",
    }),
    "vendor": LOCKED_FIELDS["vendor"] | frozenset({
        "email", "phone", "address", "gstin", "state_code",
        "payment_term_id", "opening_balance", "wht_tax_code_id", "wht_rate",
    }),
    "product": LOCKED_FIELDS["product"] | frozenset({
        "code", "unit", "product_type", "default_rate", "reorder_level",
        "category_id", "hs_code", "pct_code", "hsn_sac",
        "is_deferred", "recognition_months", "cost_method",
        "track_lot", "track_serial", "standalone_selling_price",
    }),
}


def assert_role(role: str) -> str:
    if role not in ROLES:
        raise HTTPException(400, f"role must be one of: {', '.join(sorted(ROLES))}")
    return role


def _empty_schema() -> dict:
    return {"version": 1, "fields": {}}


def _fields_of(schema: Optional[dict]) -> dict[str, dict]:
    if not isinstance(schema, dict):
        return {}
    fields = schema.get("fields") or {}
    if not isinstance(fields, dict):
        return {}
    return fields


def load_row(session: Session, tenant_id: int, entity: str, role: str) -> Optional[FormSchema]:
    return session.exec(
        select(FormSchema).where(
            FormSchema.tenant_id == tenant_id,
            FormSchema.entity == entity,
            FormSchema.role == role,
        )
    ).first()


def resolve_schema(
    session: Session,
    user: User,
    entity: str,
    *,
    role: Optional[str] = None,
) -> tuple[dict, str]:
    """Return (schema_json, source_role). Role row if present else ``*``."""
    assert_entity(entity)
    want = assert_role(role if role is not None else (user.role or "*"))
    if want != "*":
        row = load_row(session, user.tenant_id, entity, want)
        if row:
            return dict(row.payload_json or _empty_schema()), want
    star = load_row(session, user.tenant_id, entity, "*")
    if star:
        return dict(star.payload_json or _empty_schema()), "*"
    return _empty_schema(), "*"


def hidden_keys(schema: dict) -> set[str]:
    return {
        k for k, cfg in _fields_of(schema).items()
        if isinstance(cfg, dict) and cfg.get("visible") is False
    }


def required_keys(schema: dict) -> set[str]:
    hidden = hidden_keys(schema)
    return {
        k for k, cfg in _fields_of(schema).items()
        if isinstance(cfg, dict) and cfg.get("required") is True and k not in hidden
    }


def validate_schema_doc(entity: str, schema: Any) -> dict:
    """Reject locked hides, unknown core keys, and malformed field configs."""
    assert_entity(entity)
    if not isinstance(schema, dict):
        raise HTTPException(400, "schema must be an object")
    version = schema.get("version", 1)
    if version != 1:
        raise HTTPException(400, "schema.version must be 1")
    fields = schema.get("fields")
    if fields is None:
        fields = {}
    if not isinstance(fields, dict):
        raise HTTPException(400, "schema.fields must be an object")

    locked = LOCKED_FIELDS[entity]
    core = CORE_FIELDS[entity]
    out: dict[str, dict] = {}
    for key, cfg in fields.items():
        if not isinstance(key, str) or not key:
            raise HTTPException(400, "schema field keys must be non-empty strings")
        if not isinstance(cfg, dict):
            raise HTTPException(400, f"schema.fields['{key}'] must be an object")
        extra = set(cfg) - CFG_KEYS
        if extra:
            raise HTTPException(400, f"Unknown keys on '{key}': {', '.join(sorted(extra))}")
        if KEY_RE.match(key):
            pass
        elif key in core:
            pass
        else:
            raise HTTPException(400, f"Unknown form field '{key}' for {entity}")
        if cfg.get("visible") is False and key in locked:
            raise HTTPException(
                400,
                f"Cannot hide locked field '{key}'",
            )
        clean: dict[str, Any] = {}
        if "visible" in cfg:
            clean["visible"] = bool(cfg["visible"])
        if "required" in cfg:
            clean["required"] = bool(cfg["required"])
        if "readonly" in cfg:
            clean["readonly"] = bool(cfg["readonly"])
        if "order" in cfg:
            try:
                clean["order"] = int(cfg["order"])
            except (TypeError, ValueError):
                raise HTTPException(400, f"schema.fields['{key}'].order must be an integer")
        out[key] = clean
    return {"version": 1, "fields": out}


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def apply_to_payload(
    session: Session,
    user: User,
    entity: str,
    payload: dict,
    *,
    existing: Optional[dict] = None,
    existing_lines: Optional[list[dict]] = None,
    schema: Optional[dict] = None,
) -> tuple[dict, set[str]]:
    """Drop hidden keys (restore from existing on update); 400 if required missing.

    Returns ``(cleaned_payload, hidden_keys)``.
    """
    if schema is None:
        schema, _src = resolve_schema(session, user, entity)
    from services.permissions import field_access_map

    access = field_access_map(session, user, entity)
    overlay_hidden = {k for k, lvl in access.items() if lvl in ("none", "view")}
    hidden = hidden_keys(schema) | overlay_hidden
    required = required_keys(schema)
    dump = dict(payload)
    original_keys = set(payload)
    existing_d = dict(existing or {})
    lines = dump.get("lines")
    if isinstance(lines, list):
        dump["lines"] = [dict(ln) if isinstance(ln, dict) else ln for ln in lines]

    cf = dict(dump.get("custom_fields") or {})
    for key in hidden:
        if key.startswith("x."):
            cf.pop(key, None)
        elif key == "discount_pct":
            for i, line in enumerate(dump.get("lines") or []):
                if not isinstance(line, dict):
                    continue
                line.pop("discount_pct", None)
                if existing_lines and i < len(existing_lines):
                    prev = existing_lines[i].get("discount_pct")
                    if prev is not None:
                        line["discount_pct"] = prev
        else:
            if key not in original_keys:
                continue
            dump.pop(key, None)
            if key in existing_d:
                dump[key] = existing_d[key]
    if "custom_fields" in original_keys or any(k.startswith("x.") for k in hidden):
        dump["custom_fields"] = cf
    elif "custom_fields" not in original_keys:
        dump.pop("custom_fields", None)

    for key in required:
        if key in overlay_hidden:
            continue
        if key.startswith("x."):
            val = (dump.get("custom_fields") or {}).get(key)
        elif key == "discount_pct":
            continue
        else:
            val = dump.get(key)
        if _is_empty(val):
            raise HTTPException(400, f"Field '{key}' is required")

    return dump, hidden


def apply_to_model(
    session: Session,
    user: User,
    entity: str,
    body: BaseModel,
    *,
    existing: Any = None,
    existing_lines: Optional[list[dict]] = None,
) -> set[str]:
    """Mutate a Pydantic create/update body to match the tenant schema."""
    existing_d = existing.model_dump() if existing is not None and hasattr(existing, "model_dump") else existing
    dump, hidden = apply_to_payload(
        session, user, entity, body.model_dump(),
        existing=existing_d,
        existing_lines=existing_lines,
    )
    restored = type(body).model_validate(dump)
    for name in type(body).model_fields:
        setattr(body, name, getattr(restored, name))
    return hidden


def skip_custom_required(hidden: set[str]) -> set[str]:
    return {k for k in hidden if k.startswith("x.")}


def fmt_schema(
    entity: str,
    schema: dict,
    *,
    role: str,
    source_role: str,
    field_access: Optional[dict[str, str]] = None,
) -> dict:
    return {
        "entity": entity,
        "role": role,
        "source_role": source_role,
        "schema": {
            "version": int(schema.get("version") or 1),
            "fields": _fields_of(schema),
        },
        "locked": sorted(LOCKED_FIELDS.get(entity, ())),
        "field_access": field_access or {},
    }


def upsert_schema(
    session: Session,
    user: User,
    entity: str,
    role: str,
    schema: dict,
) -> FormSchema:
    clean = validate_schema_doc(entity, schema)
    row = load_row(session, user.tenant_id, entity, role)
    if row is None:
        row = FormSchema(
            tenant_id=user.tenant_id,
            entity=entity,
            role=role,
            payload_json=clean,
            updated_at=datetime.utcnow(),
            updated_by_id=user.id,
        )
    else:
        row.payload_json = clean
        row.updated_at = datetime.utcnow()
        row.updated_by_id = user.id
    session.add(row)
    return row
