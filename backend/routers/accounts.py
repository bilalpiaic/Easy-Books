"""Chart of accounts CRUD — with hierarchy validation, tree payload, next-code, activate."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select

from models import Account, JournalEntry
from services.accounts import (
    account_has_children,
    account_has_postings,
    suggest_next_code,
)

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/accounts", tags=["accounts"], dependencies=[perm_dep("accounts")])


class AccountCreate(BaseModel):
    code: str
    name: str
    type: Optional[str] = None  # defaults from parent when omitted
    parent_id: Optional[int] = None
    is_group: bool = False
    is_active: bool = True


class AccountUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    parent_id: Optional[int] = None
    is_group: Optional[bool] = None
    is_active: Optional[bool] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_descendants(session, tenant_id: int, account_id: int) -> set[int]:
    """Return the set of all descendant account IDs (not including account_id itself)."""
    # Build a parent→children map for all tenant accounts
    rows = session.exec(
        select(Account.id, Account.parent_id).where(Account.tenant_id == tenant_id)
    ).all()
    children_map: dict[int, list[int]] = {}
    for acct_id, parent_id in rows:
        if parent_id is not None:
            children_map.setdefault(parent_id, []).append(acct_id)

    descendants: set[int] = set()
    queue = list(children_map.get(account_id, []))
    while queue:
        nxt = queue.pop()
        descendants.add(nxt)
        queue.extend(children_map.get(nxt, []))
    return descendants


def _check_no_cycle(session, tenant_id: int, account_id: int, new_parent_id: int) -> None:
    """Raise 400 if setting parent_id=new_parent_id on account_id would create a cycle."""
    if account_id == new_parent_id:
        raise HTTPException(400, "Cycle detected: an account cannot be its own parent.")
    descendants = _get_descendants(session, tenant_id, account_id)
    if new_parent_id in descendants:
        raise HTTPException(
            400,
            "Cycle detected: the target parent is a descendant of this account.",
        )


def _check_dup_name(
    session, tenant_id: int, name: str, parent_id: Optional[int], exclude_id: Optional[int] = None
) -> None:
    """Raise 400 if another account under the same parent already has this name (case-insensitive)."""
    q = (
        select(Account)
        .where(Account.tenant_id == tenant_id)
        .where(Account.name.ilike(name))
    )
    if parent_id is None:
        q = q.where(Account.parent_id.is_(None))
    else:
        q = q.where(Account.parent_id == parent_id)
    if exclude_id is not None:
        q = q.where(Account.id != exclude_id)
    dup = session.exec(q).first()
    if dup:
        parent_label = f"parent {parent_id}" if parent_id else "top-level"
        raise HTTPException(
            400,
            f"An account named '{name}' already exists under {parent_label}.",
        )


def _check_parent_not_posted(session, tenant_id: int, parent_id: int) -> None:
    """Raise 400 if the designated parent already has journal entry postings."""
    if account_has_postings(session, tenant_id, parent_id):
        raise HTTPException(
            400,
            "Cannot add a sub-account to an account that already has journal entry postings. "
            "A posting account must remain a leaf.",
        )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/next-code")
def get_next_code(
    session: SessionDep,
    user: CurrentUserDep,
    parent_id: Optional[int] = Query(None),
):
    """Suggest the next available account code under *parent_id* (or top-level)."""
    code = suggest_next_code(session, user.tenant_id, parent_id)
    return {"code": code}


@router.post("")
def create_account(session: SessionDep, user: WriteUserDep, data: AccountCreate):
    # Resolve type from parent when omitted
    resolved_type = data.type
    if resolved_type is None:
        if data.parent_id is not None:
            parent = session.exec(
                select(Account).where(
                    Account.id == data.parent_id,
                    Account.tenant_id == user.tenant_id,
                )
            ).first()
            if parent is None:
                raise HTTPException(404, "Parent account not found.")
            resolved_type = parent.type
        else:
            raise HTTPException(422, "type is required when no parent_id is given.")

    # Validate parent exists and is in the same tenant
    if data.parent_id is not None:
        parent = session.exec(
            select(Account).where(
                Account.id == data.parent_id,
                Account.tenant_id == user.tenant_id,
            )
        ).first()
        if parent is None:
            raise HTTPException(404, "Parent account not found.")
        # Cannot add child under an account that already has postings
        _check_parent_not_posted(session, user.tenant_id, data.parent_id)

    # Duplicate code check (existing unique constraint — surface clean 400)
    existing = session.exec(
        select(Account).where(
            Account.tenant_id == user.tenant_id, Account.code == data.code
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Account code {data.code} already exists")

    # Duplicate name within same parent
    _check_dup_name(session, user.tenant_id, data.name, data.parent_id)

    account = Account(
        code=data.code,
        name=data.name,
        type=resolved_type,
        parent_id=data.parent_id,
        tenant_id=user.tenant_id,
        is_group=data.is_group,
        is_active=data.is_active,
    )
    session.add(account)
    session.flush()
    log_audit(
        session, user, "CREATE", "account", account.id,
        {"code": account.code, "name": account.name},
    )
    session.commit()
    session.refresh(account)
    return account


@router.put("/{account_id}")
def update_account(
    account_id: int, session: SessionDep, user: WriteUserDep, data: AccountUpdate
):
    account = session.exec(
        select(Account).where(
            Account.id == account_id, Account.tenant_id == user.tenant_id
        )
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Cycle check: if parent_id is being changed
    new_parent_id = data.parent_id
    if new_parent_id is not None and new_parent_id != account.parent_id:
        _check_no_cycle(session, user.tenant_id, account_id, new_parent_id)
        # Check that the new parent exists in the same tenant
        new_parent = session.exec(
            select(Account).where(
                Account.id == new_parent_id,
                Account.tenant_id == user.tenant_id,
            )
        ).first()
        if new_parent is None:
            raise HTTPException(404, "Parent account not found.")
        # Cannot move under an account that already has postings
        _check_parent_not_posted(session, user.tenant_id, new_parent_id)

    # Duplicate name check if name or parent_id is changing
    effective_name = data.name if data.name is not None else account.name
    effective_parent_id = new_parent_id if new_parent_id is not None else account.parent_id
    if data.name is not None or new_parent_id is not None:
        _check_dup_name(
            session, user.tenant_id, effective_name, effective_parent_id,
            exclude_id=account_id
        )

    for field in ("code", "name", "type", "parent_id"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(account, field, val)
    # Boolean fields need explicit None check (False is a valid value)
    for field in ("is_group", "is_active"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(account, field, val)

    session.add(account)
    log_audit(
        session, user, "UPDATE", "account", account.id,
        {"code": account.code, "name": account.name},
    )
    session.commit()
    session.refresh(account)
    return account


@router.patch("/{account_id}/active")
def set_account_active(
    account_id: int,
    session: SessionDep,
    user: WriteUserDep,
    is_active: bool = Query(...),
):
    """Activate or deactivate an account. Deactivated accounts are not postable."""
    account = session.exec(
        select(Account).where(
            Account.id == account_id, Account.tenant_id == user.tenant_id
        )
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.is_active = is_active
    session.add(account)
    log_audit(
        session, user, "UPDATE", "account", account.id,
        {"is_active": is_active},
    )
    session.commit()
    session.refresh(account)
    return account


@router.delete("/{account_id}")
def delete_account(account_id: int, session: SessionDep, user: WriteUserDep):
    account = session.exec(
        select(Account).where(
            Account.id == account_id, Account.tenant_id == user.tenant_id
        )
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if session.exec(select(JournalEntry).where(JournalEntry.account_id == account_id)).first():
        raise HTTPException(
            status_code=400, detail="Cannot delete account with existing journal entries"
        )
    log_audit(
        session, user, "DELETE", "account", account.id,
        {"code": account.code, "name": account.name},
    )
    session.delete(account)
    session.commit()
    return {"success": True}


@router.get("")
def list_accounts(
    session: SessionDep, user: CurrentUserDep,
    search: Optional[str] = None, skip: int = 0, limit: int = 200,
):
    q = select(Account).where(Account.tenant_id == user.tenant_id)
    if search:
        q = q.where(
            (Account.name.ilike(f"%{search}%")) | (Account.code.ilike(f"%{search}%"))
        )
    # Fetch all matching accounts (for computing tree fields; avoids N+1)
    all_results = session.exec(q.order_by(Account.code)).all()
    total = len(all_results)

    # Build parent→children map from ALL tenant accounts in ONE query (no N+1).
    # We query all tenant accounts (not just the search-filtered ones) so that
    # has_children and depth are correct even when a parent is filtered out.
    all_tenant_accts = session.exec(
        select(Account).where(Account.tenant_id == user.tenant_id)
    ).all()

    parent_ids_with_children: set[int] = set()
    depth_map: dict[int, int] = {}
    id_to_parent: dict[int, Optional[int]] = {}
    for a in all_tenant_accts:
        id_to_parent[a.id] = a.parent_id
        if a.parent_id is not None:
            parent_ids_with_children.add(a.parent_id)

    # Compute depth for each account by walking parent chain
    def _depth(acct_id: int, visited: set) -> int:
        if acct_id in depth_map:
            return depth_map[acct_id]
        if acct_id in visited:
            return 0  # cycle guard (shouldn't happen after validation)
        parent = id_to_parent.get(acct_id)
        if parent is None:
            d = 0
        else:
            d = 1 + _depth(parent, visited | {acct_id})
        depth_map[acct_id] = d
        return d

    for a in all_tenant_accts:
        _depth(a.id, set())

    # Apply pagination to all_results
    paginated = all_results[skip: skip + limit]

    items = []
    for a in paginated:
        d = a.model_dump()
        has_children = a.id in parent_ids_with_children
        postable = not a.is_group and a.is_active and not has_children
        depth = depth_map.get(a.id, 0)
        d["has_children"] = has_children
        d["postable"] = postable
        d["depth"] = depth
        items.append(d)

    return {"total": total, "items": items}
