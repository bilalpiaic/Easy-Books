"""Studio form-schema overlay (#373)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from routers.common import AdminUserDep, CurrentUserDep, SessionDep, log_audit
from services.custom_fields import assert_entity
from services.form_schema import (
    assert_role,
    fmt_schema,
    resolve_schema,
    upsert_schema,
)
from services.permissions import field_access_map, perm_dep

router = APIRouter(
    prefix="/api/studio/forms",
    tags=["studio"],
    dependencies=[perm_dep("studio.forms")],
)


class FormSchemaPut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    role: str = "*"
    doc: dict = Field(alias="schema")


@router.get("/{entity}")
def get_form_schema(
    entity: str,
    user: CurrentUserDep,
    session: SessionDep,
    role: Optional[str] = None,
):
    entity = assert_entity(entity)
    want = assert_role(role) if role is not None else (user.role or "*")
    schema, source = resolve_schema(session, user, entity, role=want)
    return fmt_schema(
        entity, schema, role=want, source_role=source,
        field_access=field_access_map(session, user, entity),
    )


@router.put("/{entity}", dependencies=[perm_dep("studio.forms", "edit")])
def put_form_schema(entity: str, body: FormSchemaPut, user: AdminUserDep, session: SessionDep):
    entity = assert_entity(entity)
    role = assert_role(body.role or "*")
    row = upsert_schema(session, user, entity, role, body.doc)
    session.flush()
    log_audit(
        session, user, "UPDATE", "form_schema", None,
        {"entity": entity, "role": role},
    )
    session.commit()
    session.refresh(row)
    return fmt_schema(
        entity, row.payload_json, role=role, source_role=role,
        field_access=field_access_map(session, user, entity),
    )
