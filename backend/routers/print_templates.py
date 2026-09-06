"""Studio print-template picker / clone (#374)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.common import AdminUserDep, CurrentUserDep, SessionDep, log_audit
from services.permissions import perm_dep
from services.print_templates import (
    PRINT_ENTITIES,
    clone_template,
    delete_template,
    fmt_template,
    get_owned,
    list_templates,
    set_default,
    update_template,
)

router = APIRouter(
    prefix="/api/studio/print-templates",
    tags=["studio"],
    dependencies=[perm_dep("studio.print")],
)


class CloneBody(BaseModel):
    entity: str
    key: str
    label: str
    from_key: str = "standard"
    is_default: bool = False


class UpdateBody(BaseModel):
    label: Optional[str] = None
    html: Optional[str] = None
    is_default: Optional[bool] = None


class DefaultBody(BaseModel):
    entity: str
    key: str


@router.get("")
def get_templates(
    user: CurrentUserDep,
    session: SessionDep,
    entity: Optional[str] = None,
):
    if entity is not None and entity not in PRINT_ENTITIES:
        raise HTTPException(400, f"entity must be one of: {', '.join(sorted(PRINT_ENTITIES))}")
    return list_templates(session, user.tenant_id, entity)


@router.post("", status_code=201, dependencies=[perm_dep("studio.print", "edit")])
def post_clone(body: CloneBody, user: AdminUserDep, session: SessionDep):
    row = clone_template(
        session, user,
        entity=body.entity,
        key=body.key,
        label=body.label,
        from_key=body.from_key or "standard",
        is_default=body.is_default,
    )
    log_audit(session, user, "CREATE", "print_template", row.id, {"key": row.key, "entity": row.entity})
    session.commit()
    session.refresh(row)
    return fmt_template(row)


@router.put("/default", dependencies=[perm_dep("studio.print", "edit")])
def put_default(body: DefaultBody, user: AdminUserDep, session: SessionDep):
    set_default(session, user.tenant_id, body.entity, body.key)
    log_audit(session, user, "UPDATE", "print_template", None, {"entity": body.entity, "default": body.key})
    session.commit()
    return {"ok": True, "entity": body.entity, "key": body.key}


@router.get("/{template_id}")
def get_template(template_id: int, user: CurrentUserDep, session: SessionDep):
    row = get_owned(session, user.tenant_id, template_id)
    return fmt_template(row)


@router.put("/{template_id}", dependencies=[perm_dep("studio.print", "edit")])
def put_template(template_id: int, body: UpdateBody, user: AdminUserDep, session: SessionDep):
    row = get_owned(session, user.tenant_id, template_id)
    row = update_template(
        session, user, row,
        label=body.label,
        html=body.html,
        is_default=body.is_default,
    )
    log_audit(session, user, "UPDATE", "print_template", row.id, {"key": row.key})
    session.commit()
    session.refresh(row)
    return fmt_template(row)


@router.delete("/{template_id}", dependencies=[perm_dep("studio.print", "edit")])
def remove_template(template_id: int, user: AdminUserDep, session: SessionDep):
    row = get_owned(session, user.tenant_id, template_id)
    tid, key = row.id, row.key
    delete_template(session, user, row)
    log_audit(session, user, "DELETE", "print_template", tid, {"key": key})
    session.commit()
    return {"ok": True, "deleted": tid}
