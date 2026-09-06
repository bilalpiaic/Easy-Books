"""Studio custom-field definitions (#372). Values live on documents."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import CustomFieldDef
from routers.common import AdminUserDep, CurrentUserDep, SessionDep, log_audit
from services.custom_fields import (
    MAX_DEFS,
    assert_entity,
    assert_key,
    assert_type,
    count_active,
    fmt_def,
)
from services.permissions import perm_dep

router = APIRouter(
    prefix="/api/studio/fields",
    tags=["studio"],
    dependencies=[perm_dep("studio.fields")],
)


class FieldCreate(BaseModel):
    entity: str
    key: str
    label: str
    type: str = "text"
    enum_values: Optional[list[str]] = None
    required: bool = False
    show_on_form: bool = True
    show_on_print: bool = False
    show_on_list: bool = False
    sort_order: int = 0


class FieldUpdate(BaseModel):
    label: Optional[str] = None
    type: Optional[str] = None
    enum_values: Optional[list[str]] = None
    required: Optional[bool] = None
    show_on_form: Optional[bool] = None
    show_on_print: Optional[bool] = None
    show_on_list: Optional[bool] = None
    sort_order: Optional[int] = None


def _validate_enum(type_name: str, enum_values: Optional[list[str]]) -> Optional[list[str]]:
    if type_name == "enum":
        vals = [str(v) for v in (enum_values or []) if str(v).strip()]
        if len(vals) < 2:
            raise HTTPException(400, "enum fields need at least two enum_values")
        return vals
    return None


@router.get("")
def list_fields(
    user: CurrentUserDep,
    session: SessionDep,
    entity: Optional[str] = None,
    include_archived: bool = False,
):
    q = select(CustomFieldDef).where(CustomFieldDef.tenant_id == user.tenant_id)
    if entity:
        assert_entity(entity)
        q = q.where(CustomFieldDef.entity == entity)
    if not include_archived:
        q = q.where(CustomFieldDef.archived_at == None)  # noqa: E711
    rows = session.exec(
        q.order_by(CustomFieldDef.entity, CustomFieldDef.sort_order, CustomFieldDef.id)
    ).all()
    return [fmt_def(r) for r in rows]


@router.post("", status_code=201, dependencies=[perm_dep("studio.fields", "edit")])
def create_field(body: FieldCreate, user: AdminUserDep, session: SessionDep):
    entity = assert_entity(body.entity)
    key = assert_key(body.key)
    type_name = assert_type(body.type)
    if not (body.label or "").strip():
        raise HTTPException(400, "label is required")
    enum_values = _validate_enum(type_name, body.enum_values)

    dup = session.exec(
        select(CustomFieldDef).where(
            CustomFieldDef.tenant_id == user.tenant_id,
            CustomFieldDef.entity == entity,
            CustomFieldDef.key == key,
        )
    ).first()
    if dup:
        raise HTTPException(400, f"Field key '{key}' already exists for {entity}")

    if count_active(session, user.tenant_id, entity) >= MAX_DEFS:
        raise HTTPException(400, f"At most {MAX_DEFS} custom fields per entity")

    row = CustomFieldDef(
        tenant_id=user.tenant_id,
        entity=entity,
        key=key,
        label=body.label.strip(),
        type=type_name,
        enum_values=enum_values,
        required=bool(body.required),
        show_on_form=bool(body.show_on_form),
        show_on_print=bool(body.show_on_print),
        show_on_list=bool(body.show_on_list),
        sort_order=int(body.sort_order or 0),
    )
    session.add(row)
    session.flush()
    log_audit(session, user, "CREATE", "custom_field_def", row.id, {"key": key, "entity": entity})
    session.commit()
    session.refresh(row)
    return fmt_def(row)


@router.put("/{field_id}", dependencies=[perm_dep("studio.fields", "edit")])
def update_field(field_id: int, body: FieldUpdate, user: AdminUserDep, session: SessionDep):
    row = session.get(CustomFieldDef, field_id)
    if not row or row.tenant_id != user.tenant_id:
        raise HTTPException(404, "Field not found")
    if row.archived_at:
        raise HTTPException(400, "Archived fields cannot be edited")
    data = body.model_dump(exclude_unset=True)
    if "type" in data:
        data["type"] = assert_type(data["type"])
    type_name = data.get("type", row.type)
    if "enum_values" in data or "type" in data:
        data["enum_values"] = _validate_enum(type_name, data.get("enum_values", row.enum_values))
    if "label" in data:
        if not str(data["label"] or "").strip():
            raise HTTPException(400, "label is required")
        data["label"] = str(data["label"]).strip()
    for k, v in data.items():
        setattr(row, k, v)
    session.add(row)
    log_audit(session, user, "UPDATE", "custom_field_def", row.id, {"key": row.key})
    session.commit()
    session.refresh(row)
    return fmt_def(row)


@router.delete("/{field_id}", dependencies=[perm_dep("studio.fields", "edit")])
def archive_field(field_id: int, user: AdminUserDep, session: SessionDep):
    row = session.get(CustomFieldDef, field_id)
    if not row or row.tenant_id != user.tenant_id:
        raise HTTPException(404, "Field not found")
    if row.archived_at:
        return {"ok": True, "archived": True}
    row.archived_at = datetime.utcnow()
    session.add(row)
    log_audit(session, user, "DELETE", "custom_field_def", row.id, {"key": row.key, "archived": True})
    session.commit()
    return {"ok": True, "archived": True}
