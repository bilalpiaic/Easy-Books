"""Apply / archive Marketplace `studio` bundles. No partner code is executed."""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from models import CustomFieldDef, User
from services.custom_fields import MAX_DEFS, assert_entity, assert_key, assert_type, count_active
from services.form_schema import load_row, upsert_schema, validate_schema_doc
from services.marketplace.manifest import StudioBundle
from services.print_templates import PRINT_ENTITIES, set_default


def apply_studio_bundle(
    session: Session,
    user: User,
    extension_id: str,
    bundle: StudioBundle,
) -> dict:
    created: list[str] = []
    patched: list[str] = []
    for spec in bundle.custom_fields or []:
        entity = assert_entity(spec.entity)
        key = assert_key(spec.key)
        type_name = assert_type(spec.type)
        row = session.exec(
            select(CustomFieldDef).where(
                CustomFieldDef.tenant_id == user.tenant_id,
                CustomFieldDef.entity == entity,
                CustomFieldDef.key == key,
            )
        ).first()
        if row is None:
            if count_active(session, user.tenant_id, entity) >= MAX_DEFS:
                continue
            row = CustomFieldDef(
                tenant_id=user.tenant_id,
                entity=entity,
                key=key,
                label=spec.label.strip() or key,
                type=type_name,
                enum_values=list(spec.enum_values) if spec.enum_values else None,
                required=bool(spec.required),
                show_on_form=bool(spec.show_on_form),
                show_on_print=bool(spec.show_on_print),
                show_on_list=bool(spec.show_on_list),
                sort_order=int(spec.sort_order or 0),
                source_extension_id=extension_id,
            )
            session.add(row)
            created.append(f"{entity}:{key}")
        else:
            row.archived_at = None
            row.source_extension_id = extension_id
            if spec.label.strip():
                row.label = spec.label.strip()
            session.add(row)
            created.append(f"{entity}:{key}")

    for entity, patch in (bundle.form_schema_patch or {}).items():
        entity = assert_entity(entity)
        existing = load_row(session, user.tenant_id, entity, "*")
        base = dict((existing.payload_json if existing else None) or {"version": 1, "fields": {}})
        fields = dict(base.get("fields") or {})
        incoming = (patch or {}).get("fields") or patch or {}
        if isinstance(incoming, dict):
            for k, cfg in incoming.items():
                if isinstance(cfg, dict):
                    fields[k] = {**(fields.get(k) or {}), **cfg}
        merged = validate_schema_doc(entity, {"version": 1, "fields": fields})
        upsert_schema(session, user, entity, "*", merged)
        patched.append(entity)

    key = bundle.print_template_key
    if key:
        for ent in sorted(PRINT_ENTITIES):
            try:
                set_default(session, user.tenant_id, ent, key)
            except Exception:
                continue

    session.commit()
    return {"fields": created, "schemas": patched, "print_template_key": key}


def archive_studio_bundle(session: Session, tenant_id: int, extension_id: str) -> int:
    rows = list(
        session.exec(
            select(CustomFieldDef).where(
                CustomFieldDef.tenant_id == tenant_id,
                CustomFieldDef.source_extension_id == extension_id,
                CustomFieldDef.archived_at == None,  # noqa: E711
            )
        ).all()
    )
    now = datetime.utcnow()
    for row in rows:
        row.archived_at = now
        session.add(row)
    session.commit()
    return len(rows)
