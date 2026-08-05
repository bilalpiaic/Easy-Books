"""User Rights Module — permission management endpoints."""
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import User, UserPermission
from routers.common import AdminUserDep, CurrentUserDep, SessionDep, log_audit
from services.permissions import (
    PERMISSION_RESOURCES,
    _rights_enabled,
    get_effective_permission,
)

router = APIRouter(prefix="/api/permissions", tags=["permissions"])


class PermissionSet(BaseModel):
    permissions: dict[str, str]  # resource_key → "none"|"view"|"edit"
    my_data_only: bool
    module_enabled: bool


class PermissionUpdate(BaseModel):
    resource_key: str
    access_level: str  # "none" | "view" | "edit" | "default" (removes override)


@router.get("/me", response_model=PermissionSet)
def my_permissions(user: CurrentUserDep, session: SessionDep):
    """Full permission map for the calling user. Frontend fetches this at login."""
    module_on = _rights_enabled(user.tenant_id, session)
    perms = {key: get_effective_permission(user, key, session) for key in PERMISSION_RESOURCES}
    return PermissionSet(permissions=perms, my_data_only=user.my_data_only, module_enabled=module_on)


@router.get("/resources")
def list_resources(_: CurrentUserDep):
    """Full resource registry, used by the admin permissions matrix UI."""
    return [
        {"key": k, "label": v["label"], "category": v["category"]}
        for k, v in PERMISSION_RESOURCES.items()
    ]


@router.get("/users/{user_id}", response_model=PermissionSet)
def get_user_permissions(user_id: int, admin: AdminUserDep, session: SessionDep):
    target = session.get(User, user_id)
    if not target or target.tenant_id != admin.tenant_id:
        raise HTTPException(404, "User not found")
    module_on = _rights_enabled(admin.tenant_id, session)
    perms = {key: get_effective_permission(target, key, session) for key in PERMISSION_RESOURCES}
    return PermissionSet(permissions=perms, my_data_only=target.my_data_only, module_enabled=module_on)


@router.put("/users/{user_id}", status_code=200)
def set_user_permissions(
    user_id: int,
    updates: List[PermissionUpdate],
    admin: AdminUserDep,
    session: SessionDep,
):
    """Batch-upsert permission overrides. access_level='default' removes the override row."""
    target = session.get(User, user_id)
    if not target or target.tenant_id != admin.tenant_id:
        raise HTTPException(404, "User not found")
    if target.role == "owner" and admin.role != "owner":
        raise HTTPException(403, "Cannot modify owner permissions")

    for upd in updates:
        if upd.resource_key not in PERMISSION_RESOURCES:
            raise HTTPException(400, f"Unknown resource key: {upd.resource_key}")
        if upd.access_level not in ("none", "view", "edit", "default"):
            raise HTTPException(400, f"Invalid access_level: {upd.access_level}")

        existing = session.exec(
            select(UserPermission).where(
                UserPermission.tenant_id == admin.tenant_id,
                UserPermission.user_id == user_id,
                UserPermission.resource_key == upd.resource_key,
            )
        ).first()

        if upd.access_level == "default":
            if existing:
                session.delete(existing)
        elif existing:
            existing.access_level = upd.access_level
            session.add(existing)
        else:
            session.add(UserPermission(
                tenant_id=admin.tenant_id,
                user_id=user_id,
                resource_key=upd.resource_key,
                access_level=upd.access_level,
            ))

    session.commit()
    log_audit(session, admin, "UPDATE", "user_permissions", user_id, {"changes": len(updates)})
    session.commit()
    return {"updated": len(updates)}


@router.patch("/users/{user_id}/my-data-only", status_code=200)
def set_my_data_only(user_id: int, enabled: bool, admin: AdminUserDep, session: SessionDep):
    target = session.get(User, user_id)
    if not target or target.tenant_id != admin.tenant_id:
        raise HTTPException(404, "User not found")
    target.my_data_only = enabled
    session.add(target)
    session.commit()
    log_audit(session, admin, "UPDATE", "user", user_id, {"my_data_only": enabled})
    session.commit()
    return {"my_data_only": enabled}
